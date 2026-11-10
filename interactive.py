"""Pruebas interactivas y evidencia de la práctica Docker."""
import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.table import Table


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


DEFAULT_PROBES = 10


def parse_command(text: str, servers: int) -> tuple[str, int | None]:
    words = text.strip().lower().split()
    if len(words) == 1 and words[0] in ("estado", "informe", "ayuda", "salir"):
        return words[0], None
    if words and words[0] == "probar":
        if len(words) == 1:
            return "probar", DEFAULT_PROBES
        if len(words) == 2:
            try:
                count = int(words[1])
            except ValueError:
                count = 0
            if count >= 1:
                return "probar", count
        raise ValueError("Comando inválido. Usa 'probar' o 'probar N' con N ≥ 1.")
    if len(words) == 2 and words[0] in ("detener", "iniciar"):
        try:
            number = int(words[1])
        except ValueError:
            number = 0
        if 1 <= number <= servers:
            return words[0], number
    raise ValueError(f"Comando inválido. Escribe 'ayuda'; servidores válidos: 1–{servers}.")


def compose_rows(command: list[str], run: Callable) -> dict[str, dict]:
    result = run(command + ["ps", "-a", "--format", "json"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "No se pudo consultar Docker Compose")
    return {item["Service"]: item for line in result.stdout.splitlines() if line.strip() for item in [json.loads(line)]}


def server_status(number: int, command: list[str], run: Callable, rows: dict | None = None) -> dict:
    service = f"servidor{number}"
    rows = compose_rows(command, run) if rows is None else rows
    docker = rows.get(service, {}).get("State", "ausente").lower()
    state = {"servidor": f"Servidor {number}", "docker": docker, "http": "desconectado", "detalle": ""}
    if docker != "running":
        state["detalle"] = "Contenedor no ejecutándose"
        return state
    code = "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/salud',timeout=2).read().decode())"
    result = run(command + ["exec", "-T", service, "python", "-c", code])
    if result.returncode:
        detail = (result.stderr or result.stdout or "Sin respuesta HTTP").strip()
        state["detalle"] = (detail.splitlines()[-1] if detail else "Sin respuesta HTTP")[-300:]
        return state
    try:
        health = json.loads(result.stdout.strip())
        if health == {"estado": "OK", "servidor": state["servidor"]}:
            state["http"] = "conectado"
        else:
            state["detalle"] = f"Respuesta inesperada: {health}"
    except ValueError as exc:
        state["detalle"] = f"Respuesta no JSON: {exc}"
    return state


def all_status(servers: int, command: list[str], run: Callable, fetch: Callable) -> tuple[list[dict], dict]:
    rows = compose_rows(command, run)
    services = [server_status(number, command, run, rows) for number in range(1, servers + 1)]
    balanceador = {"docker": rows.get("balanceador", {}).get("State", "ausente"), "http": "desconectado", "detalle": ""}
    if balanceador["docker"] == "running":
        try:
            health = fetch("http://localhost:8080/salud")
            if health.get("estado") == "OK" and health.get("servidor") in {f"Servidor {n}" for n in range(1, servers + 1)}:
                balanceador["http"] = "conectado"
                balanceador["detalle"] = f"Respondió {health['servidor']}"
            else:
                balanceador["detalle"] = f"Respuesta inesperada: {health}"
        except Exception as exc:
            balanceador["detalle"] = str(exc)
    return services, balanceador


def control_server(action: str, number: int, command: list[str], run: Callable, status: Callable = server_status) -> dict:
    if action not in ("iniciar", "detener") or number < 1:
        raise ValueError("Acción o servidor inválido")
    verb = "start" if action == "iniciar" else "stop"
    result = run(command + [verb, f"servidor{number}"])
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Error Docker").strip()[-300:])
    observed = status(number, command, run)
    expected = "running" if action == "iniciar" else "exited"
    if observed["docker"] != expected:
        raise RuntimeError(f"La acción terminó pero Docker muestra {observed['docker']} (se esperaba {expected})")
    if action == "iniciar":
        deadline = time.monotonic() + 10
        while observed["http"] != "conectado" and time.monotonic() < deadline:
            time.sleep(0.5)
            observed = status(number, command, run)
            if observed["docker"] != "running":
                raise RuntimeError(f"El contenedor dejó de ejecutarse: {observed['docker']}")
    return observed


def probe_round(servers: int, fetch: Callable, count: int = DEFAULT_PROBES) -> list[dict]:
    if count < 1:
        raise ValueError("La cantidad de pruebas debe ser ≥ 1.")
    expected = {f"Servidor {n}" for n in range(1, servers + 1)}
    records = []
    for number in range(1, count + 1):
        started = time.perf_counter()
        row = {"fecha": now(), "intento": number, "servidor": "", "error": "", "duracion_ms": 0}
        try:
            message = fetch("http://localhost:8080/").get("mensaje", "")
            matches = [name for name in expected if f"desde el {name}" in message]
            if len(matches) != 1:
                raise ValueError(f"Respuesta no identificada: {message}")
            row["servidor"] = matches[0]
        except Exception as exc:
            row["error"] = str(exc)
        row["duracion_ms"] = round((time.perf_counter() - started) * 1000, 2)
        records.append(row)
    return records


@dataclass
class Session:
    servers: int
    started_at: str = field(default_factory=now)
    events: list[dict] = field(default_factory=list)

    def add(self, action: str, **fields) -> dict:
        event = {"fecha": fields.pop("fecha", now()), "accion": action, **fields}
        self.events.append(event)
        return event


def export_report(session: Session, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    stem = f"practica-{session.servers}-servidores-{stamp}"
    markdown, csv_file = directory / f"{stem}.md", directory / f"{stem}.csv"
    lines = [f"# Informe de la práctica ({session.servers} servidores)", "", f"Inicio: {session.started_at}", f"Exportado: {now()}", "", "## Cronología observada", ""]
    for event in session.events:
        details = ", ".join(f"{key}={value}" for key, value in event.items() if key not in ("fecha", "accion"))
        lines.append(f"- {event['fecha']} — **{event['accion']}**: {details}")
    if not session.events:
        lines.append("- Aún no hay eventos registrados.")
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    fields = ("fecha", "modo_servidores", "inicio_sesion", "etapa", "intento", "servidor", "error", "duracion_ms")
    with csv_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for event in session.events:
            if event["accion"] == "solicitud":
                writer.writerow({**{key: event.get(key, "") for key in fields}, "modo_servidores": session.servers, "inicio_sesion": session.started_at})
    return markdown, csv_file


def show_status(console: Console, services: list[dict], balanceador: dict) -> None:
    table = Table(title="Estado observado")
    for col in ("Servicio", "Docker", "HTTP /salud", "Detalle"):
        table.add_column(col)
    for service in services:
        table.add_row(service["servidor"], service["docker"], service["http"], service["detalle"])
    table.add_row("Nginx", balanceador["docker"], balanceador["http"], balanceador["detalle"])
    console.print(table)


def show_round(console: Console, rows: list[dict]) -> None:
    total = len(rows)
    title = "Diez solicitudes reales" if total == DEFAULT_PROBES else f"{total} solicitudes reales"
    table = Table(title=title)
    for col in ("N.º", "Servidor", "Duración (ms)", "Error"):
        table.add_column(col)
    for row in rows:
        table.add_row(str(row["intento"]), row["servidor"] or "—", str(row["duracion_ms"]), row["error"])
    console.print(table)


def interactive_loop(servers: int, command: list[str], run: Callable, fetch: Callable, console: Console, reports: Path, session: Session) -> None:
    console.print("[bold]Comandos: estado | probar [N] | detener N | iniciar N | informe | ayuda | salir[/bold]")
    while True:
        try:
            text = console.input("[cyan]práctica> [/cyan]")
        except EOFError:
            return
        try:
            action, number = parse_command(text, servers)
            if action == "salir":
                return
            if action == "ayuda":
                console.print("estado: Docker y HTTP reales; probar [N]: N solicitudes (por defecto 10); detener/iniciar N: cambia una API; informe: Markdown + CSV; salir o Ctrl+C: apaga la pila.")
            elif action == "estado":
                services, balancer = all_status(servers, command, run, fetch)
                show_status(console, services, balancer)
                session.add("estado", servidores=services, balanceador=balancer)
            elif action == "probar":
                rows = probe_round(servers, fetch, count=number)
                show_round(console, rows)
                round_name = f"manual {1 + sum(event['accion'] == 'prueba' for event in session.events)}"
                for row in rows:
                    session.add("solicitud", etapa=round_name, **row)
                successes = sum(not row["error"] for row in rows)
                failures = sum(bool(row["error"]) for row in rows)
                total = len(rows)
                session.add("prueba", exitos=successes, errores=failures, solicitudes=total)
                console.print(f"Éxitos: {successes}/{total}; errores: {failures}/{total}")
            elif action in ("detener", "iniciar"):
                state = control_server(action, number, command, run)
                console.print(f"{state['servidor']}: Docker={state['docker']}, HTTP={state['http']}. {state['detalle']}")
                session.add(action, **state)
            elif action == "informe":
                md, csv_path = export_report(session, reports)
                console.print(f"Informe: {md}\nSolicitudes: {csv_path}")
        except (ValueError, RuntimeError, OSError) as exc:
            console.print(f"[red]No se completó '{text.strip()}': {exc}[/red]")
            session.add("error", comando=text.strip(), detalle=str(exc))
