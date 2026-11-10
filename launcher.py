#!/usr/bin/env python3
"""Lanzador interactivo de las fases de dos y tres servidores."""
import atexit
import hashlib
import json
import signal
import socket
import subprocess
import time
from collections import Counter
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import typer
from rich.console import Console
from rich.table import Table

import interactive

ROOT = Path(__file__).resolve().parent
PROJECT_NAME = "taller-" + hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:12]
LOCAL_HTTP = build_opener(ProxyHandler({}))
console = Console()
app = typer.Typer(help="Práctica de servidores Docker con Nginx")


def compose_command(servers: int) -> list[str]:
    if servers not in (2, 3):
        raise ValueError("--servidores debe ser 2 o 3")
    command = ["docker", "compose", "-f", "compose.yaml", "-p", PROJECT_NAME]
    if servers == 3:
        command.extend(["--profile", "tres", "-f", "compose.tres.yaml"])
    return command


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def checked(command: list[str]) -> subprocess.CompletedProcess:
    result = run_command(command)
    if result.returncode:
        detail = (result.stderr or result.stdout or "sin detalles").strip()[-3000:]
        raise RuntimeError(f"{' '.join(command)}: {detail}")
    return result


def fetch_json(url: str) -> dict:
    with LOCAL_HTTP.open(url, timeout=3) as response:
        return json.load(response)


def wait_until_healthy(servers: int, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    expected = {f"Servidor {n}" for n in range(1, servers + 1)}
    while time.monotonic() < deadline:
        try:
            for number in range(1, servers + 1):
                code = "import json,urllib.request; print(urllib.request.urlopen('http://localhost:8000/salud',timeout=2).read().decode())"
                response = checked(compose_command(servers) + ["exec", "-T", f"servidor{number}", "python", "-c", code])
                health = json.loads(response.stdout.strip())
                if health != {"estado": "OK", "servidor": f"Servidor {number}"}:
                    raise RuntimeError(f"Estado de servidor{number} incorrecto: {health}")
            public_health = fetch_json("http://localhost:8080/salud")
            if public_health.get("estado") != "OK" or public_health.get("servidor") not in expected:
                raise RuntimeError(f"Estado del balanceador incorrecto: {public_health}")
            with LOCAL_HTTP.open("http://localhost:8080/docs", timeout=3) as response:
                if response.status != 200 or b"swagger" not in response.read().lower():
                    raise RuntimeError("La documentación /docs no responde correctamente")
            return
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            time.sleep(1)
    raise TimeoutError(f"Los {servers} servidores y el balanceador no respondieron en {timeout}s; consulte docker compose logs")


def record_requests(servers: int) -> list[str]:
    expected = {f"Servidor {n}" for n in range(1, servers + 1)}
    table = Table(title="Diez solicitudes a http://localhost:8080/")
    table.add_column("Solicitud", justify="right")
    table.add_column("Servidor que respondió")
    responses = []
    for number in range(1, 11):
        data = fetch_json("http://localhost:8080/")
        message = data.get("mensaje", "")
        matches = [name for name in expected if f"desde el {name}" in message]
        if len(matches) != 1:
            raise RuntimeError(f"Respuesta no reconocida en solicitud {number}: {data}")
        responses.append(matches[0])
        table.add_row(str(number), matches[0])
    console.print(table)
    console.print("Distribución:", dict(sorted(Counter(responses).items())))
    if set(responses) != expected:
        console.print("[yellow]Advertencia: no respondieron todos los servidores en estas diez solicitudes.[/yellow]")
    return responses


def stop_project() -> None:
    """Detiene la pila Compose de esta práctica (incluye servicios del perfil tres)."""
    with console.status("[cyan]Deteniendo contenedores de la práctica…", spinner="dots"):
        checked(compose_command(3) + ["down"])
    console.print("[green]Contenedores detenidos.[/green]")


def _shutdown_signals() -> tuple[signal.Signals, ...]:
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        signals.append(signal.SIGHUP)
    return tuple(signals)


def launch(servers: int) -> None:
    command = compose_command(servers)
    existing = checked(compose_command(3) + ["ps", "-a", "-q"])
    if existing.stdout.strip():
        raise RuntimeError(
            "Hay contenedores existentes de esta práctica. "
            "Ejecuta ./iniciar.sh --detener (o iniciar.cmd --detener) y vuelve a iniciar; no se alteraron."
        )
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 8080))
        except OSError as exc:
            raise RuntimeError("El puerto 8080 está ocupado; no se iniciaron contenedores") from exc
    started = False
    cleaned = False
    failure: Exception | None = None
    previous_handlers: dict[signal.Signals, object] = {}

    def cleanup_stack() -> None:
        nonlocal cleaned
        if cleaned or not started:
            return
        cleaned = True
        try:
            with console.status("[cyan]Deteniendo contenedores de la práctica…", spinner="dots"):
                checked(command + ["down"])
            console.print("[green]Contenedores detenidos.[/green]")
        except Exception as cleanup_error:
            if failure is None:
                raise
            console.print(f"[red]Además, falló la limpieza: {cleanup_error}[/red]")

    def on_terminal_gone(signum: int, _frame: object) -> None:
        # SystemExit ejecuta finally/atexit; sin esto, cerrar la terminal deja la pila en -d.
        raise SystemExit(128 + signum)

    try:
        with console.status("[cyan]Construyendo las imágenes Docker…", spinner="dots"):
            checked(command + ["build"])
        started = True
        atexit.register(cleanup_stack)
        for sig in _shutdown_signals():
            previous_handlers[sig] = signal.signal(sig, on_terminal_gone)
        with console.status("[cyan]Iniciando contenedores…", spinner="dots"):
            checked(command + ["up", "-d", "--no-build"])
        with console.status("[cyan]Comprobando APIs, balanceador y Swagger…", spinner="dots"):
            wait_until_healthy(servers)
        console.print(f"[green]Activos: {servers} servidores y Nginx en http://localhost:8080[/green]")
        session = interactive.Session(servers)
        for attempt, name in enumerate(record_requests(servers), start=1):
            session.add("solicitud", etapa="inicial", intento=attempt, servidor=name, error="", duracion_ms="")
        console.print(
            "[bold]Escribe 'ayuda' para pruebas interactivas; "
            "Ctrl+C, 'salir' o cerrar la terminal detiene la práctica.[/bold]"
        )
        interactive.interactive_loop(servers, command, run_command, fetch_json, console, ROOT / "informes", session)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupción recibida.[/yellow]")
    except Exception as exc:
        failure = exc
        raise
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)  # type: ignore[arg-type]
        atexit.unregister(cleanup_stack)
        cleanup_stack()


@app.command()
def main(
    servidores: int = typer.Option(3, "--servidores", help="Fase inicial: 2; ampliación: 3"),
    detener: bool = typer.Option(False, "--detener", help="Detiene contenedores huérfanos de esta práctica y sale"),
) -> None:
    try:
        if detener:
            stop_project()
            return
        launch(servidores)
    except (RuntimeError, TimeoutError, ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
