import os, re

# 1. PATCH CRM.PY
crm_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'blueprints', 'crm.py')
with open(crm_path, 'r', encoding='utf-8') as f:
    crm_text = f.read()

# Replace tuctuc-drawer-actions to include both buttons
target_drawer_actions = """  <div class="tuctuc-drawer-actions">
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-ctx-cancion" style="display:none;background:rgba(201,100,66,0.35);border-color:#c96442" onclick="tuctucCompartirCancionActual()">
      🎵 Compartir canción
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucActivarPushDesdeGlobo()" style="background:rgba(16,185,129,0.22);border-color:#10b981;color:#10b981;font-weight:700">
      🔔 Activar Alertas / Sonido
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucCompartirContexto('pregunta')">
      ❓ Consultar pantalla
    </button>"""

repl_drawer_actions = """  <div class="tuctuc-drawer-actions">
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-ctx-cancion" style="display:none;background:rgba(201,100,66,0.35);border-color:#c96442" onclick="tuctucCompartirCancionActual()">
      🎵 Compartir
    </button>
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-activar-push" onclick="tuctucActivarPushDesdeGlobo()" style="background:rgba(16,185,129,0.22);border-color:#10b981;color:#10b981;font-weight:700">
      🔔 Activar Alertas
    </button>
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-probar-timbre" onclick="tuctucProbarTimbreDesdeGlobo()" style="background:rgba(232,133,106,0.22);border-color:#e8856a;color:#e8856a;font-weight:700">
      🔊 Probar Timbre
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucCompartirContexto('pregunta')">
      ❓ Consultar
    </button>"""

if target_drawer_actions in crm_text:
    crm_text = crm_text.replace(target_drawer_actions, repl_drawer_actions, 1)
    print("Updated drawer actions in crm.py")
else:
    print("Warning: target_drawer_actions not found in crm.py")

# Replace _emitirChime in crm.py with 100% safe audio that CANNOT whistle forever
old_emitir_chime = """  function _emitirChime(ctx) {
    const t0 = ctx.currentTime;
    // Chime doble brillante y de alto volumen (880Hz -> 1320Hz con armónicos)
    const notas = [
      { f: 880, start: 0, dur: 0.16, vol: 0.85, type: 'triangle' },
      { f: 1760, start: 0.01, dur: 0.14, vol: 0.40, type: 'sine' },
      { f: 1320, start: 0.13, dur: 0.35, vol: 0.90, type: 'triangle' },
      { f: 2640, start: 0.14, dur: 0.30, vol: 0.45, type: 'sine' }
    ];
    notas.forEach(n => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = n.type;
      osc.frequency.setValueAtTime(n.f, t0 + n.start);
      gain.gain.setValueAtTime(0, t0 + n.start);
      gain.gain.linearRampToValueAtTime(n.vol, t0 + n.start + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.001, t0 + n.start + n.dur);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t0 + n.start);
      osc.stop(t0 + n.start + n.dur + 0.04);
    });
  }"""

new_emitir_chime = """  function _emitirChime(ctx) {
    try {
      const t0 = ctx.currentTime;
      const notas = [
        { f: 880, start: 0, dur: 0.16, vol: 0.70, type: 'triangle' },
        { f: 1320, start: 0.12, dur: 0.28, vol: 0.80, type: 'triangle' }
      ];
      notas.forEach(n => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = n.type;
        osc.frequency.setValueAtTime(n.f, t0 + n.start);
        gain.gain.setValueAtTime(0.001, t0 + n.start);
        gain.gain.linearRampToValueAtTime(n.vol, t0 + n.start + 0.015);
        gain.gain.linearRampToValueAtTime(0.0001, t0 + n.start + n.dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t0 + n.start);
        osc.stop(t0 + n.start + n.dur + 0.05);
        setTimeout(() => {
          try { osc.stop(); } catch(e) {}
          try { osc.disconnect(); gain.disconnect(); } catch(e) {}
        }, (n.start + n.dur + 0.1) * 1000);
      });
    } catch(e) {
      console.warn('emitirChime error', e);
    }
  }"""

if old_emitir_chime in crm_text:
    crm_text = crm_text.replace(old_emitir_chime, new_emitir_chime, 1)
    print("Replaced _emitirChime in crm.py")
else:
    print("Warning: old_emitir_chime not found in crm.py")

# Replace tuctucActivarPushDesdeGlobo and add tuctucProbarTimbreDesdeGlobo in crm.py
old_globo_push = """  window.tuctucActivarPushDesdeGlobo = async function() {
    _despertarAudio();
    _tocarChimeFuerte();
    if ('Notification' in window) {
      try {
        const perm = await Notification.requestPermission();
        if (perm === 'granted' && 'serviceWorker' in navigator) {
          const reg = await navigator.serviceWorker.ready;
          const rKey = await fetch('/api/chat/vapid-public-key');
          const dKey = await rKey.json();
          if (dKey.ok && dKey.public_key) {
            const padding = '='.repeat((4 - dKey.public_key.length % 4) % 4);
            const base64 = (dKey.public_key + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
            let sub = await reg.pushManager.getSubscription();
            if (!sub) {
              sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: outputArray });
            }
            await fetch('/api/chat/push/suscribir', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ subscription: sub })
            });
            await fetch('/api/chat/push/test', { method: 'POST' });
            alert('Alertas Web Push y sonido activados exitosamente en este dispositivo.');
            return;
          }
        }
      } catch(e) {
        console.error('push globo error', e);
      }
    }
    const ifr = document.getElementById('tuctuc-chat-iframe');
    if (ifr && ifr.contentWindow) {
      try { ifr.contentWindow.postMessage({ type: 'abrir_perfil' }, '*'); } catch(e) {}
    }
  };"""

new_globo_push = """  async function _obtenerSWReg() {
    if (!('serviceWorker' in navigator)) return null;
    let r = await navigator.serviceWorker.getRegistration('/sw.js');
    if (!r) r = await navigator.serviceWorker.getRegistration();
    if (!r) r = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    if (r.active) return r;
    return new Promise(res => {
      const t = setTimeout(() => res(r), 3000);
      navigator.serviceWorker.ready.then(rr => { clearTimeout(t); res(rr); }).catch(() => { clearTimeout(t); res(r); });
    });
  }

  window.tuctucActivarPushDesdeGlobo = async function() {
    _despertarAudio();
    _tocarChimeFuerte();
    const btn = document.getElementById('tuctuc-btn-activar-push');
    if (btn) btn.textContent = '⏳ Activando...';
    try {
      if ('Notification' in window) {
        const perm = await Notification.requestPermission();
        if (perm === 'granted' && 'serviceWorker' in navigator) {
          const reg = await _obtenerSWReg();
          const rKey = await fetch('/api/chat/vapid-public-key');
          const dKey = await rKey.json();
          if (dKey.ok && dKey.public_key && reg) {
            const padding = '='.repeat((4 - dKey.public_key.length % 4) % 4);
            const base64 = (dKey.public_key + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
            let sub = await reg.pushManager.getSubscription();
            if (!sub) {
              sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: outputArray });
            }
            await fetch('/api/chat/push/suscribir', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ subscription: sub })
            });
            if (btn) btn.textContent = '✓ Alertas OK';
            alert('✓ Alertas Web Push activadas correctamente en este dispositivo.');
            return;
          }
        }
      }
    } catch(e) {
      console.error('push globo error', e);
    }
    if (btn) btn.textContent = '🔔 Activar Alertas';
    const ifr = document.getElementById('tuctuc-chat-iframe');
    if (ifr && ifr.contentWindow) {
      try { ifr.contentWindow.postMessage({ type: 'abrir_perfil' }, '*'); } catch(e) {}
    }
  };

  window.tuctucProbarTimbreDesdeGlobo = async function() {
    _despertarAudio();
    _tocarChimeFuerte();
    try {
      await fetch('/api/chat/push/test', { method: 'POST' });
    } catch(e) {}
  };"""

if old_globo_push in crm_text:
    crm_text = crm_text.replace(old_globo_push, new_globo_push, 1)
    print("Replaced tuctucActivarPushDesdeGlobo in crm.py")
else:
    print("Warning: old_globo_push not found in crm.py")

with open(crm_path, 'w', encoding='utf-8') as f:
    f.write(crm_text)


# 2. PATCH CHAT_V3.HTML
chat_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chat_v3.html')
with open(chat_path, 'r', encoding='utf-8') as f:
    chat_text = f.read()

# Replace _nota in chat_v3.html
old_nota = """function _nota(freq, inicio, dur, vol = 0.85, tipo = 'triangle') {
  const ctx = _ctx();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.type = tipo;
  osc.frequency.setValueAtTime(freq, ctx.currentTime + inicio);
  gain.gain.setValueAtTime(0, ctx.currentTime + inicio);
  gain.gain.linearRampToValueAtTime(vol, ctx.currentTime + inicio + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + inicio + dur);
  osc.start(ctx.currentTime + inicio);
  osc.stop(ctx.currentTime + inicio + dur + 0.05);
}"""

new_nota = """function _nota(freq, inicio, dur, vol = 0.85, tipo = 'triangle') {
  const ctx = _ctx();
  if (!ctx) return;
  try {
    const t0 = ctx.currentTime + inicio;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = tipo;
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0.001, t0);
    gain.gain.linearRampToValueAtTime(vol, t0 + 0.015);
    gain.gain.linearRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.05);
    setTimeout(() => {
      try { osc.stop(); } catch(e) {}
      try { osc.disconnect(); gain.disconnect(); } catch(e) {}
    }, (inicio + dur + 0.1) * 1000);
  } catch(e) {
    console.warn('_nota err', e);
  }
}"""

if old_nota in chat_text:
    chat_text = chat_text.replace(old_nota, new_nota, 1)
    print("Replaced _nota in chat_v3.html")
else:
    print("Warning: old_nota not found in chat_v3.html")

# Replace activarWebPush in chat_v3.html
old_act_push = """    if (label) label.textContent = 'Obteniendo clave VAPID segura...';
    const resKey = await fetch('/api/chat/vapid-public-key');
    const dataKey = await resKey.json();
    if (!dataKey.ok || !dataKey.public_key) {
      throw new Error(dataKey.error || 'Clave VAPID no disponible en servidor');
    }

    const reg = await navigator.serviceWorker.ready;
    const applicationServerKey = _urlBase64ToUint8Array(dataKey.public_key);"""

new_act_push = """    if (label) label.textContent = 'Obteniendo clave VAPID segura...';
    const resKey = await fetch('/api/chat/vapid-public-key');
    const dataKey = await resKey.json();
    if (!dataKey.ok || !dataKey.public_key) {
      throw new Error(dataKey.error || 'Clave VAPID no disponible en servidor');
    }

    if (label) label.textContent = 'Iniciando servicio de alertas...';
    const reg = await _obtenerSWReg();
    if (!reg) throw new Error('No se pudo inicializar el Service Worker');

    const applicationServerKey = _urlBase64ToUint8Array(dataKey.public_key);"""

if old_act_push in chat_text:
    chat_text = chat_text.replace(old_act_push, new_act_push, 1)
    print("Replaced activarWebPush flow in chat_v3.html")
else:
    print("Warning: old_act_push not found in chat_v3.html")

# Add _obtenerSWReg definition in chat_v3.html if missing
sw_helper_fn = """async function _obtenerSWReg() {
  if (!('serviceWorker' in navigator)) return null;
  let r = await navigator.serviceWorker.getRegistration('/sw.js');
  if (!r) r = await navigator.serviceWorker.getRegistration();
  if (!r) r = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
  if (r.active) return r;
  return new Promise(res => {
    const t = setTimeout(() => res(r), 3000);
    navigator.serviceWorker.ready.then(rr => { clearTimeout(t); res(rr); }).catch(() => { clearTimeout(t); res(r); });
  });
}
"""

if "_obtenerSWReg" not in chat_text:
    target_place = "function _urlBase64ToUint8Array"
    chat_text = chat_text.replace(target_place, sw_helper_fn + "\n" + target_place, 1)
    print("Added _obtenerSWReg to chat_v3.html")

# Replace registration in chat_v3.html from /static/sw.js to /sw.js
chat_text = chat_text.replace("navigator.serviceWorker.register('/static/sw.js')", "navigator.serviceWorker.register('/sw.js', { scope: '/' })")
crm_text_sw = None

with open(chat_path, 'w', encoding='utf-8') as f:
    f.write(chat_text)

# Also update crm.py registration from /static/sw.js to /sw.js
with open(crm_path, 'r', encoding='utf-8') as f:
    crm_text = f.read()
crm_text = crm_text.replace("navigator.serviceWorker.register('/static/sw.js')", "navigator.serviceWorker.register('/sw.js', { scope: '/' })")
with open(crm_path, 'w', encoding='utf-8') as f:
    f.write(crm_text)

print("All audio and push hang fixes applied!")
