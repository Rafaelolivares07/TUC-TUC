# Manual de Desarrollo — Chat Bridge Terminal↔/captura

> Módulo: Chat conversacional entre Rafael (celular) y Claude Code (terminal)
> Estado: En producción (2026-03-16)

---

## 1. Arquitectura general

```
[Rafael - celular]
    │ escribe en /captura
    ▼
POST /api/captura/mensaje
    │ guarda en chat_mensajes (canal='captura', rol='user')
    │ devuelve {ok, id}
    ▼
captura_watcher.ps1 (loop 10s en PowerShell)
    │ detecta: chat_mensajes WHERE canal='captura' AND rol='user' AND id > MAX(assistant id)
    │ activa Windows Terminal via WScript.Shell.AppActivate
    │ envía ".{ENTER}" al terminal
    ▼
Claude Code (esta terminal)
    │ hook UserPromptSubmit → chat_context_hook.py → inyecta historial + requerimientos
    │ Claude responde
    │ hook Stop → chat_terminal_hook.py → guarda respuesta en BD (canal='terminal', rol='assistant')
    ▼
GET /api/captura/historial?since_id=X (polling cada 4s)
    │ filtra: canal='captura' OR rol='assistant'
    ▼
[Frontend /captura - celular]
    │ muestra burbuja con respuesta
    │ TTS automático (Web Speech API)
```

---

## 2. Tabla `chat_mensajes`

```sql
CREATE TABLE chat_mensajes (
    id         SERIAL PRIMARY KEY,
    rol        VARCHAR(20) NOT NULL,    -- 'user' | 'assistant'
    contenido  TEXT NOT NULL,
    estado     VARCHAR(20),             -- 'enviado' | NULL
    canal      VARCHAR(20) DEFAULT 'terminal',  -- 'captura' | 'terminal'
    archivado  BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Valores de `canal`
- `'captura'` — mensaje enviado desde la UI /captura (celular de Rafael)
- `'terminal'` — mensaje guardado por el hook Stop desde la sesión terminal

### Valores de `estado`
- `'enviado'` — mensajes de Rafael desde /captura (los que el watcher detecta)
- `NULL` — mensajes guardados por el hook Stop (terminal → no disparan el watcher)

### Lógica de visibilidad en /captura
```sql
WHERE archivado = FALSE
  AND id > {since_id}
  AND (canal = 'captura' OR rol = 'assistant')
ORDER BY created_at ASC
```
Muestra: todos los mensajes de Rafael desde /captura + todas las respuestas de Claude.
Oculta: mensajes de user enviados desde la terminal (los `.` del watcher, contexto inyectado, etc.)

---

## 3. APIs Flask

### POST `/api/captura/mensaje`
Guarda un mensaje del usuario en la BD. No llama a la API de Anthropic.

**Payload**: `{ "mensaje": "texto del usuario" }`

**Respuesta exitosa**: `{ "ok": true, "id": 42 }`
- Devuelve el `id` para que el frontend actualice `ultimoId` y evite duplicados en el polling.

**Implementación**:
```python
row = conn.execute(
    "INSERT INTO chat_mensajes (rol, contenido, estado, canal) VALUES (%s, %s, %s, %s) RETURNING id",
    ('user', texto, 'enviado', 'captura')
).fetchone()
```
**Importante**: `RETURNING id` es obligatorio para obtener el ID (regla general del proyecto).

### GET `/api/captura/historial?since_id=X`
Devuelve mensajes nuevos desde `since_id`.

Sin `since_id`: devuelve los últimos 60 mensajes (carga inicial).

---

## 4. captura_watcher.ps1

**Ubicación**: `C:\Users\RAFAEL OLIVARES\captura_watcher.ps1`
**Log**: `C:\Users\RAFAEL OLIVARES\captura_watcher.log`

### Variables clave
```powershell
$DB_URL            = "postgresql://..."    # conexión directa a Render
$CLAUDE_WINDOW     = "Claude Code"        # título de ventana a activar
$COOLDOWN_SEC      = 45                   # mínimo entre disparos
$POLL_SEC          = 10                   # intervalo de polling
$HB_CADA           = 60                   # heartbeat de presencia cada N segundos
$SENDKEYS_COOLDOWN = 90                   # segundos a ignorar windowsIdle después de SendKeys
$PID_FILE          = "C:\Users\RAFAEL OLIVARES\claude_pid.txt"
```

### Query de detección (Python embebido)
```python
SELECT COUNT(*) FROM chat_mensajes
WHERE archivado = FALSE
  AND rol = 'user'
  AND canal = 'captura'
  AND created_at > NOW() - INTERVAL '10 minutes'
  AND id > COALESCE(
        (SELECT MAX(id) FROM chat_mensajes WHERE archivado = FALSE AND rol = 'assistant'),
        0)
```
Detecta mensajes de Rafael en /captura que aún no tienen respuesta de Claude.

### Activación de ventana — 3 intentos
```powershell
# Intento 1: por título exacto (falla si el título cambió)
$wshell.AppActivate("Claude Code")

# Intento 2: por PID guardado en archivo
$claudePid = [int](Get-Content $PID_FILE)
$wshell.AppActivate($claudePid)

# Intento 3: buscar WindowsTerminal en vivo (siempre funciona)
$wtProc = Get-Process WindowsTerminal | Select-Object -First 1
$wshell.AppActivate($wtProc.Id)
```

**Por qué 3 intentos**: el título de Windows Terminal incluye un emoji (✨ Claude Code) que no coincide exacto con "Claude Code". `AppActivate` busca coincidencia desde el inicio del título. El intento 3 es el fallback robusto.

### Por qué Python para la query
PowerShell no tiene driver nativo para PostgreSQL. Se escribe el script Python en un archivo temporal y se ejecuta con `python $tmp`. La DB_URL se pasa como variable de entorno (`$env:CW_DB_URL`) para evitar problemas de interpolación de strings en here-strings de PowerShell.

---

## 5. Hooks de Claude Code

### Configuración en `.claude/settings.json`
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python C:\\...\\chat_context_hook.py" }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python C:\\...\\chat_terminal_hook.py" }
        ]
      }
    ]
  }
}
```

### Carga de credenciales (ambos hooks)
Ninguno de los dos hooks usa `python-dotenv`. El `.env` se carga manualmente al inicio:
```python
_ENV_PATH = Path(r"C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\.env")
for _line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
    if _line and not _line.startswith('#') and '=' in _line:
        _k, _, _v = _line.partition('=')
        os.environ.setdefault(_k.strip(), _v.strip())
DB_URL = os.getenv('DATABASE_URL', '')
```

### set_window_title() — presente en AMBOS hooks
Guarda el PID de Windows Terminal en `claude_pid.txt` para que el watcher siempre tenga un PID válido:
```python
def set_window_title():
    r = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         'Get-Process WindowsTerminal -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Id'],
        capture_output=True, text=True, timeout=5
    )
    pid_str = r.stdout.strip()
    if pid_str.isdigit():
        Path(r"C:\Users\RAFAEL OLIVARES\claude_pid.txt").write_text(pid_str)
```
- En `chat_context_hook.py`: se llama al inicio (antes de responder)
- En `chat_terminal_hook.py`: se llama al final (después de guardar en BD)

Esto garantiza que el PID se actualiza en cada ciclo completo — útil si la terminal se reinicia entre prompts.

### chat_context_hook.py (UserPromptSubmit)
Se ejecuta ANTES de que Claude responda. Su output va a stdout y Claude Code lo inyecta como contexto adicional al prompt.

**Constantes clave**:
```python
MAX_MSGS  = 20   # últimos mensajes del historial a inyectar
MAX_CHARS = 600  # máximo de chars por mensaje (trunca con "…" si supera)
```

**Qué inyecta**:
1. Historial reciente de `chat_mensajes` (últimos 20, sin `archivado=TRUE`, ordenados ASC)
2. Requerimientos pendientes de `requerimientos` (hasta 30, estado NOT IN ('Completado', 'Descartado'))

**Por qué truncar a 600 chars**: para no saturar el contexto de Claude con mensajes muy largos. El historial completo está en BD; este es solo el vistazo rápido.

**Nota sobre stdin**: el hook recibe un payload JSON por stdin pero no lo necesita — lo consume con `sys.stdin.read()` y lo descarta. El output relevante es el historial que se imprime en stdout.

**Por qué forzar UTF-8 en stdout**:
```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```
Windows usa `cp1252` por defecto. Sin esto, los tildes y caracteres especiales del historial generan errores de encoding.

### chat_terminal_hook.py (Stop)
Se ejecuta DESPUÉS de cada respuesta de Claude. Lee el JSONL del transcript y guarda los mensajes nuevos en BD.

**Flujo**:
1. Lee `transcript_path` del payload JSON en stdin
2. Compara con `last_uuid` guardado en `C:\Users\RAFAEL OLIVARES\.claude\chat_hook_state.json`
3. Procesa solo eventos nuevos (posteriores al `last_uuid` anterior)
4. Extrae mensajes `user` (texto real, ignora `tool_result`) y `assistant` (ignora `thinking`/`tool_use`)
5. Inserta en `chat_mensajes` con `canal='terminal'`, `estado=NULL`
6. Actualiza `chat_hook_state.json` con el nuevo `last_uuid`
7. Llama `set_window_title()` para mantener el PID actualizado

**Estado NULL en INSERT**: a diferencia de los mensajes de /captura (que usan `estado='enviado'`), los mensajes de terminal se insertan con `estado=NULL`. Son informativos — no disparan el watcher.

**Por qué ignorar tool_result en mensajes user**: Claude Code los genera internamente como respuesta a tool calls. No son texto del usuario.

**connect_timeout**: `5s` en context_hook (debe ser rápido, bloquea el prompt), `10s` en terminal_hook (tiene más margen, corre después de responder).

---

## 6. Frontend — /captura

**Template**: `templates/captura_chat.html`
**Ruta Flask**: `/captura` (requiere autenticación)

### Polling
```javascript
let ultimoId = 0;

async function pollNuevos() {
    if (enviando) return;  // no interferir mientras espera respuesta del POST
    const r = await fetch('/api/captura/historial?since_id=' + ultimoId);
    const d = await r.json();
    d.mensajes.forEach(m => {
        agregarBurbuja(m.rol, m.contenido, m.rol === 'assistant');
        if (m.id > ultimoId) ultimoId = m.id;
    });
}
setInterval(pollNuevos, 4000);
```

### Envío sin duplicado
```javascript
async function enviarMensaje() {
    agregarBurbuja('user', txt);   // mostrar inmediatamente (UX)
    const d = await fetch('/api/captura/mensaje', { method: 'POST', ... });
    if (d.id && d.id > ultimoId) { ultimoId = d.id; }  // evitar que polling repita
    // La respuesta llega por polling cuando el Stop hook la guarda en BD
}
```

### TTS (Web Speech API)
- Voz: Google español > Microsoft español > cualquier es- > default
- Auto-play: configurable por el usuario, guardado en `localStorage`
- Botón "🔊 Escuchar" en cada burbuja de Claude
- Mientras TTS habla: `ttsHablando = true` — el mic no escucha en modo conversación

### Modo Conversación 🗣️ (manos libres)
Toggle en el header. Persiste en `localStorage` (`captura-convo`).

**Flujo completo:**
```
Usuario activa 🗣️
  → mic arranca automáticamente (iniciarMicAuto)
  → usuario habla
  → resultado isFinal → texto al textarea + timer SILENCIO_MS
  → barra de progreso azul se vacía visualmente
  → SILENCIO_MS sin hablar → auto-envío (enviarMensajeConvo)
  → mic se detiene (grabando = false)
  → typing indicator visible
  → polling detecta respuesta de Claude
  → agregarBurbuja → TTS auto-play (si autoplay ON)
  → TTS onend → mic arranca solo (si modo conversación)
  → ciclo continuo
```

**Constantes:**
```javascript
const SILENCIO_MS = 1800;  // ms de silencio antes de auto-enviar
```

**Estados que bloquean el mic:**
- `enviando === true` — Claude está procesando
- `ttsHablando === true` — Claude está leyendo en voz alta

**`enviarMensajeConvo()`** — variante de `enviarMensaje()` para uso automático:
- Detiene el mic antes de enviar
- Cancela el silencioTimer y oculta la barra de progreso
- No hace `inp.focus()` al terminar (no interrumpe el flujo de voz)

**Reactivación del mic — tres rutas posibles:**
1. TTS termina (`utt.onend`) → `iniciarMicAuto()` con 400ms de delay
2. Respuesta llega pero autoplay OFF → `iniciarMicAuto()` con 500ms de delay
3. `reconocedor.onend` (reconocedor se detiene solo) → `iniciarMicAuto()` con 300ms de delay

**Por qué delays en lugar de llamada inmediata**: el navegador necesita un ciclo de event loop para liberar el micrófono antes de poder reabrirlo. Sin delay, `reconocedor.start()` lanza una excepción silenciosa.

**Modo manual sigue disponible**: los botones 🎤 y ➤ funcionan en cualquier momento, incluso con 🗣️ activo. El usuario puede escribir en el textarea o tocar enviar sin romper nada.

**Si el permiso de mic es denegado**: el modo se desactiva automáticamente con toast de error.

---

## 7. Problemas conocidos y soluciones

| Problema | Causa | Solución |
|---|---|---|
| Watcher no activa ventana | Título "✨ Claude Code" ≠ "Claude Code" | Intento 3: Get-Process WindowsTerminal |
| PID de archivo obsoleto | Terminal reiniciada | Hook actualiza claude_pid.txt en cada prompt |
| Mensajes duplicados | agregarBurbuja + polling | POST devuelve id → ultimoId actualizado |
| Mensajes terminal visibles en /captura | Hook guardaba todo con canal='terminal' | Filtro: canal='captura' OR rol='assistant' |
| Python unterminated string | DB_URL interpolada en here-string PS1 | Pasar como $env:CW_DB_URL |
| Int32 overflow en elapsed | [int] no cabe 63B segundos | Usar [long] y chequear $null |
| Heartbeat reporta presencia con usuario ausente | SendKeys resetea idle de Windows → watcher leía windowsIdle<30 y actualizaba lastRealInput | $lastSendKeys + $SENDKEYS_COOLDOWN=90s — no actualizar lastRealInput por 90s después de SendKeys |
| Dos emisores de heartbeat en paralelo | presencia_heartbeat.ps1 + captura_watcher.ps1 corrían a la vez | Eliminar presencia_heartbeat.ps1 del startup; único emisor = captura_watcher.ps1 |

---

## 8. Iniciar el sistema

### Modo automático (configuración actual — recomendado)

Al iniciar sesión en Windows, el script `iniciar_tuctuc.ps1` arranca todo de forma automática:

1. `captura_watcher.ps1` corre en segundo plano, sin ninguna ventana visible.
2. Windows Terminal se abre **minimizado** en la barra de tareas con Claude Code listo.
3. Rafael puede abrir `/captura` en el celular inmediatamente.

**Acceso directo configurado en Startup de Windows:**
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TUC TUC Arranque.lnk
```
Apunta a:
```powershell
powershell.exe -NoProfile -WindowStyle Hidden -File "C:\Users\RAFAEL OLIVARES\iniciar_tuctuc.ps1"
```

**Contenido de `iniciar_tuctuc.ps1`:**
```powershell
# 1. Watcher del chat en segundo plano (sin ventana)
#    — también envía heartbeat de presencia domótica cada 60s
Start-Process powershell `
    -ArgumentList "-NoProfile -WindowStyle Hidden -File `"...\captura_watcher.ps1`"" `
    -WindowStyle Hidden

# 2. Claude Code en Windows Terminal (minimizado)
Start-Process wt `
    -ArgumentList "-w 0 nt --title `"✨ Claude Code`" -d `"...\MiAppMedicamentos`" powershell -NoExit -Command claude" `
    -WindowStyle Minimized
```

**Nota**: `presencia_heartbeat.ps1` (que existía antes) fue eliminado del startup.
El heartbeat de presencia ahora lo gestiona exclusivamente `captura_watcher.ps1` (ver sección 4).

**Política de ejecución:** `RemoteSigned` en `CurrentUser` — scripts locales corren sin aviso, sin necesidad de intervención.

---

### Modo manual (si algo falla o se reinicia el watcher)

Abrir una terminal PowerShell y ejecutar:
```powershell
& "C:\Users\RAFAEL OLIVARES\captura_watcher.ps1"
```

Al recibir el primer mensaje en la terminal de Claude Code, el hook `UserPromptSubmit` guarda automáticamente el PID de Windows Terminal en `claude_pid.txt`.

---

**Logs del watcher:**
```
[HH:mm:ss] Check: pendientes=1 elapsed=99999s
[HH:mm:ss] Mensaje pendiente - activando Claude...
[HH:mm:ss] Terminal activada OK
```

---

---

## 9. Deep linking — enlazar secciones del manual desde la app

El visor `docs_viewer.html` genera automáticamente un `id` en cada `h1`, `h2` y `h3` usando un renderer custom de `marked.js`. El `id` es la versión slugificada del texto del heading (minúsculas, sin tildes, espacios → guiones).

### Cómo construir un anchor

| Heading en el markdown | `id` generado |
|---|---|
| `## 1. Arquitectura general` | `1-arquitectura-general` |
| `## Modo Conversación 🗣️` | `modo-conversacion` |
| `### set_window_title()` | `set_window_title` |

### Enlace desde la app → sección del manual

```html
<!-- Desde cualquier input, label o tooltip en la UI -->
<a href="/admin/docs/captura-chat#modo-conversacion" target="_blank">📖 Ver manual</a>
```

Al abrir ese link:
- El navegador hace scroll automático a la sección
- El heading se resalta con fondo índigo durante ~2 segundos
- El ícono 🔗 aparece al hover sobre cualquier heading; clic copia la URL completa con anchor

### Enlace desde el manual → página de la app

En el markdown, un link normal:
```markdown
[Ir a /captura](/captura)
[Ver panel admin](/admin)
```

### Cómo copiar un anchor sin saber el id

1. Abrir el manual en el navegador
2. Hacer hover sobre el heading destino
3. Clic en el 🔗 que aparece
4. La URL completa (incluyendo `#anchor`) queda en el portapapeles

*Creado: 2026-03-16 | Última actualización: 2026-03-17 (fix heartbeat contaminado por SendKeys)*
