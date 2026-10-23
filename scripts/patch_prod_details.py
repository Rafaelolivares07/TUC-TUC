import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/inventario_admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Locate and remove old accounting box
start_tag = '<!-- Accounting impact help box -->'
end_tag = '</div>\n\n\n\n      <div id="prod-alerta"'
if '</div>\r\n\r\n\r\n\r\n      <div id="prod-alerta"' in html:
    end_tag = '</div>\r\n\r\n\r\n\r\n      <div id="prod-alerta"'

idx_start = html.find(start_tag)
idx_end = html.find(end_tag)

if idx_start != -1 and idx_end != -1 and idx_start < idx_end:
    html = html[:idx_start] + html[idx_end + len('</div>'):]
    print('Removed accounting box from preview section successfully')
else:
    print('WARNING: Could not find bounds for old accounting box', idx_start, idx_end)

# 2. Place accounting box at bottom of tab-produccion
marker = '<!-- ── TAB COMPRAS SUGERIDAS (ETAPA 5) ──'
idx_marker = html.find(marker)
if idx_marker != -1:
    # find preceding </div>\n\n  </div>
    # Let's search backward for '</div>\n\n  </div>'
    sub = html[:idx_marker]
    last_div = sub.rfind('  </div>')
    if last_div != -1:
        new_box = """    <!-- Registro Contable de Producción (Al pie de la vista de producción) -->
    <div class="mt-8 p-4 bg-blue-50/80 border border-blue-200/80 rounded-2xl text-xs text-blue-900 flex flex-col gap-1.5 shadow-2xs">
      <div class="flex items-center gap-2 font-bold text-blue-950">
        <span class="text-base">🛈</span>
        <span>Información del Registro Contable de Producción</span>
      </div>
      <p class="text-[11px] text-blue-800 leading-relaxed">
        Si tu negocio tiene habilitada la contabilidad de producción, al registrar cada orden se generará automáticamente el comprobante de reclasificación interna:
      </p>
      <ul class="list-disc pl-5 text-[11px] space-y-0.5 text-blue-900 font-medium">
        <li><b>Crédito (Salida de inventario):</b> Cuentas 14x de los componentes/insumos por su costo total consumido.</li>
        <li><b>Débito (Entrada de inventario):</b> Cuenta 14x del producto terminado fabricado por el costo total acumulado.</li>
      </ul>
    </div>\n\n"""
        html = html[:last_div] + new_box + html[last_div:]
        print('Inserted new accounting box before end of tab-produccion')
    else:
        print('Could not find last div before marker')
else:
    print('Could not find marker')

# 3. Update JavaScript logic for Cantidad Real Obtenida
# We want to ensure:
# - _prodRealManualmenteModificada tracks whether user edited prod-preview-cant-input
# - ajustarCantidadRealProducida does NOT overwrite prod-cantidad
# - previsualizarProduccion preserves manual real quantity
# - limpiarPreview resets _prodRealManualmenteModificada

old_js_ajustar = """function ajustarCantidadRealProducida(valStr, origen = 'preview') {
  const topInp = document.getElementById('prod-cantidad');
  const sugInp = document.getElementById('prod-sug-real-cant');
  const prevInp = document.getElementById('prod-preview-cant-input');

  if (origen !== 'top' && topInp) topInp.value = valStr;
  if (origen !== 'sug' && sugInp) sugInp.value = valStr;
  if (origen !== 'preview' && prevInp) prevInp.value = valStr;"""

new_js_ajustar = """let _prodRealManualmenteModificada = false;

function ajustarCantidadRealProducida(valStr, origen = 'preview') {
  if (origen === 'preview') {
    _prodRealManualmenteModificada = true;
  } else if (origen === 'restore') {
    _prodRealManualmenteModificada = false;
  }

  const prevInp = document.getElementById('prod-preview-cant-input');
  const sugInp = document.getElementById('prod-sug-real-cant');

  // Solo sincronizar el input de la vista previa si el llamado no vino de él mismo
  if (origen !== 'preview' && prevInp) prevInp.value = valStr;
  if (sugInp) sugInp.value = valStr;
  // NOTA: 'Cantidad Real Obtenida' NO debe modificar 'prod-cantidad' (Cantidad a Simular),
  // para mantener desacoplada la intención teórica de la producción real obtenida."""

if old_js_ajustar in html:
    html = html.replace(old_js_ajustar, new_js_ajustar, 1)
    print('Updated ajustarCantidadRealProducida successfully')
else:
    print('WARNING: old_js_ajustar not found')

# In limpiarPreview:
old_limpiar = """  prodPuedeRegistrar = false;
  activePreviewData = null;
}"""

new_limpiar = """  prodPuedeRegistrar = false;
  activePreviewData = null;
  _prodRealManualmenteModificada = false;
}"""

if old_limpiar in html:
    html = html.replace(old_limpiar, new_limpiar, 1)
    print('Updated limpiarPreview successfully')
else:
    print('WARNING: old_limpiar not found')

# In previsualizarProduccion:
old_prev_cant = """  const prevCantInput = document.getElementById('prod-preview-cant-input');
  if (prevCantInput) prevCantInput.value = qty;"""

new_prev_cant = """  const prevCantInput = document.getElementById('prod-preview-cant-input');
  if (prevCantInput) {
    if (!_prodRealManualmenteModificada) {
      prevCantInput.value = qty;
    } else {
      const valManual = parseFloat(prevCantInput.value);
      if (valManual && !isNaN(valManual) && valManual > 0) {
        d.cantidad = valManual;
      }
    }
  }"""

if old_prev_cant in html:
    html = html.replace(old_prev_cant, new_prev_cant, 1)
    print('Updated prevCantInput in previsualizarProduccion successfully')
else:
    print('WARNING: old_prev_cant not found')

with open('templates/inventario_admin.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Finished script')
