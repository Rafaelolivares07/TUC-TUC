# Manual de Desarrollo — Asistencia Remota (TUC TUC Remote)

**Módulo:** Asistencia Remota
**Versión:** 1.0
**Última actualización:** 2026-03-14
**Audiencia:** Desarrolladores que mantienen o extienden el módulo

---

## Visión general

El módulo de Asistencia Remota permite que un técnico controle la pantalla de un usuario a través del navegador. La arquitectura es de 3 capas:

```
[Agente - PC del usuario]
        ↕  WebSocket
[Relay - tuc-tuc-remote.onrender.com]
        ↕  WebSocket
[Visor - navegador del técnico]
```

- **Agente** (`agente.py` / `AsistenciaTucTuc.exe`): corre en el PC del usuario. Captura pantalla y la envía. Recibe comandos y los ejecuta.
- **Relay** (`server.py`): servidor Flask + SocketIO desplegado en Render. Solo hace de puente. No procesa ni almacena nada de las pantallas.
- **Visor**: página HTML embebida en `server.py` (`VIEWER_HTML`). El técnico la abre en su navegador.

---

## Archivos del módulo

```
remote-assist/
├── agente.py              ← agente para correr desde Python (desarrollo)
├── agente_cliente.py      ← variante del agente empaquetable (PyInstaller)
├── server.py              ← relay Flask + SocketIO + visor HTML embebido
├── requirements.txt       ← dependencias del servidor (para Render)
├── requirements_agente.txt← dependencias del agente (para build local)
├── render.yaml            ← config de despliegue en Render
├── build_exe.bat          ← script Windows para compilar AsistenciaTucTuc.exe
├── AsistenciaTucTuc.spec  ← spec de PyInstaller (generado en el primer build)
├── build/                 ← archivos intermedios de PyInstaller (ignorar)
└── dist/
    └── AsistenciaTucTuc.exe ← el ejecutable final para distribuir al usuario
```

---

## Agente (`agente.py`)

### Dependencias
```
mss              # captura de pantalla (nativo, multiplataforma)
pyautogui        # control de mouse y teclado
python-socketio[client]  # cliente SocketIO
Pillow           # redimensionado y compresión JPEG
tkinter          # ventana de código (incluido en Python estándar)
```

### Configuración por defecto (constantes en el archivo)

| Constante | Valor | Descripción |
|---|---|---|
| `DEFAULT_SERVER` | `https://tuc-tuc-remote.onrender.com` | URL del relay |
| `DEFAULT_TOKEN` | `tuctuc-remote-2026` | Token de autenticación compartido con el relay |
| `FPS_TARGET` | `8` | Frames por segundo de captura |
| `QUALITY` | `70` | Calidad JPEG (1-95). Menor = más rápido, peor imagen |
| `SCALE` | `0.85` | Factor de escala de pantalla antes de enviar. Reduce ancho de banda |

Estos valores son los predeterminados. Se pueden sobreescribir por argumentos de línea de comandos:
```bash
python agente.py --server URL --token TOKEN --fps 12 --quality 80 --scale 0.9
```

### Flujo de ejecución

```
main()
  ├── Detectar resolución real del monitor principal (mss)
  ├── generar_codigo() → "XXX-XXX" (6 dígitos aleatorios, formato 3-3)
  ├── session_id = codigo sin guion ("XXXXXX")
  ├── mostrar_ventana(codigo) → tkinter en main thread (BLOQUEANTE)
  └── socket_loop() → thread daemon
        ├── sio.connect(server, transports=['websocket'])
        ├── emit('agent_join', {token, session_id})
        └── loop mientras sio.connected:
              ├── capturar_frame() → base64 JPEG
              ├── emit('frame', {session_id, img})
              └── sleep para mantener FPS_TARGET
```

### Captura de pantalla (`capturar_frame`)

1. `mss` captura el monitor principal (`sc.monitors[1]`) en formato BGRX raw
2. Convierte a `PIL.Image` en modo RGB
3. Redimensiona por factor `SCALE` con `Image.LANCZOS`
4. Comprime a JPEG en memoria (no toca disco)
5. Codifica en base64 para envío por SocketIO
6. Retorna `(base64_str, width, height)`

**Por qué JPEG y no PNG:** JPEG con quality=70 produce frames de ~50-100KB. PNG sin comprimir serían 3-10MB. La pérdida de calidad es imperceptible en uso de soporte.

### Control remoto (`ejecutar_comando`)

Recibe un dict `data` con campo `type`. Tipos soportados:

| type | Parámetros | Acción |
|---|---|---|
| `move` | `x`, `y` (0.0-1.0 relativo) | `pyautogui.moveTo()` |
| `click` | `x`, `y`, `button` ('left'/'right') | `pyautogui.click()` |
| `double_click` | `x`, `y` | `pyautogui.doubleClick()` |
| `scroll` | `dy` (int) | `pyautogui.scroll()` |
| `key` | `key` (nombre tecla JS) | `pyautogui.press()` con mapeo de nombres |

Las coordenadas `x` e `y` son **relativas** (0.0 a 1.0). Se multiplican por `screen_w` / `screen_h` (resolución real detectada al iniciar) para obtener coordenadas absolutas en píxeles.

**Teclas especiales:** El mapeo `key_map` convierte nombres de teclas de JavaScript (`Enter`, `Backspace`, `ArrowUp`, etc.) a los nombres que acepta pyautogui. Teclas modificadoras solas (`Control`, `Shift`, `Alt`, `Meta`) no se envían — el visor captura la combinación completa y el mapeo se puede extender en `ejecutar_comando`.

### Código de sesión

```python
def generar_codigo():
    digits = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return digits[:3] + '-' + digits[3:]
```

- Genera 6 dígitos aleatorios → formato `XXX-XXX` para mostrar al usuario
- `session_id` = código sin guion (6 dígitos puros) → es la sala SocketIO
- Cada ejecución del agente genera un código distinto
- No hay persistencia ni base de datos: el código vive mientras el proceso corre

### Reconexión automática

```python
sio = sio_lib.Client(reconnection=True, reconnection_delay=3, reconnection_attempts=0)
```

`reconnection_attempts=0` = intentos infinitos. Si el relay se cae (Render hace cold start en ~30s la primera vez), el agente seguirá intentando hasta que el relay responda.

Si la conexión se pierde pero el proceso sigue vivo, al reconectar emite `agent_join` de nuevo con el mismo `session_id`. El técnico puede reconectarse con el mismo código.

---

## Servidor Relay (`server.py`)

### Stack
- Flask + Flask-SocketIO
- `async_mode='gevent'` (necesario para Render)
- Desplegado en Render, URL: `https://tuc-tuc-remote.onrender.com`

### Autenticación

Un único token compartido (`ACCESS_TOKEN`) valida tanto al agente como al visor. El token está en la variable de entorno `ACCESS_TOKEN` del servicio de Render. Por defecto: `tuctuc-remote-2026`.

**⚠️ Para cambiar el token:** actualizar la variable de entorno en Render Y el valor `DEFAULT_TOKEN` en `agente.py` (y recompilar el `.exe`). Son dos lugares.

### Rooms SocketIO

Por cada sesión `XXX-XXX` existen 3 rooms:

| Room | Miembros | Para qué |
|---|---|---|
| `session_XXXXXX` | agente + visor | room base (no se usa directamente ahora) |
| `agent_XXXXXX` | solo el agente | recibir comandos del visor |
| `viewer_XXXXXX` | solo el visor | recibir frames y notificaciones del agente |

### Eventos SocketIO

**Agente → Relay:**

| Evento | Payload | Acción |
|---|---|---|
| `agent_join` | `{token, session_id}` | Valida token, une a rooms, emite `agent_ready` al agente, `agent_connected` al visor |
| `frame` | `{session_id, img}` | Re-emite al room `viewer_XXXXXX` sin modificar |

**Visor → Relay:**

| Evento | Payload | Acción |
|---|---|---|
| `viewer_join` | `{token, session_id}` | Valida token, une a rooms, emite `viewer_ok` |
| `command` | `{session_id, type, ...}` | Re-emite al room `agent_XXXXXX` |

**Relay → cliente (agente o visor):**

| Evento | Destino | Cuándo |
|---|---|---|
| `agent_ready` | agente | Después de `agent_join` exitoso |
| `agent_error` | agente | Token incorrecto en `agent_join` |
| `viewer_ok` | visor | Después de `viewer_join` exitoso |
| `viewer_error` | visor | Token incorrecto en `viewer_join` |
| `agent_connected` | visor | Cuando el agente hace `agent_join` |
| `agent_disconnected` | visor | Cuando el agente se desconecta (evento `disconnect`) |

### Registro de sesiones activas

```python
active_sessions = {}   # session_id → timestamp de conexión
sid_to_session = {}    # socket.sid → session_id
```

- Se llena en `on_agent_join` y se limpia en `on_disconnect`
- Expuesto por `GET /api/sessions` → `{"sessions": [{"session_id": "...", "ts": 1234}]}`
- El visor consulta este endpoint cada 3 segundos para mostrar sesiones disponibles

### Límite de tamaño de buffer

```python
max_http_buffer_size=8 * 1024 * 1024  # 8MB
```

Un frame JPEG con `SCALE=0.85` y `QUALITY=70` pesa ~50-150KB (depende del contenido de la pantalla). El límite de 8MB da margen amplio incluso si se sube calidad.

### Rutas HTTP

| Ruta | Método | Respuesta |
|---|---|---|
| `/` | GET | Página HTML del visor (embebida en `VIEWER_HTML`) |
| `/health` | GET | `"ok"` — para health checks de Render |
| `/api/sessions` | GET | JSON con sesiones activas |

---

## Visor (página HTML embebida en `server.py`)

La constante `VIEWER_HTML` en `server.py` contiene todo el HTML, CSS y JS del visor. No hay archivos separados.

### Flujo del visor

1. Al cargar, consulta `/api/sessions` y muestra sesiones activas (refresca cada 3s)
2. El técnico ingresa token + código `XXX-XXX`
3. JS emite `viewer_join` → recibe `viewer_ok` → oculta overlay, muestra `<img id="screen">`
4. Cada evento `frame` del relay actualiza el `src` del `<img>` con el nuevo base64 JPEG
5. Mouse y teclado del técnico sobre la imagen disparan eventos que emiten `command` al relay

### Coordenadas relativas

El visor calcula posición relativa dividiendo por las dimensiones del elemento `<img>`:
```javascript
x: (e.clientX - rect.left) / rect.width,
y: (e.clientY - rect.top) / rect.height
```

El agente recibe estas coordenadas relativas y las multiplica por la resolución real de su pantalla. Así el mapeo es correcto sin importar el tamaño de la ventana del técnico ni la resolución del usuario.

### FPS display

El visor cuenta frames recibidos en ventanas de 1 segundo y muestra los fps reales en el header.

---

## Build del ejecutable (`AsistenciaTucTuc.exe`)

### ¿Cuándo recompilar?

Cada vez que se modifique `agente.py` o `agente_cliente.py` **el `.exe` en GitHub Releases debe actualizarse manualmente**. El `.exe` no es parte del repositorio git (solo el código fuente lo es).

### Prerequisitos

- Python 3.10+ en Windows (se recomienda el mismo Python con que correrá el .exe)
- Las dependencias del agente instaladas:
  ```bash
  pip install mss pyautogui Pillow "python-socketio[client]"
  pip install pyinstaller
  ```

### Comando de compilación (desde `remote-assist/`)

Usando `build_exe.bat` (doble clic en Windows):
```bat
pyinstaller --onefile --windowed --name "AsistenciaTucTuc" ^
  --hidden-import=mss ^
  --hidden-import=mss.windows ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=pyautogui ^
  --hidden-import=socketio ^
  --hidden-import=engineio ^
  agente_cliente.py
```

O directamente desde terminal (si `pyinstaller` no está en PATH):
```bash
cd "C:/Users/RAFAEL OLIVARES/Documents/MiAppMedicamentos/remote-assist"
python -m PyInstaller --onefile --noconsole --name AsistenciaTucTuc agente.py
```

**Flags clave:**
- `--onefile`: todo en un solo `.exe` (no carpeta)
- `--windowed` / `--noconsole`: suprime la ventana de consola negra (usa tkinter en su lugar)
- `--hidden-import`: PyInstaller a veces no detecta imports dinámicos de mss/PIL/socketio — hay que declararlos explícitamente

El `.exe` resultante queda en `dist/AsistenciaTucTuc.exe`.

### Subir a GitHub Releases

El `.exe` se distribuye como **asset de GitHub Release** (no como archivo del repo).

1. Ir a: `https://github.com/Rafaelolivares07/TUC-TUC/releases/tag/V1.0`
   *(Ojo: `V1.0` con V mayúscula — así fue creado el tag)*
2. Editar el release → arrastrar/subir el nuevo `dist/AsistenciaTucTuc.exe`
3. Guardar

El enlace de descarga directo es:
`https://github.com/Rafaelolivares07/TUC-TUC/releases/download/V1.0/AsistenciaTucTuc.exe`

Este enlace no cambia aunque se reemplace el archivo en el release.

### Diferencia entre `agente.py` y `agente_cliente.py`

- `agente.py`: versión de desarrollo, se puede correr directamente con Python
- `agente_cliente.py`: variante pensada para empaquetar (puede tener ajustes de paths o imports para que PyInstaller los detecte bien)
- El `build_exe.bat` apunta a `agente_cliente.py`
- Para desarrollo y pruebas rápidas, usar `agente.py` directamente

---

## Despliegue del relay en Render

El servidor relay ya está desplegado. Para referencia, el `render.yaml` define:

```yaml
services:
  - type: web
    name: tuctuc-remote
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python server.py
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: ACCESS_TOKEN
        value: tuctuc-remote-2026
```

**Cold start:** Render en plan gratuito duerme el servicio tras ~15 minutos de inactividad. El primer frame puede tardar 20-30 segundos mientras Render levanta el proceso. El agente reconecta automáticamente. Para evitar cold starts se puede usar un servicio de ping externo (UptimeRobot, etc.) al endpoint `/health`.

**requirements.txt del servidor:**
```
flask
flask-socketio
gevent
gevent-websocket
```

---

## Integración en la UI de TUC TUC

### Pestaña Soporte en `tienda_admin.html`

El tab fue agregado al carrusel de pestañas del panel admin de tienda:

**Botón tab:**
```html
<button onclick="cambiarTab('soporte')" id="tab-soporte" class="tab-btn">🖥️ Soporte</button>
```

**Array de tabs (en `cambiarTab()`):**
```javascript
['catalogo','pedidos','inventario','personalizar','acceso','ubicacion','soporte']
```

**Panel** (`panel-soporte`): muestra el flujo de 3 pasos con enlace de descarga del `.exe` y enlace al visor para técnicos.

### Card en `admin_menu.html`

La card de Asistencia Remota en el panel de admin principal (`/area_admin`) contiene un enlace al visor (`https://tuc-tuc-remote.onrender.com`).

**Bug histórico resuelto (2026-03-14):** La card tenía un `<a>` anidado dentro de otro `<a>` (el botón de descarga del `.exe` era un `<a>` dentro del `<a>` de la card). HTML inválido — Chrome lo "arreglaba" cerrando el `<a>` externo antes de tiempo, lo que creaba una card vacía extra en el grid. **Fix:** reemplazar el `<a>` interior por un `<span onclick="window.open(...)">`  — HTML válido, comportamiento idéntico.

---

## Consideraciones de seguridad

1. **Token único:** El `ACCESS_TOKEN` autentica tanto al agente como al visor. Si se compromete, cualquiera puede ver sesiones activas y conectarse como técnico. Rotar el token implica actualizar Render + recompilar el `.exe`.

2. **Código de sesión temporal:** El código `XXX-XXX` existe solo mientras el proceso del agente está vivo. No se almacena en base de datos. No hay forma de conectarse a una sesión anterior.

3. **Transmisión:** Los frames se transmiten como base64 sobre WebSocket. No hay cifrado adicional a nivel de aplicación (el cifrado TLS del WebSocket es suficiente para uso de soporte interno).

4. **El relay no graba:** El servidor solo reenvía los frames. No los almacena en disco ni en memoria más allá del evento SocketIO.

5. **Control total:** El técnico conectado tiene control completo del mouse y teclado. Solo iniciar una sesión con técnicos de confianza.
