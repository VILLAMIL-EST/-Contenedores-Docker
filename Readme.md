# Servidores Docker: FastAPI + Nginx

<p align="center">
  <img src="docs/badges/estado.svg" alt="Estado funcional" />
  <img src="docs/badges/docker.svg" alt="Docker Compose" />
  <img src="docs/badges/python.svg" alt="Python 3.11+" />
  <img src="docs/badges/fastapi.svg" alt="FastAPI" />
  <img src="docs/badges/nginx.svg" alt="Nginx" />
  <img src="docs/badges/linux.svg" alt="Linux iniciar.sh" />
  <img src="docs/badges/windows.svg" alt="Windows iniciar.cmd" />
  <img src="docs/badges/curso.svg" alt="Redes y Comunicacion" />
</p>

Práctica de **Redes y Comunicación** (Universidad de Cundinamarca). Despliega APIs FastAPI detrás de Nginx: fase inicial con **2 servidores** y ampliación a **3**. El tráfico público entra por `http://localhost:8080` con balanceo round-robin.

Los scripts de arranque crean un `.venv` local, instalan solo dependencias del lanzador (Typer/Rich), construyen la pila Docker, verifican `/`, `/salud` y `/docs`, muestran diez solicitudes reales y abren una **consola interactiva** para simular caídas y exportar evidencia.

## Tabla de contenidos

- [Requisitos](#requisitos)
- [Ejecución rápida](#ejecución-rápida)
- [Linux (`iniciar.sh`)](#linux-iniciarsh)
- [Windows (`iniciar.cmd`)](#windows-iniciarcmd)
- [Consola interactiva](#consola-interactiva)
- [Uso manual sin lanzador](#uso-manual-sin-lanzador)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Créditos](#créditos)

## Requisitos

| Componente | Linux | Windows |
|---|---|---|
| Contenedores | Docker Engine + plugin `compose` en marcha | Docker Desktop con motor activo |
| Backend de Docker | Nativo (no hace falta Docker Desktop) | **WSL 2** obligatorio |
| Python | 3.11+ con `venv` y `pip` (`python3`) | 3.11+ (`py -3` o `python`) |
| Puerto | `8080` libre | `8080` libre |
| Red | Internet en la primera construcción de imágenes | Igual |

> [!NOTE]
> Los scripts resuelven siempre la carpeta donde están los archivos (`iniciar.sh` / `iniciar.cmd`). Puedes clonar o copiar el proyecto en cualquier ruta; no dependen de una ubicación fija del disco.

> [!WARNING]
> No mezcles la fase de 2 y la de 3 sin apagar la anterior: ambas publican el puerto **8080**. Si el lanzador detecta contenedores previos de esta misma práctica, **no los apaga automáticamente**; usa `./iniciar.sh --detener` (o `iniciar.cmd --detener`) y vuelve a iniciar.

## Ejecución rápida

| Sistema | Comando de entrada | Detener |
|---|---|---|
| Linux | `./iniciar.sh --servidores 2` | `Ctrl+C`, `salir` o cerrar la terminal |
| Linux (3 servidores) | `./iniciar.sh --servidores 3` | `Ctrl+C`, `salir` o cerrar la terminal |
| Windows | `iniciar.cmd --servidores 2` | `Ctrl+C`, `salir` o cerrar la terminal |
| Windows (3 servidores) | `iniciar.cmd --servidores 3` | `Ctrl+C`, `salir` o cerrar la terminal |
| Recuperación (huérfanos) | `./iniciar.sh --detener` / `iniciar.cmd --detener` | Apaga la pila si quedó activa |

`3` es el valor predeterminado si omites `--servidores`. Al salir (incluye cerrar la ventana de terminal), el lanzador hace `docker compose down` **solo** de la pila que él creó (nombre de proyecto derivado de la ruta del clon).

URLs útiles mientras corre:

- Principal: http://localhost:8080/
- Salud: http://localhost:8080/salud
- Swagger: http://localhost:8080/docs

## Linux (`iniciar.sh`)

```bash
chmod +x iniciar.sh   # solo la primera vez si hace falta
./iniciar.sh --servidores 2
# cuando termines esa fase:
./iniciar.sh --servidores 3
```

Qué hace exactamente el script:

1. Se posiciona en la raíz del proyecto.
2. Crea `.venv` si no existe (`python3 -m venv`).
3. Instala `requirements-cli.txt` dentro del venv (no instala paquetes globales).
4. Ejecuta `launcher.py` con los mismos argumentos que le pasaste (`--servidores 2` o `3`).

<details>
  <summary>Detalle del flujo tras el script (común con Windows)</summary>

  1. Comprueba que no haya contenedores previos de esta práctica y que el puerto 8080 esté libre.
  2. Construye imágenes e inicia Compose (perfil `tres` + `compose.tres.yaml` solo en modo 3).
  3. Espera salud real de cada API y del balanceador; visita `/docs`.
  4. Registra diez solicitudes a `/` en una tabla Rich.
  5. Abre la consola interactiva (`ayuda`, `estado`, `probar [N]`, …).
  6. Con `Ctrl+C`, `salir` o al cerrar la terminal (`SIGHUP`/`SIGTERM`), detiene únicamente su pila Compose.

</details>

## Windows (`iniciar.cmd`)

> [!IMPORTANT]
> En Windows la entrada soportada es **`iniciar.cmd`** (también vale el alias `activar.cmd`).  
> **No** uses `.\iniciar.ps1` directamente: PowerShell suele bloquear `.ps1` por ExecutionPolicy.  
> `iniciar.cmd` llama al preparador con `-ExecutionPolicy Bypass` **solo para ese arranque**; no necesitas `Set-ExecutionPolicy RemoteSigned`.

Desde CMD, PowerShell o explorador (doble clic), en la carpeta del proyecto:

```bat
iniciar.cmd --servidores 2
:: al terminar esa fase:
iniciar.cmd --servidores 3
```

Cadena real de arranque:

`iniciar.cmd` → `scripts\windows\preparar.ps1` (Bypass) → `.venv` + `launcher.py` → misma consola interactiva que en Linux.

<details>
  <summary>Qué prepara automáticamente en Windows</summary>

  1. Refresca el `PATH` de la sesión (evita el bucle “Docker no está en el PATH” justo después de `winget`).
  2. Busca `python` / `py` y, si falta, puede ofrecer instalar Python 3.12 con `winget` (confirmación S/N).
  3. Comprueba **WSL 2**. Si falta, puede abrir PowerShell elevado con `wsl --install --no-distribution`.
  4. Detecta Docker Desktop en Program Files o LocalAppData; **no lo reinstala** si ya está.
  5. Si Docker no está, puede ofrecer instalarlo con `winget`.
  6. Inicia Docker Desktop si hace falta y espera a que el motor responda (`docker info`).
  7. Crea `.venv`, sincroniza Typer/Rich, asegura la carpeta `informes\` y lanza la práctica.

</details>

> [!WARNING]
> Si el preparador instala o activa WSL, **reinicia Windows** y vuelve a ejecutar `iniciar.cmd`. Hasta que WSL esté listo, Docker Desktop mostrará errores del tipo “WSL is not installed” y la práctica no arrancará.

<details>
  <summary>Recuperación rápida si Docker ya está instalado pero falla el PATH o WSL</summary>

  1. Cierra la terminal actual.
  2. Abre una **nueva** CMD en la carpeta del proyecto.
  3. Ejecuta `iniciar.cmd --servidores 2`.
  4. Si pide WSL: acepta UAC → reinicia → otra vez `iniciar.cmd`.
  5. Confirma en Docker Desktop que el icono indique motor en marcha (“Engine running”).

</details>

## Consola interactiva

Cuando el arranque termina, escribe un comando y pulsa **Enter**:

| Comando | Acción |
|---|---|
| `ayuda` | Lista los comandos disponibles |
| `estado` | Estado Docker y `/salud` de cada API + balanceador |
| `detener 1` / `iniciar 1` | Detiene o recupera solo esa API (números válidos según modo 2 o 3) |
| `probar` / `probar N` | N solicitudes reales a `/` (por defecto 10; servidor, duración, errores) |
| `informe` | Exporta Markdown + CSV en `informes/` (ignorado por Git) |
| `salir` o **Ctrl+C** | Apaga la pila propia y termina |

> [!TIP]
> Secuencia útil para el informe del taller:  
> `estado` → `probar` → `detener 2` → `estado` → `probar 20` → `iniciar 2` → `estado` → `probar 5` → `informe`.  
> El estado del contenedor y la respuesta HTTP pueden diferir: un contenedor “running” no se da por conectado si `/salud` falla. Los errores de red se registran tal cual; no se inventan respuestas.

## Uso manual sin lanzador

<details>
  <summary>Comandos Docker Compose directos</summary>

```bash
# Fase 1 — dos servidores
docker compose -f compose.yaml up --build -d
docker compose -f compose.yaml down

# Ampliación — tres servidores
docker compose --profile tres -f compose.yaml -f compose.tres.yaml up --build -d
docker compose --profile tres -f compose.yaml -f compose.tres.yaml down
```

Para depurar: `docker compose logs`. El lanzador, si falla, muestra el error de Docker al final.

**Tests locales** (tras haber corrido el script al menos una vez, para tener `.venv`):

```bash
# Linux
.venv/bin/python -m unittest discover -s tests -v

# Windows
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

</details>

## Estructura del proyecto

| Archivo / carpeta | Rol |
|---|---|
| `app.py` | FastAPI: `/` y `/salud`; `SERVIDOR` distingue cada instancia |
| `Dockerfile` | Imagen `python:3.11-slim` + Uvicorn en el puerto 8000 |
| `compose.yaml` + `nginx/nginx.conf` | Fase de 2 servidores + Nginx en 8080 |
| `compose.tres.yaml` + `nginx/nginx.tres.conf` | Ampliación a 3 servidores |
| `launcher.py` / `interactive.py` | Orquestación, pruebas y export de informes |
| `iniciar.sh` | Entrada Linux |
| `iniciar.cmd` / `activar.cmd` | Entrada Windows (alias incluido) |
| `scripts/windows/preparar.ps1` | Bootstrap Windows (PATH, WSL, Docker, venv) |
| `iniciar.ps1` | Solo delega en `iniciar.cmd`; no es la vía recomendada |
| `requirements-cli.txt` | Typer/Rich del lanzador |
| `tests/` | Pruebas de modos, wrappers, consola e informes |
| `docs/badges/` | Badges SVG del README |
| `informes/` | Salida local de `informe` (no versionada) |

## Créditos

- **Autor original:** Yecid Villamil · Universidad de Cundinamarca, Ingeniería de Sistemas y Computación
- **Repositorio:** [VILLAMIL-EST/-Contenedores-Docker](https://github.com/VILLAMIL-EST/-Contenedores-Docker)
- Documentación: [Docker](https://docs.docker.com/) · [FastAPI](https://fastapi.tiangolo.com/) · [Nginx](https://nginx.org/en/docs/) · [WSL](https://learn.microsoft.com/windows/wsl/)
