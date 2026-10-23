import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chat_v3.html')
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target_dots = """      <button class="dots-item" onclick="abrirModalEnlazarUsuario();cerrarDotsMenu()">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
        Enlazar con Usuario
      </button>"""

repl_dots = """      <button class="dots-item" onclick="abrirModalEnlazarUsuario();cerrarDotsMenu()">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
        Enlazar con Usuario
      </button>
      <button class="dots-item" onclick="abrirModalPerfil();cerrarDotsMenu()">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        Sonido y Alertas Push
      </button>"""

if target_dots in text:
    text = text.replace(target_dots, repl_dots, 1)
    print("Dots menu updated!")
else:
    print("Warning: target_dots not found!")

target_listener = """  navigator.serviceWorker.addEventListener('message', ev => {
    if (ev.data && ev.data.type === 'tuctuc_push_click') {
      if (ev.data.token && typeof abrirChat === 'function') {
        abrirChat(ev.data.token);
      }
    }
  });"""

repl_listener = """  navigator.serviceWorker.addEventListener('message', ev => {
    if (ev.data && ev.data.type === 'tuctuc_push_click') {
      if (ev.data.token && typeof abrirChat === 'function') {
        abrirChat(ev.data.token);
      }
    }
  });

  window.addEventListener('message', ev => {
    if (ev.data && ev.data.type === 'abrir_perfil') {
      if (typeof abrirModalPerfil === 'function') abrirModalPerfil();
    }
  });"""

if target_listener in text:
    text = text.replace(target_listener, repl_listener, 1)
    print("Window message listener added!")
else:
    print("Warning: target_listener not found!")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("chat_v3.html patched successfully!")
