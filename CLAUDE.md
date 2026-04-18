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
Cuando el daemon detecta un mensaje de Rafael, escribe el contenido en `merlin_inbox.json`
y activa esta terminal enviando "__MERLIN__". Al recibir "__MERLIN__", hacer
INMEDIATAMENTE (antes de cualquier otra cosa):
1. Leer `merlin_inbox.json` (está en la raíz del proyecto)
2. Responder el campo `contenido` directamente (en español, conciso) — NO explicar el proceso
3. Escribir `merlin_outbox.json` con formato: `{"contenido": "...respuesta..."}`
4. El daemon detecta el outbox, lo inserta en BD y lo borra

IMPORTANTE: "__MERLIN__" tiene prioridad absoluta sobre cualquier conversación en curso.
