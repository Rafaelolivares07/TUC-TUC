# Manual de Desarrollo — Asistencia Remota (TUC TUC Remote)

**Módulo:** Asistencia Remota
**Versión:** 1.2
**Última actualización:** 2026-04-01
**Audiencia:** Desarrolladores que mantienen o extienden el módulo

---

## Visión general

El módulo de Asistencia Remota permite que un técnico controle la pantalla de un usuario a través del navegador, transfiera archivos, y ejecute comandos remotamente. La arquitectura es de 3 capas:

```
[Agente - PC del usuario]
        ↕  WebSocket
[Relay - tuc-tuc-remote.onrender.com]
        ↕  WebSocket
[Visor - navegador del técnico]
```

- **Agente** (`agente_cliente.py` / `AsistenciaTucTuc.exe`): corre en el PC del usuario. Captura pantalla, recibe comandos, ejecuta comandos shell, transfiere archivos.
- **Relay** (`server.py`): servidor Flask + SocketIO en Render. Solo hace de puente.
- **Visor**: página HTML embebida en `server.py`. El técnico la abre en el navegador.
- **merlin_remote.py**: cliente Python que conecta al relay como visor y expone una API local en `:7777` para que Merlin (IA) opere remotamente.

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

C:\S.A.R\
└── merlin_remote.py       ← puente Merlin ↔ relay (API local :7777)
```

---

## Agente (`agente_cliente.py`)

### Dependencias
```
mss              # captura de pantalla
pyautogui        # control de mouse y teclado
python-socketio[client]
Pillow
tkinter          # incluido en Python estándar
zipfile          # incluido en Python estándar
subprocess       # incluido en Python estándar
```

### Configuración por defecto

| Constante | Valor | Descripción |
|---|---|---|
| `SERVER` | `https://tuc-tuc-remote.onrender.com` | URL del relay |
| `TOKEN` | `tuctuc-remote-2026` | Token de autenticación |
| `SESSION` | `random.randint(100000,999999)` | Código aleatorio por sesión |
| `FPS` | `8` | Frames por segundo |
| `QUALITY` | `70` | Calidad JPEG |
| `SCALE` | `0.85` | Factor de escala |

### Comandos soportados (evento `command`)

| type | Parámetros | Acción |
|---|---|---|
| `move` | `x`, `y` (0.0-1.0) | Mover mouse |
| `click` | `x`, `y`, `button` | Clic |
| `double_click` | `x`, `y` | Doble clic |
| `scroll` | `dy` | Rueda |
| `key` | `key` | Tecla |

### Transferencia de archivos — chunks (512KB)

**Recibir archivo del técnico (`file_chunk_in`):**
- El visor divide el archivo en chunks de 512KB y los envía con `{nombre, idx, total, b64}`
- El agente ensambla los chunks en memoria y guarda el archivo completo en `Desktop\`
- Muestra progreso en la ventana tkinter

**Enviar archivo/carpeta al técnico (`file_request`):**
- El visor envía `{ruta}` — puede ser archivo o carpeta
- Si es carpeta: el agente la zipea en memoria con `zipfile.ZipFile`
- Divide el contenido en chunks de 512KB y emite `file_chunk` con cada uno
- El visor ensambla y descarga automáticamente
- Corre en thread separado para no bloquear los frames

### Terminal remota (`exec`)

```python
@sio.on('exec')
def on_exec(data):
    cmd = data.get('cmd', '')
    subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    sio.emit('exec_result', {'session_id': SESSION, 'output': output})
```

- Timeout: 60 segundos
- Corre en thread daemon para no bloquear
- Captura stdout + stderr
- Si el comando no produce output, devuelve el código de salida

---

## Servidor Relay (`server.py`)

### Buffer
```python
max_http_buffer_size=50 * 1024 * 1024  # 50MB — soporta chunks de archivos
```

### Eventos SocketIO completos

**Visor → Relay → Agente:**

| Evento | Descripción |
|---|---|
| `viewer_join` | Autenticar visor |
| `command` | Mouse/teclado |
| `file_chunk_in` | Chunk de archivo enviado al cliente |
| `file_request` | Pedir archivo/carpeta del cliente |
| `exec` | Ejecutar comando en PC del cliente |

**Agente → Relay → Visor:**

| Evento | Descripción |
|---|---|
| `agent_join` | Autenticar agente |
| `frame` | Frame de pantalla (base64 JPEG) |
| `file_chunk` | Chunk de archivo del cliente al técnico |
| `exec_result` | Output del comando ejecutado |

### Visor — paneles adicionales (V1.1+)

**Panel Archivos (`📁 Archivos`):**
- Sección "Enviar archivo al cliente": `input file` → chunks → Desktop del agente
- Sección "Pedir archivo del cliente": input de ruta → agente zipea si es carpeta → descarga en navegador

**Panel Terminal (`⌨️ Terminal`):**
- Input de comando con historial (↑↓)
- Output en verde sobre fondo negro
- Muestra `❯ comando` y resultado
- Enter para ejecutar

---

## merlin_remote.py (`C:\S.A.R\`)

Script que conecta al relay como visor y expone API REST local para que Merlin (IA) opere remotamente desde esta terminal.

### Uso
```bash
python C:\S.A.R\merlin_remote.py <codigo_sesion>
# Ejemplo:
python C:\S.A.R\merlin_remote.py 847293
```

### API local (`http://localhost:7777`)

| Endpoint | Método | Body | Descripción |
|---|---|---|---|
| `/estado` | GET | — | Estado de conexión |
| `/pantalla` | GET | — | Guarda screenshot en `%TEMP%\merlin_screen.jpg`, retorna path |
| `/exec` | POST | `{"cmd": "..."}` | Ejecuta comando, retorna output |
| `/click` | POST | `{"x": 0.5, "y": 0.5, "button": "left"}` | Clic (coords 0.0-1.0) |
| `/doble_click` | POST | `{"x", "y"}` | Doble clic |
| `/mover` | POST | `{"x", "y"}` | Mover mouse |
| `/tecla` | POST | `{"key": "enter"}` | Presionar tecla |
| `/escribir` | POST | `{"texto": "hola"}` | Escribir texto |
| `/scroll` | POST | `{"dy": 3}` | Scroll |

### Flujo Merlin opera PC remota

1. Pilar abre `AsistenciaTucTuc.exe` → aparece código ej. `847-293`
2. Rafael le dice a Merlin: "conéctate a 847293"
3. Merlin corre: `python C:\S.A.R\merlin_remote.py 847293` en background
4. Merlin llama `/pantalla` → lee la imagen con visión → ve la pantalla de Pilar
5. Merlin llama `/exec`, `/click`, `/escribir` para operar
6. Rafael puede conectarse al mismo tiempo desde el visor web y ver todo en vivo

---

## Build del ejecutable

### Comando (desde `remote-assist/`)
```bash
python -m PyInstaller --onefile --windowed --name "AsistenciaTucTuc" \
  --hidden-import=mss --hidden-import=mss.windows \
  --hidden-import=PIL --hidden-import=PIL.Image \
  --hidden-import=pyautogui --hidden-import=socketio \
  --hidden-import=engineio agente_cliente.py
```

### Publicar release en GitHub
```bash
'C:\Program Files\GitHub CLI\gh.exe' release create V1.X \
  'remote-assist/dist/AsistenciaTucTuc.exe' \
  --title "V1.X — descripcion" --notes "..."
```

La URL de descarga `releases/latest/download/AsistenciaTucTuc.exe` siempre apunta al release más reciente — no hay que actualizar templates.

### Historial de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| V1.0 | 2026-03-14 | Control remoto básico (pantalla + mouse/teclado) |
| V1.1 | 2026-04-01 | Transferencia de archivos y carpetas por chunks, terminal remota |
| V1.2 | 2026-04-01 | Código de sesión aleatorio visible en la ventana del agente |

---

## Despliegue del relay en Render

- URL: `https://tuc-tuc-remote.onrender.com`
- Autodespliega en cada push a `main` que toque archivos en `remote-assist/`
- Cold start: ~20-30s en plan gratuito
- Buffer: 50MB (aumentado en V1.1 para soportar transferencia de archivos)

**requirements.txt del servidor:**
```
flask
flask-socketio
gevent
gevent-websocket
```

---

## Consideraciones de seguridad

1. **Token único** autentica agente y visor — rotar implica actualizar Render + recompilar exe
2. **Terminal remota** (`exec`) da acceso shell completo — solo usar con clientes de confianza
3. **merlin_remote.py** expone API en localhost:7777 sin autenticación — solo correr cuando se necesite
4. El relay no graba frames ni comandos
5. El código de sesión es temporal — muere al cerrar el exe
