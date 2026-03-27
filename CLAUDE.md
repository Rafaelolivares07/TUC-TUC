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

## Git push — pre-autorizado siempre
`git push` está pre-autorizado en este proyecto. No preguntar antes de ejecutarlo.
Esto incluye cualquier combinación: `git push`, `cd ... && git push`, `git push origin main`.
Rafael ha autorizado git push de forma permanente para este proyecto.

## Commits
Hacer commit y push sin pedir confirmación cuando el trabajo esté completo.
Usar siempre `git commit -m "..."` con mensaje descriptivo del cambio.

## Mensajes desde el chat móvil de Rafael (/chat)
Cuando el captura_watcher detecta un mensaje de Rafael en el chat de Merlin,
activa esta terminal enviando "." como input. Al recibir ".", hacer:
1. Consultar `chat_mensajes` en BD: último mensaje `rol='user'`, `canal='captura'`, `archivado=FALSE`, después del último `rol='assistant'`
2. Responder ese mensaje directamente (en español, conciso)
3. La respuesta queda guardada por el hook y el bridge la copia al chat de usuario

DB: usar `os.getenv('DATABASE_URL')` con psycopg2 (el .env está en la raíz del proyecto).
