# Diseño: lanzador multiplataforma de la práctica

## Objetivo y alcance

Presentar las dos fases del taller: dos APIs y luego tres, con Nginx en localhost:8080, diez solicitudes registradas por fase y una terminal que permanece abierta hasta Ctrl+C. La aplicación FastAPI y su Dockerfile no requieren cambios funcionales. La ejecución manual con Docker Compose seguirá documentada.

## Enfoques valorados

- **Typer + Rich (elegido):** una implementación Python común y adaptadores pequeños de shell/PowerShell. Rich muestra spinners, estados y tabla de respuestas reales; Typer valida la opción 2/3.
- Shell y PowerShell separados: sin dependencias Python externas, pero duplican gestión de procesos y pruebas.
- TUI con Halo y tqdm: más dependencias y una barra de porcentaje engañosa para una construcción Docker sin total conocido.

## Arquitectura y flujo

`iniciar.sh` y `iniciar.ps1` crean un entorno Python local si hace falta, instalan dependencias CLI fijadas y llaman `python launcher.py --servidores {2|3}`. Compose base incluye servidor1, servidor2 y Nginx con un upstream de dos; servidor3 usa el perfil `tres` y un overlay Compose sustituye solo el montaje del archivo Nginx por el upstream de tres. El comando equivalente para tres emplea `--profile tres -f compose.yaml -f compose.tres.yaml`; para dos, solo el compose base. El directorio `.venv` queda ignorado por Git.

El lanzador comprueba Docker/Compose, puerto 8080 y ausencia de contenedores existentes de esta práctica antes de construir. Ejecuta `build`, `up -d --no-build`, espera respuestas saludables desde las APIs y Nginx con plazo fijo, visita `/`, `/salud`, `/docs`, registra diez solicitudes secuenciales a `/` con respuestas y muestra el resumen. La terminal queda a la espera y Ctrl+C llama `down` para los contenedores que lanzó. Ante fallo de construcción/arranque, imprime diagnóstico, limpia únicamente los recursos que creó y devuelve código distinto de cero. No borra otros proyectos ni apaga contenedores preexistentes.

No habrá porcentaje de progreso inventado: Rich presenta spinner por fase y estados solo después de verificarlos. Las salidas de Docker se conservan para diagnóstico. Para Windows se ofrece `.ps1` (PowerShell); requiere Python disponible en el PATH/launcher `py` y Docker Engine. Linux usa `./iniciar.sh`.

## Pruebas y entrega

Tests del flujo, elección de fase, limpieza al interrumpir/fallar y protección de stack preexistente con procesos simulados; prueba real Linux de ambas fases con diez respuestas y Ctrl+C; README con uso, requisitos, fase inicial y ampliación. La ejecución Windows se podrá probar en CI Windows tras publicar, pero no se afirmará que se verificó en este Linux. Preparar la rama local y verificarla antes de crear el fork y abrir un PR hacia `VILLAMIL-EST/-Contenedores-Docker:main`. No fusionar el PR.
