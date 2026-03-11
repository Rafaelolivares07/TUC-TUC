"""
RemoteAssist — Servidor relay
- El agente (PC controlado) se conecta y envía frames + recibe comandos
- El visor (navegador del técnico) recibe frames + envía comandos
- El servidor solo hace de puente, no procesa nada
"""

import os
from flask import Flask, render_template_string, request, abort
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cambiar-en-produccion')

# max_http_buffer_size: frames JPEG pueden pesar ~50-80KB
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    max_http_buffer_size=2 * 1024 * 1024,  # 2MB por frame
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
)

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN', 'tuctuc-remote-2026')

# ─── Páginas ─────────────────────────────────────────────────────────────────

VIEWER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TUC TUC Remote</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #111; color: #eee; font-family: monospace; }
  #header { padding: 10px 16px; background: #1a1a1a; display: flex; align-items: center; gap: 12px; }
  #status { font-size: 13px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #555; margin-right: 6px; }
  .dot.green { background: #22c55e; }
  .dot.yellow { background: #eab308; }
  .dot.red { background: #ef4444; }
  #screen-wrap { width: 100%; height: calc(100vh - 44px); display: flex; align-items: center; justify-content: center; overflow: hidden; }
  #screen { max-width: 100%; max-height: 100%; cursor: crosshair; display: block; }
  #overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; }
  #overlay input { padding: 10px 16px; font-size: 16px; border-radius: 6px; border: 1px solid #555; background: #222; color: #eee; width: 280px; }
  #overlay button { padding: 10px 32px; font-size: 16px; border-radius: 6px; border: none; background: #2563eb; color: white; cursor: pointer; }
  #overlay button:hover { background: #1d4ed8; }
  #fps { font-size: 12px; color: #888; }
</style>
</head>
<body>
<div id="header">
  <span class="dot" id="dot"></span>
  <span id="status">Desconectado</span>
  <span id="fps"></span>
</div>
<div id="screen-wrap">
  <img id="screen" src="" alt="">
</div>

<div id="overlay">
  <div style="font-size:20px; font-weight:bold;">TUC TUC Remote</div>
  <input id="token-input" type="password" placeholder="Token de acceso" autofocus>
  <input id="session-input" type="text" placeholder="ID de sesión (del agente)" value="default">
  <button onclick="conectar()">Conectar</button>
  <div id="error" style="color:#ef4444; font-size:13px;"></div>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
let socket, sessionId;
let frameCount = 0, lastFpsTime = Date.now();

function conectar() {
  const token = document.getElementById('token-input').value.trim();
  sessionId = document.getElementById('session-input').value.trim() || 'default';
  if (!token) { document.getElementById('error').textContent = 'Ingresa el token'; return; }

  socket = io({ transports: ['websocket'] });

  socket.on('connect', () => {
    socket.emit('viewer_join', { token, session_id: sessionId });
  });

  socket.on('viewer_ok', () => {
    document.getElementById('overlay').style.display = 'none';
    setStatus('yellow', 'Esperando agente...');
  });

  socket.on('viewer_error', (d) => {
    document.getElementById('error').textContent = d.msg || 'Error';
  });

  socket.on('agent_connected', () => setStatus('green', 'Agente conectado'));
  socket.on('agent_disconnected', () => setStatus('yellow', 'Agente desconectado'));

  socket.on('frame', (data) => {
    document.getElementById('screen').src = 'data:image/jpeg;base64,' + data.img;
    frameCount++;
    const now = Date.now();
    if (now - lastFpsTime >= 1000) {
      document.getElementById('fps').textContent = frameCount + ' fps';
      frameCount = 0;
      lastFpsTime = now;
    }
  });

  socket.on('disconnect', () => setStatus('red', 'Desconectado'));
}

function setStatus(color, text) {
  document.getElementById('dot').className = 'dot ' + color;
  document.getElementById('status').textContent = text;
}

// ─── Enviar comandos al agente ───────────────────────────────────────────────
const screen = document.getElementById('screen');

screen.addEventListener('click', (e) => {
  if (!socket) return;
  const rect = screen.getBoundingClientRect();
  const rx = (e.clientX - rect.left) / rect.width;
  const ry = (e.clientY - rect.top) / rect.height;
  socket.emit('command', { session_id: sessionId, type: 'click', x: rx, y: ry, button: 'left' });
});

screen.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  if (!socket) return;
  const rect = screen.getBoundingClientRect();
  const rx = (e.clientX - rect.left) / rect.width;
  const ry = (e.clientY - rect.top) / rect.height;
  socket.emit('command', { session_id: sessionId, type: 'click', x: rx, y: ry, button: 'right' });
});

screen.addEventListener('dblclick', (e) => {
  if (!socket) return;
  const rect = screen.getBoundingClientRect();
  const rx = (e.clientX - rect.left) / rect.width;
  const ry = (e.clientY - rect.top) / rect.height;
  socket.emit('command', { session_id: sessionId, type: 'double_click', x: rx, y: ry });
});

screen.addEventListener('mousemove', (e) => {
  if (!socket) return;
  const rect = screen.getBoundingClientRect();
  const rx = (e.clientX - rect.left) / rect.width;
  const ry = (e.clientY - rect.top) / rect.height;
  socket.emit('command', { session_id: sessionId, type: 'move', x: rx, y: ry });
});

screen.addEventListener('wheel', (e) => {
  if (!socket) return;
  socket.emit('command', { session_id: sessionId, type: 'scroll', dy: e.deltaY > 0 ? -3 : 3 });
});

document.addEventListener('keydown', (e) => {
  if (!socket || document.getElementById('overlay').style.display !== 'none') return;
  e.preventDefault();
  socket.emit('command', { session_id: sessionId, type: 'key', key: e.key });
});
</script>
</body>
</html>"""


# ─── Rutas HTTP ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(VIEWER_HTML)

@app.route('/health')
def health():
    return 'ok'


# ─── SocketIO — Visor ────────────────────────────────────────────────────────

@socketio.on('viewer_join')
def on_viewer_join(data):
    token = data.get('token', '')
    session_id = data.get('session_id', 'default')
    if token != ACCESS_TOKEN:
        emit('viewer_error', {'msg': 'Token incorrecto'})
        return
    join_room(f'viewer_{session_id}')
    join_room(f'session_{session_id}')
    emit('viewer_ok')
    print(f'[visor] conectado → sesión {session_id}')


# ─── SocketIO — Agente ───────────────────────────────────────────────────────

@socketio.on('agent_join')
def on_agent_join(data):
    token = data.get('token', '')
    session_id = data.get('session_id', 'default')
    if token != ACCESS_TOKEN:
        emit('agent_error', {'msg': 'Token incorrecto'})
        return
    join_room(f'agent_{session_id}')
    join_room(f'session_{session_id}')
    emit('agent_ready')
    # Avisar al visor que el agente llegó
    emit('agent_connected', room=f'viewer_{session_id}')
    print(f'[agente] conectado → sesión {session_id}')


@socketio.on('frame')
def on_frame(data):
    session_id = data.get('session_id', 'default')
    emit('frame', data, room=f'viewer_{session_id}')


@socketio.on('command')
def on_command(data):
    session_id = data.get('session_id', 'default')
    emit('command', data, room=f'agent_{session_id}')


@socketio.on('disconnect')
def on_disconnect():
    print(f'[disconnect] sid={request.sid}')


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    print(f'RemoteAssist relay corriendo en :{port}')
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
