# AWS Infrastructure Monitor

Monitor local y de solo lectura para la cuenta AWS que aloja TUC TUC, Lopez Refrigeration y el relay de asistencia remota.

## Objetivos

- Conservar la auditoria que detecta recursos con costo innecesario.
- Proteger expresamente la infraestructura productiva.
- Mostrar costos acumulados y comparacion con el mes anterior.
- Medir CPU, memoria, disco, red y consumo aproximado por aplicacion.
- Mostrar cuanto margen queda dentro del servidor actual.

## Seguridad

La aplicacion no contiene rutas de terminacion o eliminacion. Las recomendaciones de ahorro requieren revision manual en AWS.

Las credenciales AWS no se guardan en este proyecto. El monitor usa el perfil local `tuctuc-monitor`, asociado al usuario IAM `tuctuc-cost-monitor`. Este usuario no tiene consola ni permisos para eliminar recursos, y solo puede ejecutar el documento SSM fijo de capacidad.

## Ejecucion

1. Instalar AWS CLI y autenticar el perfil autorizado.
2. Instalar dependencias: `pip install -r requirements.txt`.
3. Ejecutar `start_monitor.bat`.
4. Abrir `http://127.0.0.1:5020`.

La auditoria de infraestructura se conserva durante cinco minutos. Los costos se guardan por fecha en `cost_cache.json` y Cost Explorer se consulta como maximo una vez al dia, aunque el monitor se cierre o se reinicie.
