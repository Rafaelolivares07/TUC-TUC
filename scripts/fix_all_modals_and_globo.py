import os, re

# 1. FIX CRM.PY
crm_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'blueprints', 'crm.py')
with open(crm_path, 'r', encoding='utf-8') as f:
    crm_text = f.read()

# Replace any multiline alerts in crm.py
target_alert = "alert('✓ ¡Alertas y sonido activados exitosamente!\nTu dispositivo sonará y avisará en segundo plano.');"
repl_alert = "alert('Alertas Web Push y sonido activados exitosamente en este dispositivo.');"

if target_alert in crm_text:
    crm_text = crm_text.replace(target_alert, repl_alert)
    print("Fixed target_alert in crm.py")
else:
    # search with regex
    crm_text = re.sub(
        r"alert\('✓ ¡Alertas y sonido activados exitosamente![^']*'\);",
        repl_alert,
        crm_text
    )
    print("Checked regex for alert in crm.py")

with open(crm_path, 'w', encoding='utf-8') as f:
    f.write(crm_text)


# 2. FIX CHAT_V3.HTML
chat_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chat_v3.html')
with open(chat_path, 'r', encoding='utf-8') as f:
    chat_text = f.read()

# Ensure CSS has .sheet-modal-backdrop.open { display: flex !important; }
css_sheet = ".sheet-modal-backdrop {"
css_sheet_repl = """.sheet-modal-backdrop.open { display: flex !important; }
    .sheet-modal-backdrop {"""
if css_sheet in chat_text and ".sheet-modal-backdrop.open" not in chat_text:
    chat_text = chat_text.replace(css_sheet, css_sheet_repl, 1)
    print("Added .sheet-modal-backdrop.open to CSS!")

# Fix abrirModalPerfil and cerrarModalPerfil
old_perfil_fn = """function abrirModalPerfil() {
  const modal = document.getElementById('modal-perfil');
  if (modal) {
    modal.classList.add('open');
    if (typeof _refrescarTonosBtns === 'function') _refrescarTonosBtns();
    if (typeof _actualizarUIPush === 'function') _actualizarUIPush();
  }
}

function cerrarModalPerfil() {
  const modal = document.getElementById('modal-perfil');
  if (modal) modal.classList.remove('open');
}"""

new_perfil_fn = """function abrirModalPerfil() {
  const modal = document.getElementById('modal-perfil');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('open');
    if (typeof _refrescarTonosBtns === 'function') _refrescarTonosBtns();
    if (typeof _actualizarUIPush === 'function') _actualizarUIPush();
  }
}

function cerrarModalPerfil() {
  const modal = document.getElementById('modal-perfil');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('open');
  }
}"""

if old_perfil_fn in chat_text:
    chat_text = chat_text.replace(old_perfil_fn, new_perfil_fn, 1)
    print("abrirModalPerfil & cerrarModalPerfil updated!")
else:
    # Try more flexible replace
    chat_text = re.sub(
        r'function abrirModalPerfil\(\)\s*\{.*?function cerrarModalPerfil\(\)\s*\{[^}]*\}',
        new_perfil_fn,
        chat_text,
        flags=re.DOTALL
    )
    print("Regex replaced abrirModalPerfil & cerrarModalPerfil!")

with open(chat_path, 'w', encoding='utf-8') as f:
    f.write(chat_text)

print("All fixes applied successfully!")
