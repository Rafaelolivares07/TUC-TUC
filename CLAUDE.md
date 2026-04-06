# Instrucciones para Claude — Proyecto TUC TUC

## AL INICIO DE CADA SESIÓN — leer obligatorio
Antes de responder cualquier cosa, leer estos dos archivos:
1. `docs/leer al inicio cada sesion - reglas de trabajo.md`
2. `docs/leer al inicio cada sesion - estado sesion activa.md`
3. `docs/convenios_desarrollo.md`

## AL FINAL DE CADA SESIÓN — actualizar obligatorio
Actualizar `docs/leer al inicio cada sesion - estado sesion activa.md` con:
- Cambios pendientes de commit
- Módulo en trabajo
- Próximos pasos

Si se trabajó en VFP/SAR durante la sesión, actualizar también `docs/vfp_administrator_pilar.md`.

## Fuente de verdad — docs/
Toda la documentación, estado y manuales viven en `docs/` de este proyecto.
Las memorias internas de Claude (auto-memory) son punteros a docs/ — NUNCA duplicar estado en ellas.
Si algo cambia, actualizar el archivo en docs/, no la memoria interna.

## Git push — pre-autorizado siempre
`git push` está pre-autorizado en este proyecto. No preguntar antes de ejecutarlo.
Esto incluye cualquier combinación: `git push`, `cd ... && git push`, `git push origin main`.
Rafael ha autorizado git push de forma permanente para este proyecto.

## Commits
Hacer commit y push sin pedir confirmación cuando el trabajo esté completo.
Usar siempre `git commit -m "..."` con mensaje descriptivo del cambio.

## Mensajes desde el chat móvil de Rafael (/chat)
Cuando el captura_watcher detecta un mensaje de Rafael en el chat de Merlin,
activa esta terminal enviando "__MERLIN__" como input. Al recibir "__MERLIN__", hacer
INMEDIATAMENTE (antes de cualquier otra cosa):
1. Consultar `chat_mensajes` en BD: último mensaje `rol='user'`, `canal='captura'`, `archivado=FALSE`, con `id` mayor al del último `rol='assistant'` no archivado
2. Responder ese mensaje directamente (en español, conciso) — NO explicar el proceso, solo responder
3. Insertar la respuesta en `chat_mensajes (rol='assistant', contenido=..., canal='captura')`
4. El bridge detecta la respuesta y la copia al /chat del usuario

IMPORTANTE: "__MERLIN__" tiene prioridad absoluta sobre cualquier conversación en curso.

DB: usar `os.getenv('DATABASE_URL')` con psycopg2 (el .env está en la raíz del proyecto).
Columnas de `chat_mensajes`: id, rol, contenido, created_at, estado, archivado, canal
