with open("templates/inventario_admin.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add modal-oc-exito markup before </body>
modal_exito_markup = """
<!-- MODAL ÉXITO ORDEN DE COMPRA -->
<div id="modal-oc-exito" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center hidden p-3 backdrop-blur-xs">
  <div class="bg-white rounded-2xl max-w-lg w-full p-5 shadow-2xl border border-slate-200 space-y-4">
    <div class="flex items-center gap-2.5">
      <div class="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-black text-lg">
        <i class="bi bi-check-circle-fill"></i>
      </div>
      <div>
        <h3 class="text-sm font-bold uppercase text-slate-800" id="modal-exito-oc-titulo">Orden Generada con Éxito</h3>
        <p class="text-xs text-slate-500">Comparte el pedido con tu proveedor por WhatsApp</p>
      </div>
    </div>

    <!-- Mensaje con formato estructurado -->
    <div class="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-800 font-sans space-y-1 max-h-48 overflow-y-auto custom-scroll whitespace-pre-wrap select-all font-mono" id="modal-exito-oc-mensaje">
      <!-- Texto estructurado -->
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
      <a id="btn-exito-abrir-wa" href="#" target="_blank"
         class="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-sm transition">
        <i class="bi bi-whatsapp text-sm"></i> Abrir en WhatsApp
      </a>

      <button onclick="copiarMensajeCompletoOC()"
              class="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-800 font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition cursor-pointer">
        <i class="bi bi-clipboard-check text-sm"></i> Copiar Mensaje
      </button>
    </div>

    <div class="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
      <button onclick="copiarSoloLinkOC()" class="text-indigo-600 hover:text-indigo-800 font-bold hover:underline flex items-center gap-1 cursor-pointer">
        🔗 Copiar solo enlace
      </button>

      <button onclick="cerrarModalExitoOC()" class="px-3.5 py-1.5 bg-slate-200 hover:bg-slate-300 rounded-lg font-bold text-slate-700 cursor-pointer">
        Entendido
      </button>
    </div>
  </div>
</div>
"""

pos_body = html.rfind("</body>")
assert pos_body != -1, "</body> not found"
html = html[:pos_body] + modal_exito_markup + "\n" + html[pos_body:]

# 2. Patch confirmarYEnviarOC in JS
target_block = """      // Abrir WhatsApp con el link
      if (res.whatsapp_url) {
        window.open(res.whatsapp_url, '_blank');
      } else {
        prompt('Orden creada. Comparte este enlace con el proveedor:', res.url_publica);
      }"""

replacement_block = """      // Mostrar modal de éxito con el mensaje estructurado completo
      mostrarModalExitoOC(res);

      // Intentar abrir WhatsApp en pestaña nueva
      if (res.whatsapp_url) {
        try {
          window.open(res.whatsapp_url, '_blank');
        } catch(e) {}
      }"""

pos_target = html.find(target_block)
if pos_target != -1:
    html = html[:pos_target] + replacement_block + html[pos_target + len(target_block):]
else:
    print("Warning: target_block not found")

# 3. Add JS helper functions for modal exito
js_helpers = """
let oc_ultimo_resultado = null;

function mostrarModalExitoOC(res) {
  oc_ultimo_resultado = res;
  const tit = document.getElementById('modal-exito-oc-titulo');
  if (tit) tit.textContent = `¡Orden ${res.numero_oc} Generada!`;
  const msg = document.getElementById('modal-exito-oc-mensaje');
  if (msg) msg.textContent = res.mensaje_whatsapp || '';
  
  const btnWa = document.getElementById('btn-exito-abrir-wa');
  if (btnWa) {
    btnWa.href = res.whatsapp_url || '#';
  }
  
  document.getElementById('modal-oc-exito')?.classList.remove('hidden');
}

function cerrarModalExitoOC() {
  document.getElementById('modal-oc-exito')?.classList.add('hidden');
}

function copiarMensajeCompletoOC() {
  if (!oc_ultimo_resultado) return;
  navigator.clipboard.writeText(oc_ultimo_resultado.mensaje_whatsapp).then(() => {
    toast('📋 Mensaje completo de WhatsApp copiado al portapapeles.');
  });
}

function copiarSoloLinkOC() {
  if (!oc_ultimo_resultado) return;
  navigator.clipboard.writeText(oc_ultimo_resultado.url_publica).then(() => {
    toast('🔗 Enlace público copiado.');
  });
}
"""

pos_script = html.rfind("</script>")
assert pos_script != -1, "</script> not found"
html = html[:pos_script] + js_helpers + "\n" + html[pos_script:]

with open("templates/inventario_admin.html", "w", encoding="utf-8") as f:
    f.write(html)

print("inventario_admin.html patched successfully.")
