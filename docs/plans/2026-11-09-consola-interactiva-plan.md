# Consola interactiva — plan de implementación

> **Para Hermes:** usar pruebas RED→GREEN por comportamiento; revisar cumplimiento y calidad antes de publicar.

**Objetivo:** Controlar y medir la caída/recuperación real de APIs en la pila Docker y exportar evidencia del taller.

**Arquitectura:** Mantener `launcher.py` para orquestación y agregar `interactive.py` con funciones puras/testeables de parseo, lectura de estado, diez intentos, sesión y exportación. `launcher.py` invoca el bucle después de la prueba inicial; `finally` preserva su limpieza. Todo usa comandos Compose con el proyecto y modo que ya existe.

**Stack:** Python stdlib (csv, datetime, urllib, pathlib), Rich/Typer instalados, Docker Compose, unittest.

---

### 1. Estado real por servidor
- Crear `tests/test_interactive.py` con RED: validar `parse_command` para `estado`, `probar`, `detener N`, `iniciar N`, `informe`, `ayuda`, `salir` y rechazo de N fuera de rango; consultar contenedor parado sin llamar `exec`; ejecutar `/salud` dentro del contenedor activo y separar estado Docker de respuesta HTTP.
- Implementar `interactive.py` con `parse_command`, `server_status`, `all_status`; inyectar `checked`, `fetch_json` o funciones equivalentes para tests. `docker compose ps -a --format json` devuelve JSON por línea y puede incluir un solo objeto. En modo 2 no incluir servidor3.
- Ejecutar `.venv/bin/python -m unittest tests.test_interactive -v` y luego suite completa.

### 2. Caída, recuperación y pruebas reales
- RED: `detener`/`iniciar` forman `compose stop/start servidorN`, verifican estado después, y los errores vuelven al prompt. `probar` hace exactamente diez intentos incluso si uno falla; cada registro tiene marca temporal, duración, respuesta o mensaje de error.
- Implementar funciones `control_server`, `probe_round`, `interactive_loop` y registrar eventos tipados. Reusar `record_requests` inicial sin alterar semántica observable o adaptar para registrar su resultado. Un comando erróneo no termina la sesión; Ctrl+C/`salir` sí.
- Tests unitarios y smoke Linux con dos/tres servidores, parada de una API, estado degradado, prueba de balanceador, reinicio y limpieza con Ctrl+C.

### 3. Informe y guía
- RED: exportación Markdown + CSV a directorio indicado (test con `TemporaryDirectory`), contenido con modo, momentos, errores y resultados; sin datos inventados.
- Implementar `export_report`; ignorar `/informes/` en `.gitignore`; actualizar `Readme.md` con comandos de teclado y límites Windows.
- Ejecutar `unittest discover -s tests -v`, `bash -n iniciar.sh`, Compose config de ambos modos, `git diff --check`. Hacer revisión independiente de spec y calidad; corregir antes del push.

### 4. PR #1
- Confirmar que el head remoto no avanzó ajeno: `git fetch origin` y comparar ramas. Commit específico de código/tests/docs, `git push origin HEAD` sin force. Actualizar cuerpo del PR #1 con resultados reales y limitación de Windows; leer de vuelta URL, base, head SHA, body y checks. **No hacer merge.**
