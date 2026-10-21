import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chat_v3.html')
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update CSS to include slider-toggle and active styles
css_target = ".tonos-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }"
css_replacement = """.tonos-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .slider-toggle {
      position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
      background-color: #cbd5e1; transition: .25s; border-radius: 24px;
    }
    .slider-toggle:before {
      position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px;
      background-color: white; transition: .25s; border-radius: 50%;
    }
    input:checked + .slider-toggle { background-color: var(--accent, #e8856a); }
    input:checked + .slider-toggle:before { transform: translateX(20px); }
    .tono-btn.activo, .tono-btn.active-item {
      background: var(--accent-soft, rgba(232,133,106,0.12)) !important;
      border-color: var(--accent, #e8856a) !important;
      color: var(--accent, #e8856a) !important;
      font-weight: 600 !important;
    }"""

if css_target in text:
    text = text.replace(css_target, css_replacement, 1)
    print("CSS replaced successfully!")
else:
    print("Warning: css_target not found!")

# 2. Update modal-perfil content
modal_target = """    <div style="padding:16px 22px 12px">
      <p class="sheet-eyebrow">Tono de notificación</p>
      <div class="tonos-grid">
        <button id="tono-btn-clasico"  onclick="seleccionarTono('clasico')"  class="tono-btn">🔔 Clásico</button>
        <button id="tono-btn-suave"    onclick="seleccionarTono('suave')"    class="tono-btn">🎵 Suave</button>
        <button id="tono-btn-alegre"   onclick="seleccionarTono('alegre')"   class="tono-btn">✨ Alegre</button>
        <button id="tono-btn-pop"      onclick="seleccionarTono('pop')"      class="tono-btn">⚡ Pop</button>
      </div>
      <div style="display:flex;align-items:center;gap:10px;margin-top:8px">
        <button id="tono-btn-personalizado"
                onclick="document.getElementById('inp-tono-file').click()"
                class="tono-btn">📁 Personalizado</button>
        <span id="tono-custom-label"
              style="font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1"></span>
        <input id="inp-tono-file" type="file" accept="audio/*" style="display:none" onchange="cargarTonoPersonalizado(this)">
      </div>
      <p style="font-size:11px;color:var(--muted);margin-top:10px">Toca cada tono para previsualizarlo.</p>
    </div>"""

modal_replacement = """    <div style="padding:16px 22px 14px">
      <!-- Toggle Silencio / Sonar -->
      <div style="display:flex;align-items:center;justify-content:space-between;padding-bottom:12px;border-bottom:1px solid var(--hairline)">
        <div>
          <div style="font-weight:600;font-size:14px;color:var(--ink)">🔔 Sonido de mensajes</div>
          <div style="font-size:11px;color:var(--muted)">Sonar fuerte al recibir un nuevo mensaje</div>
        </div>
        <label style="position:relative;display:inline-block;width:44px;height:24px;cursor:pointer;flex-shrink:0">
          <input type="checkbox" id="chk-chat-sonido" checked onchange="toggleSonidoHabilitado(this.checked)" style="opacity:0;width:0;height:0">
          <span class="slider-toggle"></span>
        </label>
      </div>

      <!-- Selector de Tonos -->
      <div id="seccion-tonos" style="margin-top:14px">
        <p class="sheet-eyebrow" style="margin-bottom:8px">Tono de timbre</p>
        <div class="tonos-grid">
          <button data-tono="0" onclick="seleccionarTono(0)" class="tono-btn">🔔 Campanilla</button>
          <button data-tono="1" onclick="seleccionarTono(1)" class="tono-btn">⚡ Triple</button>
          <button data-tono="2" onclick="seleccionarTono(2)" class="tono-btn">🔊 Grave</button>
          <button data-tono="3" onclick="seleccionarTono(3)" class="tono-btn">✨ Pop doble</button>
          <button data-tono="4" onclick="seleccionarTono(4)" class="tono-btn">🎵 Melodía</button>
          <button data-tono="5" id="tono-btn-personalizado" onclick="document.getElementById('inp-tono-file').click()" class="tono-btn">📁 Subir audio</button>
        </div>
        <div id="tono-custom-container" style="display:none;align-items:center;gap:8px;margin-top:8px">
          <span style="font-size:11px;color:var(--accent);font-weight:600">Audio propio:</span>
          <span id="tono-custom-label" style="font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1"></span>
        </div>
        <input id="inp-tono-file" type="file" accept="audio/*" style="display:none" onchange="cargarTonoPersonalizado(this)">
        <p style="font-size:11px;color:var(--muted);margin-top:8px">Toca un tono para escucharlo y seleccionarlo.</p>
      </div>

      <!-- Web Push Nativo VAPID en segundo plano -->
      <div style="margin-top:16px;padding:12px 14px;background:var(--surface2);border-radius:14px;border:1px solid var(--hairline)">
        <div style="display:flex;align-items:flex-start;gap:10px">
          <span style="font-size:20px;line-height:1">📲</span>
          <div style="flex:1;min-width:0">
            <div style="font-weight:700;font-size:13px;color:var(--ink)">Alertas con la app cerrada</div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;line-height:1.35">
              Web Push nativo: te avisará y sonará tu celular o PC incluso si tienes todo cerrado.
            </div>
            <div id="push-status-label" style="font-size:11px;font-weight:600;margin-top:5px;color:var(--muted)">Comprobando estado...</div>
          </div>
        </div>
        <button id="btn-activar-push" onclick="activarWebPush()"
                style="width:100%;margin-top:10px;padding:9px 12px;border-radius:10px;font-size:12.5px;font-weight:600;background:var(--accent);color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px">
          <span id="btn-activar-push-txt">Activar alertas con app cerrada</span>
        </button>
      </div>
    </div>"""

if modal_target in text:
    text = text.replace(modal_target, modal_replacement, 1)
    print("Modal replaced successfully!")
else:
    print("Warning: modal_target not found!")

# 3. Update Audio & Push scripts at bottom of chat_v3.html
js_target = """function tocarTono(idx) {
  const i = (idx !== undefined ? idx : _tonoSeleccionado);
  try {
    const ctx = _ctx();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
    if (i === 5 && _tonoPersonalizado) {
      const src = ctx.createBufferSource();
      src.buffer = _tonoPersonalizado;
      const gain = ctx.createGain();
      gain.gain.value = 0.9;
      src.connect(gain);
      gain.connect(ctx.destination);
      src.start();
    } else if (_TONOS[i]) {
      _TONOS[i]();
    }
  } catch (e) { console.warn('tocarTono', e); }
}

function sonarNotificacion() {
  tocarTono();
  if ('vibrate' in navigator) {
    try { navigator.vibrate([200, 100, 200]); } catch (e) {}
  }
  if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification('💬 Mensaje en TUC TUC', {
        body: 'Tienes mensajes nuevos en la conversación',
        icon: '/static/icons/icon-192.png',
        tag: 'tuctuc-chat-msg'
      });
    } catch(e) {}
  }
}

function seleccionarTono(idx) {
  _tonoSeleccionado = idx;
  localStorage.setItem('chat_tono', idx);
  _refrescarTonosBtns();
  tocarTono(idx);
}

function cargarTonoPersonalizado(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async e => {
    try {
      const ctx = _ctx();
      _tonoPersonalizado = await ctx.decodeAudioData(e.target.result);
      seleccionarTono(5);
    } catch (err) { console.error('cargarTonoPersonalizado', err); }
  };
  reader.readAsArrayBuffer(file);
  input.value = '';
}

function _refrescarTonosBtns() {
  document.querySelectorAll('[data-tono]').forEach(btn => {
    const idx = parseInt(btn.dataset.tono);
    btn.classList.toggle('active-item', idx === _tonoSeleccionado);
  });
}"""

js_replacement = """function toggleSonidoHabilitado(checked) {
  localStorage.setItem('chat_sonido_habilitado', checked ? 'true' : 'false');
  const sec = document.getElementById('seccion-tonos');
  if (sec) sec.style.opacity = checked ? '1' : '0.5';
  if (checked) tocarTono();
}

function tocarTono(idx) {
  if (localStorage.getItem('chat_sonido_habilitado') === 'false') return;
  const i = (idx !== undefined ? idx : _tonoSeleccionado);
  try {
    const ctx = _ctx();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
    if (i === 5 && _tonoPersonalizado) {
      const src = ctx.createBufferSource();
      src.buffer = _tonoPersonalizado;
      const gain = ctx.createGain();
      gain.gain.value = 0.95;
      src.connect(gain);
      gain.connect(ctx.destination);
      src.start();
    } else if (_TONOS[i]) {
      _TONOS[i]();
    }
  } catch (e) { console.warn('tocarTono', e); }
}

function sonarNotificacion() {
  tocarTono();
  if ('vibrate' in navigator) {
    try { navigator.vibrate([300, 120, 300, 120, 450]); } catch (e) {}
  }
  if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification('💬 Mensaje en TUC TUC', {
        body: 'Tienes mensajes nuevos en la conversación',
        icon: '/static/icons/icon-192.png',
        tag: 'tuctuc-chat-msg'
      });
    } catch(e) {}
  }
}

function seleccionarTono(idx) {
  _tonoSeleccionado = Number(idx);
  localStorage.setItem('chat_tono', String(_tonoSeleccionado));
  _refrescarTonosBtns();
  tocarTono(_tonoSeleccionado);
}

function cargarTonoPersonalizado(input) {
  const file = input.files[0];
  if (!file) return;
  const nombre = file.name;
  const reader = new FileReader();
  reader.onload = async e => {
    try {
      const ctx = _ctx();
      _tonoPersonalizado = await ctx.decodeAudioData(e.target.result);
      const lbl = document.getElementById('tono-custom-label');
      const ctn = document.getElementById('tono-custom-container');
      if (lbl) lbl.textContent = nombre;
      if (ctn) ctn.style.display = 'flex';
      seleccionarTono(5);
    } catch (err) {
      console.error('cargarTonoPersonalizado', err);
      alert('Formato de audio no compatible.');
    }
  };
  reader.readAsArrayBuffer(file);
  input.value = '';
}

function _refrescarTonosBtns() {
  const sonidoActivo = localStorage.getItem('chat_sonido_habilitado') !== 'false';
  const chk = document.getElementById('chk-chat-sonido');
  if (chk) chk.checked = sonidoActivo;
  const sec = document.getElementById('seccion-tonos');
  if (sec) sec.style.opacity = sonidoActivo ? '1' : '0.5';

  document.querySelectorAll('[data-tono]').forEach(btn => {
    const idx = parseInt(btn.dataset.tono);
    const sel = (idx === _tonoSeleccionado);
    btn.classList.toggle('activo', sel);
    btn.classList.toggle('active-item', sel);
  });
}

// ── Web Push Nativo (VAPID) ────────────────────────────────────────────────

function _urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

async function _actualizarUIPush() {
  const label = document.getElementById('push-status-label');
  const btnTxt = document.getElementById('btn-activar-push-txt');
  const btn = document.getElementById('btn-activar-push');
  if (!label || !btn) return;

  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    label.textContent = 'Este navegador no soporta Web Push.';
    label.style.color = '#ef4444';
    btn.style.display = 'none';
    return;
  }

  if (Notification.permission === 'denied') {
    label.textContent = 'Permiso bloqueado en el navegador.';
    label.style.color = '#ef4444';
    if (btnTxt) btnTxt.textContent = 'Permiso denegado';
    btn.disabled = true;
    return;
  }

  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub && Notification.permission === 'granted') {
      label.textContent = '✓ Activas — Te sonará aun con la app cerrada';
      label.style.color = '#10b981';
      if (btnTxt) btnTxt.textContent = '✓ Alertas push ya están activas';
      btn.style.background = '#10b981';
      btn.disabled = false;
    } else {
      label.textContent = 'Desactivadas — Pulsa para activar';
      label.style.color = 'var(--muted)';
      if (btnTxt) btnTxt.textContent = 'Activar alertas con app cerrada';
      btn.style.background = 'var(--accent, #e8856a)';
      btn.disabled = false;
    }
  } catch (e) {
    label.textContent = 'Estado: ' + Notification.permission;
  }
}

async function activarWebPush() {
  const label = document.getElementById('push-status-label');
  const btnTxt = document.getElementById('btn-activar-push-txt');
  const btn = document.getElementById('btn-activar-push');

  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    alert('Tu dispositivo o navegador no soporta notificaciones Web Push.');
    return;
  }

  try {
    if (btn) btn.disabled = true;
    if (label) { label.textContent = 'Solicitando permiso al sistema...'; label.style.color = 'var(--accent)'; }

    const perm = await Notification.requestPermission();
    if (perm !== 'granted') {
      if (label) { label.textContent = 'Permiso denegado por el usuario.'; label.style.color = '#ef4444'; }
      if (btn) btn.disabled = false;
      return;
    }

    if (label) label.textContent = 'Obteniendo clave VAPID segura...';
    const resKey = await fetch('/api/chat/vapid-public-key');
    const dataKey = await resKey.json();
    if (!dataKey.ok || !dataKey.public_key) {
      throw new Error(dataKey.error || 'Clave VAPID no disponible en servidor');
    }

    const reg = await navigator.serviceWorker.ready;
    const applicationServerKey = _urlBase64ToUint8Array(dataKey.public_key);

    if (label) label.textContent = 'Suscribiendo en el sistema operativo...';
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
      });
    }

    if (label) label.textContent = 'Guardando suscripción en tu cuenta...';
    const resSub = await fetch('/api/chat/push/suscribir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subscription: sub,
        tercero_id: window._miTerceroId || null
      })
    });
    const dataSub = await resSub.json();
    if (dataSub.ok) {
      localStorage.setItem('chat_push_habilitado', 'true');
      if (label) {
        label.textContent = '✓ ¡Listo! Recibirás avisos aun con la app cerrada.';
        label.style.color = '#10b981';
      }
      if (btnTxt) btnTxt.textContent = '✓ Alertas push activas';
      if (btn) {
        btn.style.background = '#10b981';
        btn.disabled = false;
      }
      tocarTono();
    } else {
      throw new Error(dataSub.error || 'No se pudo guardar la suscripción');
    }
  } catch (err) {
    console.error('activarWebPush:', err);
    if (label) {
      label.textContent = 'Error: ' + err.message;
      label.style.color = '#ef4444';
    }
    if (btn) btn.disabled = false;
  }
}

// Registrar Service Worker al iniciar chat
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js').then(reg => {
    _actualizarUIPush();
    // Auto-renovar suscripción silenciosamente si ya tenía permiso concedido
    if (Notification.permission === 'granted' && localStorage.getItem('chat_push_habilitado') === 'true') {
      fetch('/api/chat/vapid-public-key').then(r => r.json()).then(dataKey => {
        if (!dataKey.ok || !dataKey.public_key) return;
        reg.pushManager.getSubscription().then(sub => {
          if (!sub) {
            reg.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: _urlBase64ToUint8Array(dataKey.public_key)
            }).then(nuevaSub => {
              fetch('/api/chat/push/suscribir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription: nuevaSub, tercero_id: window._miTerceroId || null })
              });
            }).catch(() => {});
          }
        });
      }).catch(() => {});
    }
  }).catch(err => console.warn('SW err:', err));

  navigator.serviceWorker.addEventListener('message', ev => {
    if (ev.data && ev.data.type === 'tuctuc_push_click') {
      if (ev.data.token && typeof abrirChat === 'function') {
        abrirChat(ev.data.token);
      }
    }
  });
}"""

if js_target in text:
    text = text.replace(js_target, js_replacement, 1)
    print("JS replaced successfully!")
else:
    print("Warning: js_target not found!")

# Also update abrirModalPerfil to refresh tone buttons and push UI
amp_target = """function abrirModalPerfil() {
  const modal = document.getElementById('modal-perfil');
  if (modal) modal.classList.add('open');
}"""
amp_replacement = """function abrirModalPerfil() {
  const modal = document.getElementById('modal-perfil');
  if (modal) {
    modal.classList.add('open');
    if (typeof _refrescarTonosBtns === 'function') _refrescarTonosBtns();
    if (typeof _actualizarUIPush === 'function') _actualizarUIPush();
  }
}"""
if amp_target in text:
    text = text.replace(amp_target, amp_replacement, 1)
    print("abrirModalPerfil replaced successfully!")
else:
    print("Warning: amp_target not found!")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("chat_v3.html updated completely!")
