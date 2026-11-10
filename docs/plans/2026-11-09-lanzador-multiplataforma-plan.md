# Lanzador de dos y tres servidores — plan de implementación

> **Para Hermes:** ejecutar por tareas con pruebas primero y revisión de cumplimiento/calidad. No publicar hasta terminar las verificaciones locales.

**Objetivo:** Ejecutar y detener la práctica desde una sola terminal en Linux/Windows, en modo de dos o tres servidores, con estados reales y registro de diez respuestas.

**Arquitectura:** Compose base (2) + perfil y override (3). Un lanzador Python con Typer/Rich gestiona Docker y limpieza; dos scripts mínimos crean su venv e invocan el mismo lanzador.

**Stack:** Docker Compose, Python 3.11+, Typer, Rich, unittest, Bash y PowerShell.

---

### Tarea 1: configuración de ambos modos
- **Archivos:** modificar `compose.yaml`, `nginx/nginx.conf`; crear `compose.tres.yaml`, `nginx/nginx.tres.conf`.
- **Prueba RED:** escribir `tests/test_compose.py` que ejecute `docker compose config --format json` base y perfil+overlay y verifique servicios y volumen esperado; confirmar fallo antes del cambio.
- **GREEN:** servidor3 con `profiles: [tres]`; upstream base de dos; overlay del montaje Nginx para tres. Eliminar campo `version` obsoleto. Comprobar con `python -m unittest tests.test_compose -v` y `docker compose config` en ambos modos.
- **Commit:** `feat: configurar fases de dos y tres servidores`.

### Tarea 2: flujo orquestado y Ctrl+C
- **Archivos:** crear `launcher.py`, `requirements-cli.txt`, `tests/test_launcher.py`, `.gitignore`.
- **Prueba RED:** casos sobre selección 2/3, rechazo del stack preexistente, falla de build/arranque, plazo de salud y limpieza en interrupción. Inyectar runner/HTTP para aislar Docker sin probar dobles en lugar de lógica.
- **GREEN:** interfaz Typer `--servidores 2|3`, Rich spinner/tabla, comprobar Docker/puerto/stack, build, up, health de APIs, diez GET secuenciales, `/salud` y `/docs`, esperar Ctrl+C, `down` solo después de crear stack. Logging de fallos con salida Docker. `python -m unittest tests.test_launcher -v`.
- **Commit:** `feat: añadir lanzador interactivo con pruebas`.

### Tarea 3: scripts y guía
- **Archivos:** crear `iniciar.sh`, `iniciar.ps1`; modificar `Readme.md`; crear tests de scripts cuando aplique.
- **Prueba RED:** test que compruebe existencia/uso del CLI y modo tres en ambos scripts, y que `./iniciar.sh --help` y `--servidores 0` fallen/funcionen según corresponda.
- **GREEN:** bootstrap de venv, dependencias CLI, propagación de argumentos/códigos, CTRL+C, requisitos Windows/Linux, los dos comandos Compose manuales, cleanup y limitaciones. `bash -n iniciar.sh` y ejecución real Linux. No instalar paquetes globales.
- **Commit:** `docs: documentar ejecución y añadir scripts multiplataforma`.

### Tarea 4: integración y entrega
- **Verificación:** `python -m unittest discover -s tests -v`; `docker compose config` ambos modos; ejecución real en Linux de `./iniciar.sh --servidores 2` y luego 3, diez respuestas por modo, `/salud` y `/docs`; Ctrl+C seguido por `docker compose ps -a` vacío. `git diff origin/main...HEAD --check` y árbol limpio.
- **Revisión:** una revisión de requisitos y otra de calidad/seguridad; corregir resultados y repetir pruebas.
- **Publicación:** solo después crear fork `RavenCore99/-Contenedores-Docker`, cambiar `origin` a fork dejando `upstream` al original, push de rama, PR base original `main`; leer el PR de vuelta y no fusionar. Si no se puede validar Windows localmente, indicarlo y dejar CI Windows como verificación posterior sin prometerla.
