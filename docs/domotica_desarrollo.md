# Manual de Desarrollo — Domótica (TUC TUC Smart Home)

**Módulo:** Domótica
**Versión:** 1.2
**Última actualización:** 2026-03-17
**Audiencia:** Desarrolladores que mantienen o extienden el módulo

---

## Arquitectura general

```
[Monitor laptop]          [Propietario / Admin]
      ↓                          ↓
POST /api/domotica/heartbeat   GET /domotica?pid=X
      ↓                          ↓
[Flask + APScheduler]  ←→  [PostgreSQL]
      ↓
POST Tuya Cloud API → switch on/off
```

**Capas:**
1. **Capa 1 (monitor)**: script Python en la laptop del usuario → reporta batería solar e idle cada 60s
2. **Capa 2 (scheduler)**: APScheduler en el servidor → evalúa reglas cada minuto
3. **Capa 3 (Tuya)**: llamadas a la API cloud de Tuya para controlar switches

---

## Tablas principales

```sql
smart_dispositivos (
    id SERIAL PRIMARY KEY,
    id_propiedad INTEGER REFERENCES propiedades(id),
    nombre TEXT NOT NULL,
    tipo TEXT,             -- 'otro', 'enchufe', 'lampara', etc.
    descripcion TEXT,
    mac_address TEXT,
    device_token TEXT,     -- token para autenticación del monitor
    version TEXT
)

smart_switches (
    id SERIAL PRIMARY KEY,
    id_dispositivo INTEGER REFERENCES smart_dispositivos(id),
    nombre TEXT NOT NULL,
    tuya_device_id TEXT,   -- ID del dispositivo en la nube Tuya
    estado_actual BOOLEAN DEFAULT FALSE,
    imagen TEXT,           -- URL del ícono PNG
    mostrar_nombre BOOLEAN DEFAULT TRUE,
    ultima_accion TIMESTAMP,
    apagar_en TIMESTAMP    -- para temporizador programado
)

smart_automatizaciones (
    id SERIAL PRIMARY KEY,
    id_switch INTEGER REFERENCES smart_switches(id),
    descripcion TEXT,
    hora_inicio INTEGER,   -- hora inicio franja solar (0-23)
    hora_fin INTEGER,
    bat_minimo_pico INTEGER,       -- %SOC mínimo para encender en franja pico
    bat_minimo_fuera_pico INTEGER, -- %SOC mínimo fuera de franja
    bat_objetivo INTEGER,          -- %SOC objetivo (deja de cargar)
    activa BOOLEAN DEFAULT TRUE
)

smart_programaciones (
    id SERIAL PRIMARY KEY,
    id_switch INTEGER REFERENCES smart_switches(id),
    hora INTEGER,          -- 0-23
    minuto INTEGER,        -- 0-59
    dias TEXT,             -- '0,1,2,3,4,5,6' (domingo=0)
    accion TEXT,           -- 'encender' | 'apagar'
    activa BOOLEAN DEFAULT TRUE
)

-- En CONFIGURACION_SISTEMA:
presencia_inactividad_seg INTEGER DEFAULT 300
presencia_ventana_seg INTEGER DEFAULT 360
laptop_last_seen TIMESTAMP   -- NULL = ausente
laptop_bat_pct INTEGER
laptop_charging BOOLEAN
pc_comando VARCHAR(20)       -- NULL | 'shutdown' — se limpia tras leer
```

---

## Control Tuya (`_dom_controlar_tuya`)

```python
def _dom_controlar_tuya(tuya_device_id, estado):
    """Envía comando on/off al dispositivo Tuya via cloud API."""
    # 1. Genera token HMAC-SHA256 con TUYA_CLIENT_ID + timestamp
    # 2. POST https://openapi.tuyaeu.com/v1.0/iot-03/devices/{id}/commands
    # 3. Payload: {"commands": [{"code": "switch_1", "value": True/False}]}
    # Retorna True/False según éxito
```

Credenciales en variables de entorno de Render:
- `TUYA_CLIENT_ID`
- `TUYA_CLIENT_SECRET`

---

## Sistema de presencia/ausencia

### Heartbeat (`GET /api/domotica/heartbeat`)

**Emisor único**: `captura_watcher.ps1` — envía cada 60s con idle protegido contra contaminación.

```
GET /api/domotica/heartbeat?token=tuctuc-hb-2026&idle=<segundos>
```

Lógica del servidor:
```python
ventana = config['presencia_ventana_seg']  # de CONFIGURACION_SISTEMA (default 360s)

if idle_seg < ventana:
    laptop_last_seen = NOW()   # activo
else:
    laptop_last_seen = NULL    # ausente

threading.Thread(target=evaluar_reglas_domotica, daemon=True).start()

# Leer y limpiar comando pendiente para el PC
cfg2 = conn.execute("SELECT pc_comando FROM CONFIGURACION_SISTEMA WHERE id=1").fetchone()
pc_cmd = cfg2['pc_comando'] if cfg2 else None
if pc_cmd:
    conn.execute("UPDATE CONFIGURACION_SISTEMA SET pc_comando = NULL WHERE id=1")
    conn.commit()
```

**Respuesta incluye `comando` si hay uno pendiente:**
```json
{ "ok": true, "activo": true, "idle": 120, "comando": "shutdown" }
```
El cliente (`captura_watcher.ps1`) verifica `$resp.comando -eq "shutdown"` y ejecuta el shutdown local.

El scheduler evalúa `laptop_last_seen IS NULL` para determinar ausencia.
El heartbeat también dispara la evaluación inmediatamente en un thread.

### Problema crítico resuelto: contaminación del idle por SendKeys (2026-03-17)

`captura_watcher.ps1` usa `SendKeys(".")` para activar la terminal de Claude Code cuando llega
un mensaje del chat web. Esto reseteaba el idle de Windows. El watcher, 10s después, leía
`windowsIdle < 30s` y actualizaba `$lastRealInput`, haciendo que `$realIdleSec` cayera a ~0,
por lo que el heartbeat siempre reportaba presencia aunque el usuario estuviera ausente.

**Fix**: variable `$lastSendKeys` + `$SENDKEYS_COOLDOWN = 90s`. El watcher no actualiza
`$lastRealInput` si `SendKeys` disparó hace menos de 90s.

### Comportamiento al apagar el PC
- Heartbeat deja de llegar → `laptop_last_seen` queda congelado
- Scheduler detecta vencimiento en el próximo ciclo (~5 min) cuando `laptop_last_seen` tiene > 6 min
- Ventilador se apaga en máximo **~11 minutos** tras apagar el PC

### Evaluación de reglas (`evaluar_reglas_domotica`)

Se ejecuta:
- Cada minuto por APScheduler
- En el mismo hilo del heartbeat cuando `idle_seg >= ventana` (respuesta inmediata)

Evalúa:
1. Reglas de presencia: si `laptop_last_seen IS NULL` → disparar reglas `presencia=ausente`
2. Programaciones: por hora/minuto/día
3. Temporizadores: si `apagar_en <= NOW()` → apagar switch

---

## Control de acceso — helpers (desde 2026-03-14)

Se agregaron 5 funciones helper para que propietarios (terceros) puedan acceder a su propia domótica:

```python
def _dom_es_admin():
    return session.get('rol') == 'Administrador'

def _dom_check_pid(conn, pid):
    """Verifica que session['usuario_id'] sea id_tercero_propietario de la propiedad."""

def _dom_check_did(conn, did):
    """Traza: dispositivo → propiedad → propietario."""

def _dom_check_sid(conn, sid):
    """Traza: switch → dispositivo → propiedad → propietario."""

def _dom_check_aid(conn, aid):
    """Traza: automatización → switch → dispositivo → propiedad → propietario."""

def _dom_check_sched(conn, sched_id):
    """Traza: programación → switch → dispositivo → propiedad → propietario."""
```

**Patrón en cada endpoint:**
```python
@app.route('/api/domotica/switch/<int:sid>/toggle', methods=['POST'])
def api_domotica_switch_toggle(sid):
    if not _dom_es_admin() and not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'Sin acceso'}), 403
    # ...
    conn = get_db_connection()
    if not _dom_check_sid(conn, sid):
        conn.close()
        return jsonify({'ok': False, 'error': 'Sin acceso'}), 403
    # ...
```

### Flujo de autenticación propietario

1. Propietario hace login en `/mis-propiedades` con su teléfono → `session['usuario_id']` = `terceros.id`
2. Abre `/domotica?pid=<id>` desde la card de su propiedad
3. `api_domotica_propiedades` filtra con `WHERE id_tercero_propietario = session['usuario_id']`
4. Solo ve sus propias propiedades; las APIs rechazan acceso a recursos de otras propiedades con 403

**Nota**: `/domotica` y `/api/domotica` están en `rutas_publicas` (el `before_request` no los bloquea), pero cada endpoint hace su propio guard interno.

---

## Acceso desde `/mis-propiedades`

La card de cada propiedad tiene un botón:
```html
<a href="/domotica?pid=${p.id}" target="_blank">💡 Domótica</a>
```

En `domotica.html`, `cargarPropiedades()` lee el parámetro `?pid=` con prioridad sobre `localStorage`:
```javascript
const urlPid = new URLSearchParams(window.location.search).get('pid');
if (urlPid && sel.querySelector(`option[value="${urlPid}"]`)) {
    sel.value = urlPid;
}
```

---

## Monitor de batería (Capa 1)

**Archivo:** `%APPDATA%\TucTuc\monitor_<token>.py`
**Launcher:** VBS en Startup de Windows + Task Scheduler (con `-WindowStyle Hidden`)
**Instalación:** descarga automática desde `GET /api/domotica/dispositivo/<did>/setup-bat` (genera .bat autoinstalable)

El monitor reporta cada 5 minutos (o según configure el scheduler):
- `bat`: porcentaje batería laptop
- `charging`: si está conectado a corriente
- `idle`: segundos sin actividad de teclado/mouse (via `GetLastInputInfo` en Windows)

**Actualización automática**: el monitor compara `version` local vs la del servidor. Si hay nueva versión, descarga el script actualizado desde `/api/domotica/dispositivo/<did>/script?token=<token>`.

---

## Ícono de switches — generación con ChatGPT

El panel admin muestra un botón para generar el ícono PNG de cada switch via ChatGPT/DALL-E:

**Prompt generado programáticamente:**
- `conTexto=true`: 65% ilustración + 35% nombre, SIN fondo/banda detrás del texto, fondo transparente
- `conTexto=false`: solo ilustración, sin texto
- Paleta: dark=blanco/gris claro, light=negro/gris oscuro

**Flujo:** botón copia el prompt al portapapeles → abre ChatGPT → `visibilitychange` detecta regreso → banner "¿Ya tienes la imagen?" → user la sube vía file input.

---

## Reglas de diseño UI — OBLIGATORIAS

Ver `feedback_ui_domotica.md` en memoria para el historial completo. Resumen:

- **NO usar 2 columnas** en la grilla de switches (rechazado 2 veces). Siempre `flex-col`, 1 columna, full-width.
- `.ctrl-icon { height: min(60vw, 220px) }` — ícono llena la card
- `.ctrl-nombre { font-size: .75rem; padding: 4px 8px 6px }` — título pequeño abajo
- Modal de detalle: `max-w-full` en ambas capas para no salirse en mobile

---

## Endpoints clave

| Ruta | Método | Auth | Descripción |
|---|---|---|---|
| `/api/domotica/propiedades` | GET | admin o propietario | Lista propiedades con count de dispositivos |
| `/api/domotica/propiedad/<pid>/dispositivos` | GET | admin o propietario | Dispositivos + switches + automatizaciones + programaciones |
| `/api/domotica/switch/<sid>/toggle` | POST | admin o propietario | Encender/apagar via Tuya |
| `/api/domotica/switch/<sid>/temporizador` | POST | admin o propietario | Encender N minutos |
| `/api/domotica/heartbeat` | GET | token dispositivo | Reporte idle → detecta presencia; retorna comando pendiente (ej. `shutdown`) |
| `/api/domotica/pc/apagar` | POST | admin | Escribe `pc_comando='shutdown'` en BD; el watcher lo ejecuta en el próximo ciclo |
| `/api/domotica/config/presencia` | POST | admin | Guardar ventana de inactividad en minutos |
| `/api/domotica/dispositivo/<did>/setup-bat` | GET | admin o propietario | Descarga .bat auto-instalable del monitor |

### Flujo "Apagar PC"

```
[Celular /domotica]
    POST /api/domotica/pc/apagar
        → UPDATE CONFIGURACION_SISTEMA SET pc_comando='shutdown'
    ↓ (hasta 60s después)
[captura_watcher.ps1]
    GET /api/domotica/heartbeat?...
        ← { "ok": true, "comando": "shutdown" }
        → START shutdown.exe /s /f /t 15
    ↓ (15s después)
[PC apagado]
```

**Columna `pc_comando`**: se limpia inmediatamente al leerla en el heartbeat (un solo disparo, no reintentable). Se crea con `ALTER TABLE CONFIGURACION_SISTEMA ADD COLUMN IF NOT EXISTS pc_comando VARCHAR(20)` en `crear_tablas_domotica`.

---

## Notas críticas

1. **Tuya region**: usar `openapi.tuyaeu.com` (Europa), no `openapi.tuyaus.com` — los dispositivos comprados en AliExpress suelen estar en región EU.
2. **Bluetooth puro sin gateway**: el MOES BAT-80A ATS es Bluetooth — nunca aparece online en la Cloud API. No intentar integrarlo sin un gateway WiFi/Zigbee.
3. **APScheduler en Render**: Render free tier duerme si no hay requests. El heartbeat del monitor (cada 60s) mantiene el servidor despierto. Si el monitor no corre, Render puede dormir y el scheduler no evaluará reglas.
4. **Timestamps en PostgreSQL**: siempre serializar con `.replace(tzinfo=timezone.utc).isoformat()` en Python y `fmtTs(str)` en JS (agrega `Z` antes de `new Date()`). Sin esto, JS interpreta la hora como local en vez de UTC y muestra 5h de desfase.
