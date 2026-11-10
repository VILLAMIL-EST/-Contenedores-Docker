# Diseño aprobado: consola interactiva de pruebas

## Decisión

La terminal que actualmente espera Ctrl+C pasará a un bucle de comandos de línea: `ayuda`, `estado`, `probar`, `detener N`, `iniciar N`, `informe` y `salir`. Ctrl+C seguirá apagando la pila entera. Alternativas descartadas: atajos de una tecla (menos claros entre Bash y PowerShell) y un panel TUI permanente (complejidad innecesaria).

## Modelo de estado y seguridad

`estado` consulta Docker Compose por el proyecto aislado y comprueba cada instancia en `/salud` mediante `docker compose exec -T` solo si su contenedor está en ejecución; muestra Docker y HTTP como campos distintos. Además comprueba `/salud` de Nginx por localhost:8080. Los errores se muestran como tales, sin convertirlos en 'conectado'. Solo se aceptan identificadores de servidor 1..2 o 1..3 conforme al modo. `detener N`/`iniciar N` usan `docker compose stop/start servidorN` de este proyecto, verifican el estado posterior y registran la acción; el contenedor Nginx no es seleccionable. Un fallo no debe apagar la pila ni perder el prompt; Ctrl+C y `salir` siguen ejecutando el `down` de la pila propia.

`probar` registra diez intentos reales a `/`, incluyendo errores HTTP y tiempos observados, muestra la distribución sin inventar respuestas y no exige que cada servidor aparezca (puede estar detenido). Debe seguir la validación inicial ya existente de las fases de dos y tres servidores. Nginx aplica el failover según su configuración real; no se promete una respuesta específica ante la primera petición tras una caída.

## Evidencia exportable

Cada sesión acumula eventos con fecha/hora ISO, tipo de comando, servidor, estados observados y resultados de solicitudes. `informe` crea bajo `informes/` (ignorado por Git) un Markdown legible y un CSV de intentos, con modo de ejecución, fechas y hechos observados — no conclusiones automáticas que excedan los datos. Las pruebas verificarán límites de servidor, estados Docker+HTTP independientes, recuperación y errores de red, diez intentos y la exportación. La guía indicará cómo usarlo en ambas plataformas y cómo adjuntar el informe al taller.

## Flujo Git

Los cambios se hacen como commits adicionales en `feat/launcher-dos-tres-servidores` y se envían al fork ya existente, actualizando el PR #1; no se fusiona. Raven confirmó la ejecución anterior en Linux. Windows sigue pendiente de ensayo real y se declara en el PR.
