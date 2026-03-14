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

# max_http_buffer_size: frames JPEG pueden pesar hasta ~300KB con SCALE=0.85/QUALITY=70
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    max_http_buffer_size=8 * 1024 * 1024,  # 8MB por frame
    async_mode='gevent',
    ping_timeout=60,
    ping_interval=25,
)

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN', 'tuctuc-remote-2026')

# Registro de sesiones activas (agentes conectados)
# session_id -> timestamp de conexión
active_sessions = {}
# sid -> session_id (para limpiar al desconectar)
sid_to_session = {}

# ─── Páginas ─────────────────────────────────────────────────────────────────

VIEWER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TUC TUC Remote — Técnico</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
  #header { padding: 10px 16px; background: #1e293b; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #334155; }
  #header h1 { font-size: 15px; font-weight: 700; color: #f1f5f9; }
  #status { font-size: 12px; color: #94a3b8; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #475569; margin-right: 5px; }
  .dot.green { background: #22c55e; } .dot.yellow { background: #eab308; } .dot.red { background: #ef4444; }
  #fps { font-size: 11px; color: #64748b; margin-left: auto; }
  #screen-wrap { width: 100%; height: calc(100vh - 44px); overflow: auto; background: #000; display: none; }
  #screen { width: 100%; height: 100%; object-fit: contain; cursor: crosshair; display: block; image-rendering: crisp-edges; }

  #overlay { position: fixed; inset: 0; background: #0f172a; display: flex; align-items: center; justify-content: center; padding: 20px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 32px; width: 100%; max-width: 420px; }
  .card h2 { font-size: 22px; font-weight: 800; color: #f1f5f9; margin-bottom: 4px; }
  .card p { font-size: 13px; color: #64748b; margin-bottom: 24px; }
  .campo { margin-bottom: 14px; }
  .campo label { display: block; font-size: 11px; font-weight: 600; color: #94a3b8; margin-bottom: 5px; letter-spacing: 0.05em; text-transform: uppercase; }
  .campo input { width: 100%; background: #0f172a; border: 1.5px solid #334155; border-radius: 10px; padding: 11px 14px; font-size: 15px; color: #f1f5f9; outline: none; transition: border-color 0.2s; }
  .campo input:focus { border-color: #6366f1; }
  .campo input.code-input { font-family: 'Courier New', monospace; font-size: 22px; font-weight: 700; text-align: center; letter-spacing: 0.15em; color: #22c55e; }
  .btn-conectar { width: 100%; background: #6366f1; color: white; border: none; border-radius: 10px; padding: 13px; font-size: 15px; font-weight: 700; cursor: pointer; transition: background 0.2s; margin-top: 4px; }
  .btn-conectar:hover { background: #4f46e5; }
  #error-msg { color: #f87171; font-size: 12px; margin-top: 8px; min-height: 16px; }

  #sesiones-activas { margin-top: 20px; }
  #sesiones-activas h3 { font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }
  .sesion-item { background: #0f172a; border: 1px solid #1e3a5f; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; transition: border-color 0.15s; }
  .sesion-item:hover { border-color: #6366f1; }
  .sesion-codigo { font-family: 'Courier New', monospace; font-size: 18px; font-weight: 700; color: #22c55e; letter-spacing: 0.1em; }
  .sesion-btn { font-size: 11px; background: #1e3a5f; color: #93c5fd; border: none; border-radius: 6px; padding: 4px 10px; cursor: pointer; }
  .sin-sesiones { font-size: 12px; color: #475569; text-align: center; padding: 12px; }
</style>
</head>
<body>
<div id="header">
  <h1>TUC TUC Remote</h1>
  <span class="dot" id="dot"></span>
  <span id="status">Desconectado</span>
  <span id="fps"></span>
</div>
<div id="screen-wrap">
  <img id="screen" src="" alt="">
</div>

<div id="overlay">
  <div class="card">
    <h2>Conectar a cliente</h2>
    <p>Ingresa el código que el cliente ve en su pantalla</p>

    <div class="campo">
      <label>Token de técnico</label>
      <input id="token-input" type="password" placeholder="••••••••••••" autofocus>
    </div>
    <div class="campo">
      <label>Código del cliente</label>
      <input id="codigo-input" class="code-input" type="text" placeholder="000-000"
             maxlength="7" oninput="formatearCodigo(this)">
    </div>
    <button class="btn-conectar" onclick="conectar()">Conectar</button>
    <div id="error-msg"></div>

    <div id="sesiones-activas">
      <h3>Sesiones activas <span id="sesiones-count" style="color:#475569"></span></h3>
      <div id="lista-sesiones"><div class="sin-sesiones">Cargando...</div></div>
    </div>
  </div>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
let socket, sessionId;
let frameCount = 0, lastFpsTime = Date.now();

function formatearCodigo(input) {
  let v = input.value.replace(/[^0-9]/g, '');
  if (v.length > 3) v = v.slice(0,3) + '-' + v.slice(3,6);
  input.value = v;
}

function seleccionarSesion(codigo) {
  document.getElementById('codigo-input').value = codigo.slice(0,3) + '-' + codigo.slice(3);
}

function conectar() {
  const token = document.getElementById('token-input').value.trim();
  const codigoRaw = document.getElementById('codigo-input').value.replace(/[^0-9]/g, '');
  if (!token) { setError('Ingresa el token de técnico'); return; }
  if (codigoRaw.length !== 6) { setError('Ingresa un código de 6 dígitos'); return; }
  sessionId = codigoRaw;
  setError('');

  socket = io({ transports: ['websocket'] });

  socket.on('connect', () => {
    socket.emit('viewer_join', { token, session_id: sessionId });
  });
  socket.on('viewer_ok', () => {
    document.getElementById('overlay').style.display = 'none';
    document.getElementById('screen-wrap').style.display = 'block';
    setStatus('yellow', 'Esperando agente...');
  });
  socket.on('viewer_error', (d) => { setError(d.msg || 'Token incorrecto'); socket.disconnect(); });
  socket.on('agent_connected', () => setStatus('green', 'Agente conectado — ' + formatCodigo(sessionId)));
  socket.on('agent_disconnected', () => setStatus('yellow', 'Agente desconectado'));
  socket.on('frame', (data) => {
    document.getElementById('screen').src = 'data:image/jpeg;base64,' + data.img;
    frameCount++;
    const now = Date.now();
    if (now - lastFpsTime >= 1000) {
      document.getElementById('fps').textContent = frameCount + ' fps';
      frameCount = 0; lastFpsTime = now;
    }
  });
  socket.on('disconnect', () => setStatus('red', 'Desconectado'));
}

function formatCodigo(c) { return c.slice(0,3) + '-' + c.slice(3); }
function setError(msg) { document.getElementById('error-msg').textContent = msg; }
function setStatus(color, text) {
  document.getElementById('dot').className = 'dot ' + color;
  document.getElementById('status').textContent = text;
}

// Cargar sesiones activas cada 3 segundos
async function cargarSesiones() {
  try {
    const r = await fetch('/api/sessions');
    const d = await r.json();
    const lista = document.getElementById('lista-sesiones');
    const count = document.getElementById('sesiones-count');
    if (!d.sessions || d.sessions.length === 0) {
      lista.innerHTML = '<div class="sin-sesiones">Sin sesiones activas ahora</div>';
      count.textContent = '(0)';
    } else {
      count.textContent = '(' + d.sessions.length + ')';
      lista.innerHTML = d.sessions.map(s => {
        const cod = formatCodigo(s.session_id);
        return '<div class="sesion-item" onclick="seleccionarSesion(\\'' + s.session_id + '\\')">' +
          '<span class="sesion-codigo">' + cod + '</span>' +
          '<button class="sesion-btn">Conectar</button>' +
          '</div>';
      }).join('');
    }
  } catch(e) {}
}
cargarSesiones();
setInterval(cargarSesiones, 3000);

// ─── Comandos al agente ──────────────────────────────────────────────────────
const screenEl = document.getElementById('screen');
screenEl.addEventListener('click', (e) => {
  if (!socket) return;
  const rect = screenEl.getBoundingClientRect();
  socket.emit('command', { session_id: sessionId, type: 'click', x: (e.clientX-rect.left)/rect.width, y: (e.clientY-rect.top)/rect.height, button: 'left' });
});
screenEl.addEventListener('contextmenu', (e) => {
  e.preventDefault(); if (!socket) return;
  const rect = screenEl.getBoundingClientRect();
  socket.emit('command', { session_id: sessionId, type: 'click', x: (e.clientX-rect.left)/rect.width, y: (e.clientY-rect.top)/rect.height, button: 'right' });
});
screenEl.addEventListener('dblclick', (e) => {
  if (!socket) return;
  const rect = screenEl.getBoundingClientRect();
  socket.emit('command', { session_id: sessionId, type: 'double_click', x: (e.clientX-rect.left)/rect.width, y: (e.clientY-rect.top)/rect.height });
});
screenEl.addEventListener('mousemove', (e) => {
  if (!socket) return;
  const rect = screenEl.getBoundingClientRect();
  socket.emit('command', { session_id: sessionId, type: 'move', x: (e.clientX-rect.left)/rect.width, y: (e.clientY-rect.top)/rect.height });
});
screenEl.addEventListener('wheel', (e) => {
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

@app.route('/api/sessions')
def api_sessions():
    from flask import jsonify
    import time
    sesiones = [{'session_id': sid, 'ts': ts} for sid, ts in active_sessions.items()]
    return jsonify({'sessions': sesiones})


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
    import time
    active_sessions[session_id] = time.time()
    sid_to_session[request.sid] = session_id


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
    session_id = sid_to_session.pop(request.sid, None)
    if session_id:
        active_sessions.pop(session_id, None)
        emit('agent_disconnected', room=f'viewer_{session_id}')


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    print(f'RemoteAssist relay corriendo en :{port}')
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
