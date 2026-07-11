# Reglas de Trabajo y Contexto de Merlin

Este archivo de personalización (regla de espacio de trabajo) se carga automáticamente al inicio de cada conversación en Antigravity.

## Acciones obligatorias al iniciar la sesión
Antes de responder al usuario por primera vez en la sesión, el agente debe leer de forma silenciosa los siguientes archivos utilizando las herramientas directas de lectura de archivos:
1. `C:\Users\RAFAEL OLIVARES\Documents\docs\_sesion\reglas_trabajo.md` (Reglas y comportamiento general)
2. `C:\Users\RAFAEL OLIVARES\Documents\docs\_sesion\estado_activo.md` (Estado actual y pendientes)
3. `C:\Users\RAFAEL OLIVARES\Documents\docs\tuctuc\convenios_desarrollo.md` (Lógica y convenios técnicos)

## Protocolo de interrupción mínima (Permisos)
- **Evitar consola**: Preferir el uso de herramientas directas del sistema de archivos (`view_file`, `replace_file_content`, `write_to_file`, `list_dir`) en lugar de comandos de consola (`run_command`), ya que la interfaz exige aprobación manual del usuario para cada comando de consola.
- **Uso de run_command**: Usar `run_command` únicamente para operaciones que no tengan herramientas nativas equivalentes (Git, ejecutar scripts, etc.).
- **Tono**: No hacer preguntas proactivas al final de cada respuesta. Responder en español de forma directa y concisa.
