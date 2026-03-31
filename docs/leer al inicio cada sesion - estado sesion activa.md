# Estado de Sesión Activa
_Actualizado: 2026-03-31_

## Módulo en trabajo
**Bridge Merlin + /chat timestamps + captura_watcher**

## Trabajo sesión 2026-03-31 — commits pusheados

### Bridge Merlin — operativo y mejorado
- Trigger cambiado de `"."` a `"__MERLIN__"` — más inequívoco, menos colisiones
- `captura_watcher.ps1` actualizado con nuevo trigger (3 instancias)
- `CLAUDE.md` raíz y TUC TUC actualizados con instrucción `__MERLIN__` y query exacta
- `POLL_INTERVAL` reducido de 4s → 2s
- Modelo Whisper cambiado de `base` → `tiny` (3x más rápido)
- Whisper precargado al arranque (no paga costo en primer audio)
- Fix crítico: archivo temporal `.webm` ahora se crea y cierra ANTES de que Whisper lo lea (bug Windows handle)
- `get_conn()` del bridge ahora hace `SET TIME ZONE 'America/Bogota'` — consistente con Flask

### Timestamps /chat — fix completo
- **Raíz del problema**: sesión PG usa `America/Bogota` → `CURRENT_TIMESTAMP` guarda hora local Colombia
- **`_ser_msg`**: cambiado de `.replace(tzinfo=timezone.utc)` a `.replace(tzinfo=ZoneInfo('America/Bogota'))` → serializa como `-05:00`
- **`formatHora`** en `chat.html`: usa `toLocaleTimeString('es-CO')` sin forzar timeZone — el offset `-05:00` maneja la conversión
- **Regla para logs vs chat**: logs de sistema (domótica, presencia) pueden usar `America/Bogota` explícito en JS. Para chat, los timestamps vienen del servidor con offset correcto — no forzar timezone en el cliente. Usuarios en otras zonas horarias verán su hora local automáticamente si el offset es correcto.

### Scroll /chat — fix
- `renderMensajes` usa doble `requestAnimationFrame` antes de `scrollTop = scrollHeight` — garantiza scroll al final exacto después del paint completo

### Whisper instalado
- `openai-whisper` instalado en sistema (`pip install openai-whisper`)
- Funcional en Python314 (el que usa el bridge)

## Estado del bridge
- `chat_merlin_bridge.py` corriendo — PID activo (reiniciar con `tuctuc_merlin_bridge.bat` en Startup)
- `captura_watcher.ps1` corriendo — PID activo
- Flujo completo funcional: audio/texto en /chat → bridge transcribe → relay a esta terminal → respuesta → /chat

## Pendientes
- **Logs de presencia /domótica**: Rafael mencionó que ya tienen un buen comportamiento — revisar si algo quedó pendiente
- **Sistema de apuntes**: diseñado en sesión — tabla `apuntes` con autor + contacto_vinculado opcional. Pendiente implementar en TUC TUC
- **Alegra/Pilar**: sync operativo y probado — pendiente BROWSE VFP contra BD TEST → producción

## Regla de timestamps (convenio)
- **BD**: sesión PG en `America/Bogota` → `CURRENT_TIMESTAMP` guarda hora Colombia
- **Python**: serializar con `ZoneInfo('America/Bogota')` → ISO con `-05:00`
- **JS chat**: `toLocaleTimeString('es-CO')` sin `timeZone` forzado — el offset del servidor maneja todo
- **JS logs/domótica**: `toLocaleString('es-CO', { timeZone: 'America/Bogota' })` — para strings sin offset
- **Usuarios en otras zonas**: el offset `-05:00` en el ISO string hace que cada browser muestre su hora local automáticamente ✓

## Commits de esta sesión
- `c4103b3` — fix(chat): hora mensajes forzada a America/Bogota
- `2aa3477` — fix(chat): scroll al final exacto al cargar
- `eedb6ca` — fix(chat): timestamps — sesion PG es Bogota, serializar con -05:00 no UTC
- `80126d8` — fix(bridge): SET TIME ZONE Bogota en conexiones

## Contexto técnico
- bypassPermissions activo en `~/.claude/settings.json` ✓
- Rafael trabaja en Cali, Colombia — timezone America/Bogota
- App en producción: `tuc-tuc.onrender.com`
- Todas las migraciones de BD son automáticas vía `_asegurar_*` / `crear_tablas_*`
