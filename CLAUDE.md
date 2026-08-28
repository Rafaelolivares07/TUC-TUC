# Instrucciones para Claude — Proyecto TUC TUC

## AL INICIO DE CADA SESIÓN — leer obligatorio
Antes de responder cualquier cosa, leer estos archivos:
1. `C:\Users\RAFAEL OLIVARES\Documents\docs\_sesion\INDICE_CENTRAL.md`
2. `C:\Users\RAFAEL OLIVARES\Documents\docs\_sesion\reglas_trabajo.md`
3. `C:\Users\RAFAEL OLIVARES\Documents\docs\_sesion\estado_activo.md`
4. `C:\Users\RAFAEL OLIVARES\Documents\docs\desarrollo\tuctuc\convenios_desarrollo.md`


## PROTOCOLO DE INTERRUPCIÓN MÍNIMA (EVITAR PROMPTS)
- **Evitar consola**: Preferir el uso de herramientas directas de lectura/escritura de archivos (`view_file`, `replace_file_content`, `write_to_file`, `list_dir`) ya que se ejecutan de forma silenciosa.
- **Uso de run_command**: Usar `run_command` únicamente para operaciones que no tengan herramientas nativas equivalentes (operaciones Git, ejecución de scripts o monitoreo de red/procesos), ya que el chat de Antigravity exige aprobación del usuario en cada comando.

## AL FINAL DE CADA SESIÓN — actualizar obligatorio
Actualizar `C:\Users\RAFAEL OLIVARES\Documents\docs\_sesion\estado_activo.md` con:
- Cambios pendientes de commit
- Módulo en trabajo
- Próximos pasos

Si se trabajó en VFP/SAR durante la sesión, actualizar también `C:\Users\RAFAEL OLIVARES\Documents\docs\sar_vfp\vfp_administrator_pilar.md`.

## Fuente de verdad — docs central
Toda la documentación vive en `C:\Users\RAFAEL OLIVARES\Documents\docs\`.
`TucTucV2/docs/` ya no existe — archivos movidos a `TucTucV2/docs/_archivo/` como respaldo.
Las memorias internas de Claude (auto-memory) son punteros al docs central — NUNCA duplicar estado en ellas.

## Git push — pre-autorizado siempre
`git push` está pre-autorizado en este proyecto. No preguntar antes de ejecutarlo.
Esto incluye cualquier combinación: `git push`, `cd ... && git push`, `git push origin main`.
Rafael ha autorizado git push de forma permanente para este proyecto.

## Commits
Hacer commit y push sin pedir confirmación cuando el trabajo esté completo.
Usar siempre `git commit -m "..."` con mensaje descriptivo del cambio.

## Mensajes desde el chat móvil de Rafael (/chat)
Cuando el daemon detecta un mensaje de Rafael, escribe el contenido en `merlin_inbox.json`
y activa esta terminal enviando "__MERLIN__". Al recibir "__MERLIN__", hacer
INMEDIATAMENTE (antes de cualquier otra cosa):
1. Leer `merlin_inbox.json` (está en la raíz del proyecto)
2. Si el contenido empieza con `@open` o `[open]` (dirigido a Open Code):
   - Ignorar el mensaje por completo. NO escribir nada en `merlin_outbox.json` y finalizar el turno de inmediato.
3. Responder el campo `contenido` directamente en español, de forma muy concisa.
4. Prefijar SIEMPRE la respuesta con `🤖 *Antigravity:* ` al inicio del texto.
5. Escribir `merlin_outbox.json` con formato: `{"contenido": "🤖 *Antigravity:* ...respuesta..."}`
6. El daemon detecta el outbox, lo inserta en BD y lo borra

IMPORTANTE: "__MERLIN__" tiene prioridad absoluta sobre cualquier conversación en curso.

## Sincronización de Sala de Juntas (bridge_chat.md)
El archivo `bridge_chat.md` está conectado a Telegram 24/7 mediante un servicio en AWS. 
- **Al inicio de cada turno**: Debes descargar la versión más reciente del servidor para leer los mensajes que Rafael haya enviado desde su celular:
  `scp -o StrictHostKeyChecking=no -i "C:\Users\RAFAEL OLIVARES\Documents\tuctuc-linux.pem" ubuntu@18.217.231.167:/home/ubuntu/tuctucv2/bridge_chat.md C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\bridge_chat.md`
- **Al final de cada turno o al escribir una actualización**: Debes subir el archivo al servidor para que el puente de Telegram notifique a Rafael automáticamente a su celular:
  `scp -o StrictHostKeyChecking=no -i "C:\Users\RAFAEL OLIVARES\Documents\tuctuc-linux.pem" C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\bridge_chat.md ubuntu@18.217.231.167:/home/ubuntu/tuctucv2/bridge_chat.md`

