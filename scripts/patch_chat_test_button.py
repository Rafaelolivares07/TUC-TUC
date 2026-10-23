import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chat_v3.html')
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add Probar Sonido button in modal-perfil
target_btn = """        <button id="btn-activar-push" onclick="activarWebPush()"
                style="width:100%;margin-top:10px;padding:9px 12px;border-radius:10px;font-size:12.5px;font-weight:600;background:var(--accent);color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px">
          <span id="btn-activar-push-txt">Activar alertas con app cerrada</span>
        </button>
      </div>"""

repl_btn = """        <button id="btn-activar-push" onclick="activarWebPush()"
                style="width:100%;margin-top:10px;padding:9px 12px;border-radius:10px;font-size:12.5px;font-weight:600;background:var(--accent);color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px">
          <span id="btn-activar-push-txt">Activar alertas con app cerrada</span>
        </button>
        <button id="btn-probar-push" onclick="probarNotificacionYTimbre()"
                style="width:100%;margin-top:8px;padding:9px 12px;border-radius:10px;font-size:12.5px;font-weight:600;background:var(--surface2);color:var(--ink);border:1px solid var(--hairline);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px">
          <span id="btn-probar-push-txt">🔊 Probar sonido y timbre ahora</span>
        </button>
      </div>"""

if target_btn in text:
    text = text.replace(target_btn, repl_btn, 1)
    print("Button added to modal-perfil!")
else:
    print("Warning: target_btn not found!")

# 2. Add probarNotificacionYTimbre function and enhance SW auto-subscribe
target_sw = """// Registrar Service Worker al iniciar chat
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
  }).catch(err => console.warn('SW err:', err));"""

repl_sw = """async function probarNotificacionYTimbre() {
  const btnTxt = document.getElementById('btn-probar-push-txt');
  if (btnTxt) btnTxt.textContent = '🔔 Probando timbre...';

  // 1. Tocar tono local a volumen completo y vibrar
  tocarTono();
  if ('vibrate' in navigator) {
    try { navigator.vibrate([300, 120, 300, 120, 450]); } catch(e) {}
  }

  // 2. Si hay permiso, lanzar notificación del SO
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification('🔔 Prueba de Alerta TUC TUC', {
        body: '¡Sonido y alertas verificados con éxito!',
        icon: '/static/icons/icon-192.png',
        tag: 'tuctuc-test-alert'
      });
    } catch(e) {}
  }

  // 3. Si no tiene permiso de notificaciones todavía, solicitarlo
  if ('Notification' in window && Notification.permission === 'default') {
    try {
      const p = await Notification.requestPermission();
      if (p === 'granted') {
        await activarWebPush();
      }
    } catch(e) {}
  }

  // 4. Solicitar al backend disparar Web Push nativo
  try {
    const r = await fetch('/api/chat/push/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tercero_id: window._miTerceroId || null })
    });
    const d = await r.json();
    if (btnTxt) btnTxt.textContent = '🔊 Probar sonido y timbre ahora';
    if (d.ok) {
      alert('✓ Timbre ejecutado en este navegador.\\nSe envió además la notificación Web Push a ' + d.subs_count + ' dispositivo(s) registrado(s).');
    } else {
      alert('Timbre ejecutado en este navegador.\\n\\nNota: Para que te suene cuando la aplicación esté CERRADA en tu celular o PC, pulsa primero el botón verde "Activar alertas con app cerrada".');
    }
  } catch(e) {
    if (btnTxt) btnTxt.textContent = '🔊 Probar sonido y timbre ahora';
    console.error('Error probando push:', e);
  }
}

// Registrar Service Worker al iniciar chat
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js').then(reg => {
    _actualizarUIPush();
    // Auto-registrar suscripción silenciosamente si el permiso ya fue concedido
    if (Notification.permission === 'granted') {
      fetch('/api/chat/vapid-public-key').then(r => r.json()).then(dataKey => {
        if (!dataKey.ok || !dataKey.public_key) return;
        reg.pushManager.getSubscription().then(sub => {
          const syncSub = (s) => {
            fetch('/api/chat/push/suscribir', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ subscription: s, tercero_id: window._miTerceroId || null })
            }).then(() => _actualizarUIPush()).catch(() => {});
          };
          if (!sub) {
            reg.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: _urlBase64ToUint8Array(dataKey.public_key)
            }).then(nuevaSub => syncSub(nuevaSub)).catch(() => {});
          } else {
            syncSub(sub);
          }
        });
      }).catch(() => {});
    }
  }).catch(err => console.warn('SW err:', err));"""

if target_sw in text:
    text = text.replace(target_sw, repl_sw, 1)
    print("SW and test function added!")
else:
    print("Warning: target_sw not found!")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("chat_v3.html updated successfully!")
