import os

crm_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'blueprints', 'crm.py')
with open(crm_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add button to tuctuc-drawer-actions
target_actions = """  <div class="tuctuc-drawer-actions">
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-ctx-cancion" style="display:none;background:rgba(201,100,66,0.35);border-color:#c96442" onclick="tuctucCompartirCancionActual()">
      🎵 Compartir canción
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucCompartirContexto('pregunta')">
      ❓ Consultar pantalla
    </button>"""

repl_actions = """  <div class="tuctuc-drawer-actions">
    <button class="tuctuc-ctx-btn" id="tuctuc-btn-ctx-cancion" style="display:none;background:rgba(201,100,66,0.35);border-color:#c96442" onclick="tuctucCompartirCancionActual()">
      🎵 Compartir canción
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucActivarPushDesdeGlobo()" style="background:rgba(16,185,129,0.22);border-color:#10b981;color:#10b981;font-weight:700">
      🔔 Activar Alertas / Sonido
    </button>
    <button class="tuctuc-ctx-btn" onclick="tuctucCompartirContexto('pregunta')">
      ❓ Consultar pantalla
    </button>"""

if target_actions in text:
    text = text.replace(target_actions, repl_actions, 1)
    print("Action button added to drawer!")
else:
    print("Warning: target_actions not found!")

# 2. Add tuctucActivarPushDesdeGlobo function
target_fn = """  window.tuctucAbrirConversacionToast = function() {"""

repl_fn = """  window.tuctucActivarPushDesdeGlobo = async function() {
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
            alert('✓ ¡Alertas y sonido activados exitosamente!\\nTu dispositivo sonará y avisará en segundo plano.');
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
  };

  window.tuctucAbrirConversacionToast = function() {"""

if target_fn in text:
    text = text.replace(target_fn, repl_fn, 1)
    print("tuctucActivarPushDesdeGlobo function added!")
else:
    print("Warning: target_fn not found!")

with open(crm_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("crm.py updated successfully!")
