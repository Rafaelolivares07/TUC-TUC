# Estado de Sesión Activa
_Actualizado: 2026-03-31_

## Módulo en trabajo
**Chat /chat — features nuevos + Alegra/Pilar Peralta (pendiente)**

## Trabajo sesión 2026-03-31 (continuación tarde)

### /chat — features implementados
- **Barra input rediseñada**: fila 1 = textarea + enviar, fila 2 = íconos secundarios
- **Title dinámico**: pestaña muestra "Nombre — TUC TUC" al abrir un chat, "Chat — TUC TUC" en el listado
- **Sistema apuntes**: tabla `apuntes`, modo apunte (toggle 📌), panel colapsable "📌 N apuntes" encima del hilo, botón ➤ por apunte para enviar al contacto cuando se decida
- **TTS 🔊**: toggle en barra secundaria — activo (verde) lee mis mensajes en voz alta al llegar. Persiste en localStorage. Web Speech API, sin costo.
- **Chulos ✓✓**: ✓ gris = llegó al servidor, ✓✓ azul = bridge/destinatario lo procesó (estado='leido'). Aplica a texto, audio e imagen. Polling actualiza en vivo cada 3s. Endpoint `/api/chat/mensajes/estados`.

### Convenios actualizados
- §7 timestamps en `convenios_desarrollo.md`
- Reglas de trabajo actualizadas (timestamps corregidos, §6 y §7 en índice)

### Commits de esta sesión (tarde)
- `e28464e` — fix(chat): barra input rediseñada
- `2c0274c` — fix(chat): title dinámico con nombre del contacto
- `00396f4` — feat(chat): sistema de apuntes completo
- `78114a2` — feat(apuntes): botón enviar al chat por apunte
- `29885fd` — feat(chat): TTS toggle con Web Speech API
- `37061c7` — feat(chat): chulos ✓✓ en burbujas propias

## Pendientes
- **Alegra/Pilar:** identificar registro "bolsa" ($73) → manejarlo como impuesto separado en formulario VFP. Mapeo métodos de pago también pendiente.
- **Whisper tiny**: transcripción de audios imprecisa — considerar `small` para apuntes de audio que Merlin debe leer
- **Logs de presencia /domótica**: Rafael mencionó buen comportamiento — verificar si algo quedó pendiente

## Regla de timestamps (convenio §7)
- **BD**: sesión PG en `America/Bogota` → `CURRENT_TIMESTAMP` guarda hora Colombia
- **Python**: serializar con `ZoneInfo('America/Bogota')` → ISO con `-05:00`
- **JS chat**: `toLocaleTimeString('es-CO')` sin `timeZone` forzado
- **JS logs/domótica**: `toLocaleString('es-CO', { timeZone: 'America/Bogota' })`

## Contexto técnico
- bypassPermissions activo en `~/.claude/settings.json` ✓
- Rafael trabaja en Cali, Colombia — timezone America/Bogota
- App en producción: `tuc-tuc.onrender.com`
- Rafael trabaja principalmente desde el celular — responder siempre por /chat, no preguntar en terminal
