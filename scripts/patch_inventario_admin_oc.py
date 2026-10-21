with open("templates/inventario_admin.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Rename tab button
btn_old = '<button class="tab-btn" onclick="mostrarTab(\'compras_sugerencias\')">🛒 Compras Sugeridas</button>'
btn_new = '<button class="tab-btn" onclick="mostrarTab(\'compras_sugerencias\')">🛒 Compras</button>'
if btn_old in html:
    html = html.replace(btn_old, btn_new, 1)

# 2. Add peso_variable in product modal
peso_modal_target = """        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-0.5">Días Stock Mínimo (Alerta)</label>
            <input id="mp-dias-min-stock" type="number" min="0" max="180" placeholder="Global (~3 d)" class="w-full text-xs border rounded px-2 py-1 outline-none">
            <span class="text-[9px] text-slate-400">Si cobertura &lt; este valor, entra en agotado y avisa.</span>
          </div>
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-0.5">Días Stock Máximo (Meta)</label>
            <input id="mp-dias-max-stock" type="number" min="0" max="180" placeholder="Global (~15 d)" class="w-full text-xs border rounded px-2 py-1 outline-none">
            <span class="text-[9px] text-slate-400">Días deseados a tener cubiertos en bodega.</span>
          </div>
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-0.5">Stock Mínimo Fijo (Und)</label>
            <input id="mp-stock-minimo" type="number" min="0" step="0.01" placeholder="Opcional (fijo)" class="w-full text-xs border rounded px-2 py-1 outline-none">
            <span class="text-[9px] text-slate-400">Umbral fijo en unidades (opcional).</span>
          </div>
        </div>
      </div>"""

peso_modal_replacement = """        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-0.5">Días Stock Mínimo (Alerta)</label>
            <input id="mp-dias-min-stock" type="number" min="0" max="180" placeholder="Global (~3 d)" class="w-full text-xs border rounded px-2 py-1 outline-none">
            <span class="text-[9px] text-slate-400">Si cobertura &lt; este valor, entra en agotado y avisa.</span>
          </div>
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-0.5">Días Stock Máximo (Meta)</label>
            <input id="mp-dias-max-stock" type="number" min="0" max="180" placeholder="Global (~15 d)" class="w-full text-xs border rounded px-2 py-1 outline-none">
            <span class="text-[9px] text-slate-400">Días deseados a tener cubiertos en bodega.</span>
          </div>
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-0.5">Stock Mínimo Fijo (Und)</label>
            <input id="mp-stock-minimo" type="number" min="0" step="0.01" placeholder="Opcional (fijo)" class="w-full text-xs border rounded px-2 py-1 outline-none">
            <span class="text-[9px] text-slate-400">Umbral fijo en unidades (opcional).</span>
          </div>
        </div>
      </div>

      <!-- Tolerancia / Variación de Peso en Despacho (Catch Weight) -->
      <div class="sm:col-span-2 bg-amber-50/60 border border-amber-200/80 p-3 rounded-xl flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1.5 text-xs font-bold text-amber-950">
            <span>⚖️</span> Tolerancia de Peso Variable en Despacho (Catch Weight)
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <span class="text-xs text-amber-900 font-semibold">Permitir variación:</span>
            <input type="checkbox" id="mp-peso-variable" class="w-4 h-4 accent-amber-600 rounded" onchange="toggleToleranciaPeso(this.checked)">
          </label>
        </div>
        <p class="text-[11px] text-amber-800/90 leading-tight">
          Actívalo para carnes, pollo, quesos o verduras que no se despachan con peso exacto. El proveedor podrá ajustar el despacho dentro del margen pactado.
        </p>
        <div id="cont-tolerancia-peso" class="hidden flex items-center gap-2 pt-1 border-t border-amber-200/60">
          <label class="text-[10px] font-bold text-amber-900 uppercase">Tolerancia permitida (± %):</label>
          <input id="mp-tolerancia-peso" type="number" min="1" max="50" step="1" value="10" class="w-20 text-xs border border-amber-300 rounded px-2 py-1 outline-none bg-white font-bold text-amber-950">
          <span class="text-[10px] text-amber-700 italic">Ej: 10% permite despachar entre 18 Kg y 22 Kg para un pedido de 20 Kg.</span>
        </div>
      </div>"""

if peso_modal_target in html:
    html = html.replace(peso_modal_target, peso_modal_replacement, 1)
else:
    print("Warning: peso_modal_target not found")

# 3. Add button ORDEN DE COMPRA next to Registrar Entrada
btn_oc_target = """            <button type="button" onclick="hacerEntradaProveedor(${pIdx})"

                    class="px-4 py-2 bg-rose-500 hover:bg-rose-600 active:scale-95 text-white font-bold rounded-xl text-xs flex items-center gap-1.5 transition shadow-sm cursor-pointer">

              📥 Registrar Entrada (FAC)

            </button>"""

btn_oc_replacement = """            <button type="button" onclick="hacerEntradaProveedor(${pIdx})"
                    class="px-3.5 py-2 bg-slate-600 hover:bg-slate-700 active:scale-95 text-white font-bold rounded-xl text-xs flex items-center gap-1.5 transition shadow-sm cursor-pointer"
                    title="Transferir directamente a la pestaña de Entradas sin enviar Orden de Compra">
              📥 Entrada Directa (FAC)
            </button>

            <button type="button" onclick="abrirModalOrdenCompra(${pIdx})"
                    class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-black rounded-xl text-xs flex items-center gap-1.5 transition shadow-sm cursor-pointer"
                    title="Generar consecutivo formal #OC-XXXX, abrir chat y enviar link interactivo al proveedor por WhatsApp">
              📄 ORDEN DE COMPRA
            </button>"""

if btn_oc_target in html:
    html = html.replace(btn_oc_target, btn_oc_replacement, 1)
else:
    print("Warning: btn_oc_target not found")

# 4. Add section of Órdenes de Compra en Curso inside tab-compras_sugerencias
sec_oc_target = """      <div class="space-y-3" id="compras-proveedores-list">
        <p class="text-xs text-slate-400 italic">Analizando cotizaciones y consumos...</p>
      </div>

    </div>

  </div>"""

sec_oc_replacement = """      <div class="space-y-3" id="compras-proveedores-list">
        <p class="text-xs text-slate-400 italic">Analizando cotizaciones y consumos...</p>
      </div>

    </div>

    <!-- ── SECCIÓN DE ÓRDENES DE COMPRA Y DESPACHOS ACTIVOS ───────────────── -->
    <div class="mt-8 bg-slate-50 border border-slate-200 rounded-2xl p-5 shadow-xs">
      <div class="flex items-center justify-between border-b border-slate-200 pb-3 mb-4 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-sm shadow-sm">
            <i class="bi bi-file-earmark-text"></i>
          </div>
          <div>
            <h2 class="text-sm font-bold text-slate-900 uppercase tracking-wide">Órdenes de Compra y Despachos</h2>
            <p class="text-[11px] text-slate-500">Historial y seguimiento de órdenes enviadas a proveedores, propuestas con cambios y recepciones.</p>
          </div>
        </div>
        <button onclick="cargarOrdenesCompraNegocio()" class="px-3 py-1.5 text-xs bg-white border border-slate-200 hover:bg-slate-100 rounded-lg font-bold text-slate-700 flex items-center gap-1 shadow-2xs transition">
          <i class="bi bi-arrow-clockwise"></i> Actualizar Órdenes
        </button>
      </div>

      <div id="lista-ordenes-compra" class="space-y-3">
        <p class="text-xs text-slate-400 italic text-center py-4">Cargando órdenes de compra...</p>
      </div>
    </div>

  </div>"""

if sec_oc_target in html:
    html = html.replace(sec_oc_target, sec_oc_replacement, 1)
else:
    print("Warning: sec_oc_target not found")

# 5. Add Modal Generar Orden de Compra at the end before </body>
modal_oc_html = """
<!-- ============================================================== -->
<!-- MODAL: GENERAR ORDEN DE COMPRA (OC)                            -->
<!-- ============================================================== -->
<div id="modal-generar-oc" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center hidden p-3 backdrop-blur-xs">
  <div class="bg-white rounded-2xl max-w-2xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
    
    <!-- Modal Header -->
    <div class="px-5 py-3.5 bg-gradient-to-r from-indigo-900 to-slate-900 text-white flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center font-black text-sm">
          📄
        </div>
        <div>
          <h3 class="text-sm font-bold uppercase tracking-wider text-white">Generar Orden de Compra</h3>
          <p id="modal-oc-prov-nombre" class="text-xs text-indigo-200 font-medium">Proveedor: ...</p>
        </div>
      </div>
      <button onclick="cerrarModalOrdenCompra()" class="text-slate-400 hover:text-white text-lg font-bold p-1">✕</button>
    </div>

    <!-- Modal Body -->
    <div class="p-5 overflow-y-auto custom-scroll space-y-4 flex-1 text-xs">
      
      <!-- Condiciones de Entrega y Pago -->
      <div class="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-3">
        <span class="text-[10px] font-extrabold uppercase tracking-wide text-slate-500 block border-b border-slate-200 pb-1">
          📍 Parámetros de Despacho y Entrega
        </span>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Modalidad -->
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">Modalidad de Despacho</label>
            <select id="modal-oc-modalidad" onchange="cambiarModalidadEntregaOC()" class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-white outline-none focus:border-indigo-500">
              <option value="sede">🛵 Proveedor entrega en nuestra Sede</option>
              <option value="recoger">🛍️ Recogemos en Bodega del Proveedor</option>
            </select>
          </div>

          <!-- Sede Destino -->
          <div id="cont-oc-sede">
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">Sede / Centro de Utilidad Destino</label>
            <select id="modal-oc-sede" onchange="cambiarSedeOC(this.value)" class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-white outline-none focus:border-indigo-500">
              <option value="">Cargando sedes...</option>
            </select>
          </div>
        </div>

        <!-- Dirección de entrega en sede (Persistente y editable) -->
        <div id="cont-oc-dir-sede">
          <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">Dirección y detalles de entrega para el transportador</label>
          <textarea id="modal-oc-dir-sede" rows="2" placeholder="Ej: Calle 45 # 12-34 - Portón de descargue / timbre 2"
                    class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 bg-white outline-none focus:border-indigo-500"></textarea>
          <span class="text-[9px] text-slate-400">Esta dirección se guardará para esta sede para futuros despachos.</span>
        </div>

        <!-- Dirección de recogida en bodega del proveedor -->
        <div id="cont-oc-dir-recogida" class="hidden">
          <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">Dirección de recogida en bodega del proveedor</label>
          <textarea id="modal-oc-dir-recogida" rows="2" placeholder="Ej: Av. Industrial # 68-20, Muelle 3..."
                    class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 bg-white outline-none focus:border-indigo-500"></textarea>
          <span class="text-[9px] text-slate-400">Quedará guardada en la ficha de este proveedor.</span>
        </div>

        <!-- Pago y WhatsApp -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-200">
          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">💳 Condición de Pago</label>
            <div class="flex gap-2">
              <select id="modal-oc-forma-pago" onchange="cambiarFormaPagoOC()" class="flex-1 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-white outline-none focus:border-indigo-500">
                <option value="contado">Contado / Transferencia</option>
                <option value="contraentrega">Contraentrega en efectivo</option>
                <option value="credito">Crédito a plazos</option>
              </select>
              <select id="modal-oc-dias-credito" class="w-24 border border-slate-200 rounded-lg px-2 py-1.5 text-xs font-bold text-indigo-900 bg-indigo-50 hidden outline-none">
                <option value="8">8 días</option>
                <option value="15" selected>15 días</option>
                <option value="30">30 días</option>
                <option value="45">45 días</option>
                <option value="60">60 días</option>
              </select>
            </div>
          </div>

          <div>
            <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">📱 Teléfono WhatsApp Proveedor</label>
            <input type="text" id="modal-oc-telefono" placeholder="Ej: 3101234567"
                   class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-white outline-none focus:border-indigo-500">
            <span class="text-[9px] text-slate-400">Se usará para enviar el enlace de confirmación por WhatsApp.</span>
          </div>
        </div>

      </div>

      <!-- Tabla Resumen de Ítems a Pedir -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-bold uppercase tracking-wide text-slate-700">📦 Productos en esta Orden</span>
          <span id="modal-oc-cant-items" class="text-[10px] text-slate-500 font-semibold">0 productos</span>
        </div>

        <div class="border border-slate-200 rounded-xl overflow-hidden">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-100 text-slate-600 uppercase font-bold text-[9.5px]">
              <tr>
                <th class="px-3 py-2">Producto</th>
                <th class="px-3 py-2 text-center">Empaque</th>
                <th class="px-3 py-2 text-right">Cant. Pedida</th>
                <th class="px-3 py-2 text-right">Precio Est.</th>
                <th class="px-3 py-2 text-right">Subtotal</th>
              </tr>
            </thead>
            <tbody id="modal-oc-items-body" class="divide-y divide-slate-100 bg-white">
              <!-- Render dinámico -->
            </tbody>
            <tfoot class="bg-slate-50 font-bold border-t border-slate-200 text-xs">
              <tr>
                <td colspan="4" class="px-3 py-2.5 text-right text-slate-600 uppercase">Total Estimado de la Orden:</td>
                <td id="modal-oc-total-val" class="px-3 py-2.5 text-right text-indigo-900 font-black text-sm font-mono">$0</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Observaciones Comprador -->
      <div>
        <label class="block text-[10px] font-bold text-slate-600 uppercase mb-1">Observaciones / Instrucciones para el Proveedor (Opcional)</label>
        <textarea id="modal-oc-observaciones" rows="1" placeholder="Ej: Por favor enviar factura electrónica al correo..."
                  class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-indigo-500 text-slate-800"></textarea>
      </div>

    </div>

    <!-- Modal Footer -->
    <div class="px-5 py-3.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between shrink-0">
      <button onclick="cerrarModalOrdenCompra()" class="px-4 py-2 border border-slate-200 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition">
        Cancelar
      </button>

      <button id="btn-generar-oc-submit" onclick="confirmarYEnviarOC()"
              class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-black text-xs uppercase tracking-wider rounded-xl shadow-md flex items-center gap-2 transition cursor-pointer">
        <span>📲 Generar y Enviar por WhatsApp</span>
      </button>
    </div>

  </div>
</div>
"""

if "</body>" in html:
    html = html.replace("</body>", modal_oc_html + "\n</body>", 1)

# 6. Add JS logic for OC and peso variable
js_logic = """
// =====================================================================
// LÓGICA DE ÓRDENES DE COMPRA (OC) Y TOLERANCIA DE PESO VARIABLE
// =====================================================================

function toggleToleranciaPeso(checked) {
  const cont = document.getElementById('cont-tolerancia-peso');
  if (cont) {
    if (checked) cont.classList.remove('hidden');
    else cont.classList.add('hidden');
  }
}

// Hook al abrir modal de producto
const _orig_abrirModalProducto = window.abrirModalProducto;
window.abrirModalProducto = function(p) {
  if (typeof _orig_abrirModalProducto === 'function') _orig_abrirModalProducto(p);
  const chkPeso = document.getElementById('mp-peso-variable');
  const inpTol = document.getElementById('mp-tolerancia-peso');
  if (chkPeso) chkPeso.checked = p ? !!p.peso_variable : false;
  if (inpTol) inpTol.value = (p && p.tolerancia_peso_pct !== null && p.tolerancia_peso_pct !== undefined) ? p.tolerancia_peso_pct : '10';
  toggleToleranciaPeso(chkPeso ? chkPeso.checked : false);
};

// Variables para el modal de OC
let oc_modal_pIdx = null;
let oc_modal_sedes = [];

async function abrirModalOrdenCompra(pIdx) {
  if (!window.COMPRAS_DATA || !window.COMPRAS_DATA[pIdx]) return;
  const p = window.COMPRAS_DATA[pIdx];
  oc_modal_pIdx = pIdx;

  document.getElementById('modal-oc-prov-nombre').textContent = `Proveedor: ${p.proveedor_nombre}`;
  document.getElementById('modal-oc-telefono').value = p.proveedor_telefono || '';
  document.getElementById('modal-oc-observaciones').value = '';

  // Modalidad por defecto
  const selMod = document.getElementById('modal-oc-modalidad');
  if (selMod) selMod.value = p.modalidad_entrega_defecto || 'sede';

  // Forma de pago por defecto
  const selPago = document.getElementById('modal-oc-forma-pago');
  if (selPago) selPago.value = p.forma_pago_defecto || 'contado';
  const selDias = document.getElementById('modal-oc-dias-credito');
  if (selDias) selDias.value = String(p.dias_credito || 15);
  cambiarFormaPagoOC();

  document.getElementById('modal-oc-dir-recogida').value = p.direccion_recogida || '';

  // Cargar sedes activas
  await cargarSedesParaOC();
  cambiarModalidadEntregaOC();

  // Renderizar ítems
  const tbody = document.getElementById('modal-oc-items-body');
  tbody.innerHTML = '';
  let totalEstimado = 0;

  (p.productos || []).forEach(prod => {
    const cantVal = prod.cantidad_sugerida_usuario || prod.paquetes_sugeridos || 1;
    const precVal = prod.costo_empaque_usuario || prod.precio_presentacion || 0;
    const subtotal = cantVal * precVal;
    totalEstimado += subtotal;

    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-50";
    tr.innerHTML = `
      <td class="px-3 py-2 font-medium text-slate-800">
        ${prod.producto_nombre}
        ${prod.peso_variable ? `<span class="ml-1 text-[9px] bg-amber-100 text-amber-800 font-bold px-1.5 py-0.2 rounded">⚖️ ±${Math.round(prod.tolerancia_peso_pct || 10)}%</span>` : ''}
      </td>
      <td class="px-3 py-2 text-center text-slate-500 font-medium">${prod.presentacion_nombre || 'Unidad'}</td>
      <td class="px-3 py-2 text-right font-bold text-slate-800">${cantVal}</td>
      <td class="px-3 py-2 text-right font-medium text-slate-600">${fmtMonC(precVal)}</td>
      <td class="px-3 py-2 text-right font-black text-indigo-900">${fmtMonC(subtotal)}</td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('modal-oc-cant-items').textContent = `${p.productos.length} producto(s)`;
  document.getElementById('modal-oc-total-val').textContent = fmtMonC(totalEstimado);

  document.getElementById('modal-generar-oc').classList.remove('hidden');
}

function cerrarModalOrdenCompra() {
  document.getElementById('modal-generar-oc').classList.add('hidden');
  oc_modal_pIdx = null;
}

async function cargarSedesParaOC() {
  try {
    const resp = await fetch('/api/centros-utilidad');
    const data = await resp.json();
    if (data.ok && data.centros) {
      oc_modal_sedes = data.centros.filter(c => c.activo !== false);
      const sel = document.getElementById('modal-oc-sede');
      sel.innerHTML = oc_modal_sedes.map(s => `
        <option value="${s.id}">${s.nombre} (${s.codigo || 'Sede'})</option>
      `).join('');

      if (oc_modal_sedes.length > 0) {
        cambiarSedeOC(oc_modal_sedes[0].id);
      }
    }
  } catch (err) {
    console.error('Error cargando sedes para OC:', err);
  }
}

function cambiarSedeOC(sedeId) {
  const sede = oc_modal_sedes.find(s => String(s.id) === String(sedeId));
  const txtDir = document.getElementById('modal-oc-dir-sede');
  if (sede && txtDir) {
    txtDir.value = sede.direccion_entrega || sede.direccion || '';
  }
}

function cambiarModalidadEntregaOC() {
  const mod = document.getElementById('modal-oc-modalidad')?.value;
  const contSede = document.getElementById('cont-oc-sede');
  const contDirSede = document.getElementById('cont-oc-dir-sede');
  const contDirRecogida = document.getElementById('cont-oc-dir-recogida');

  if (mod === 'recoger') {
    contSede?.classList.add('hidden');
    contDirSede?.classList.add('hidden');
    contDirRecogida?.classList.remove('hidden');
  } else {
    contSede?.classList.remove('hidden');
    contDirSede?.classList.remove('hidden');
    contDirRecogida?.classList.add('hidden');
  }
}

function cambiarFormaPagoOC() {
  const fp = document.getElementById('modal-oc-forma-pago')?.value;
  const diasSel = document.getElementById('modal-oc-dias-credito');
  if (fp === 'credito') {
    diasSel?.classList.remove('hidden');
  } else {
    diasSel?.classList.add('hidden');
  }
}

async function confirmarYEnviarOC() {
  if (oc_modal_pIdx === null || !window.COMPRAS_DATA[oc_modal_pIdx]) return;
  const p = window.COMPRAS_DATA[oc_modal_pIdx];
  const btn = document.getElementById('btn-generar-oc-submit');
  if (btn) btn.disabled = true;

  const mod = document.getElementById('modal-oc-modalidad').value;
  const sedeSel = document.getElementById('modal-oc-sede');
  const sedeId = sedeSel ? sedeSel.value : null;
  const sedeNom = sedeSel ? sedeSel.options[sedeSel.selectedIndex]?.text : 'Sede Principal';

  const items = (p.productos || []).map(prod => {
    const cant = prod.cantidad_sugerida_usuario || prod.paquetes_sugeridos || 1;
    const prec = prod.costo_empaque_usuario || prod.precio_presentacion || 0;
    return {
      producto_id: prod.producto_id,
      producto_nombre: prod.producto_nombre,
      presentacion_id: prod.presentacion_id || null,
      presentacion_nombre: prod.presentacion_nombre || 'Unidad',
      unidades_presentacion: prod.unidades_presentacion || 1.0,
      peso_variable: !!prod.peso_variable,
      tolerancia_peso_pct: prod.tolerancia_peso_pct || 10.0,
      cantidad_solicitada: cant,
      precio_unitario: prec,
      total_solicitado: cant * prec
    };
  });

  const payload = {
    proveedor_id: p.proveedor_id,
    modalidad_entrega: mod,
    sede_id: sedeId,
    sede_nombre: sedeNom,
    direccion_entrega: document.getElementById('modal-oc-dir-sede').value.trim(),
    direccion_recogida: document.getElementById('modal-oc-dir-recogida').value.trim(),
    forma_pago: document.getElementById('modal-oc-forma-pago').value,
    dias_credito: parseInt(document.getElementById('modal-oc-dias-credito').value) || 15,
    telefono_proveedor: document.getElementById('modal-oc-telefono').value.trim(),
    observaciones: document.getElementById('modal-oc-observaciones').value.trim(),
    items: items
  };

  try {
    const resp = await fetch(`/api/inventario/${NEGOCIO_ID}/ordenes-compra`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if (res.ok) {
      toast(`✅ Orden ${res.numero_oc} generada con éxito.`);
      cerrarModalOrdenCompra();
      cargarOrdenesCompraNegocio();

      // Abrir WhatsApp con el link
      if (res.whatsapp_url) {
        window.open(res.whatsapp_url, '_blank');
      } else {
        prompt('Orden creada. Comparte este enlace con el proveedor:', res.url_publica);
      }
    } else {
      alert('Error: ' + (res.error || 'No se pudo generar la orden'));
    }
  } catch (err) {
    alert('Error de conexión al generar la orden');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function cargarOrdenesCompraNegocio() {
  const cont = document.getElementById('lista-ordenes-compra');
  if (!cont) return;

  try {
    const resp = await fetch(`/api/inventario/${NEGOCIO_ID}/ordenes-compra`);
    const data = await resp.json();
    if (!data.ok || !data.ordenes || data.ordenes.length === 0) {
      cont.innerHTML = '<p class="text-xs text-slate-400 italic text-center py-4">No hay órdenes de compra registradas aún.</p>';
      return;
    }

    cont.innerHTML = data.ordenes.map(oc => {
      let badgeHtml = '';
      if (oc.estado === 'confirmada') {
        badgeHtml = '<span class="bg-emerald-100 text-emerald-800 border border-emerald-200 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full flex items-center gap-1"><i class="bi bi-check-circle-fill"></i> Confirmada</span>';
      } else if (oc.estado === 'propuesta_cambios') {
        badgeHtml = '<span class="bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full flex items-center gap-1"><i class="bi bi-exclamation-triangle-fill"></i> Propuesta con Cambios</span>';
      } else if (oc.estado === 'recibida') {
        badgeHtml = '<span class="bg-blue-100 text-blue-800 border border-blue-200 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full flex items-center gap-1"><i class="bi bi-box-seam-fill"></i> Recibida en Almacén</span>';
      } else {
        badgeHtml = '<span class="bg-sky-100 text-sky-800 border border-sky-200 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full flex items-center gap-1"><i class="bi bi-clock-fill"></i> Enviada (Esperando)</span>';
      }

      const totalVal = oc.total_confirmado || oc.total_estimado || 0;

      return `
        <div class="bg-white border border-slate-200 rounded-2xl p-4 shadow-2xs hover:shadow-xs transition space-y-3">
          <div class="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div class="flex items-center gap-2">
                <span class="font-mono font-black text-xs text-indigo-700 bg-indigo-50 border border-indigo-150 px-2 py-0.5 rounded-md">${oc.numero_oc}</span>
                <h3 class="text-xs font-bold text-slate-900">${oc.proveedor_nombre}</h3>
                ${badgeHtml}
              </div>
              <p class="text-[11px] text-slate-500 mt-1">
                📅 Emitida: <b>${oc.fecha_emision_str}</b> • 📦 ${oc.items_count} producto(s)
                ${oc.fecha_entrega_str ? `• 🚚 Entrega estimada: <b class="text-indigo-900">${oc.fecha_entrega_str}</b>` : ''}
              </p>
            </div>

            <div class="text-right">
              <span class="text-[10px] uppercase font-bold text-slate-500 block">Total Orden</span>
              <span class="font-mono font-black text-sm text-slate-900">${fmtMonC(totalVal)}</span>
            </div>
          </div>

          <div class="border-t border-slate-100 pt-3 flex items-center justify-between gap-2 flex-wrap text-xs">
            <div class="flex items-center gap-2">
              ${oc.conversacion_token ? `
                <a href="/chat/${oc.conversacion_token}" target="_blank"
                   class="px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 text-indigo-700 font-bold rounded-lg border border-slate-200 hover:border-indigo-200 flex items-center gap-1 transition shadow-2xs">
                  💬 Abrir Chat
                </a>
              ` : ''}

              <button onclick="copiarLinkPublicoOC('${oc.token_publico}')"
                      class="px-2.5 py-1.5 text-slate-600 hover:text-slate-800 font-medium text-[11px] flex items-center gap-1 cursor-pointer">
                📋 Copiar Link Proveedor
              </button>
            </div>

            <div class="flex items-center gap-2">
              ${oc.estado === 'propuesta_cambios' ? `
                <button onclick="aprobarPropuestaCambiosOC(${oc.id})"
                        class="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-lg shadow-sm flex items-center gap-1 cursor-pointer">
                  ✅ Aprobar Cambios
                </button>
              ` : ''}

              ${oc.estado !== 'recibida' ? `
                <button onclick="recibirOrdenEnEntradas(${oc.id})"
                        class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg shadow-sm flex items-center gap-1 cursor-pointer">
                  📥 Recibir en Almacén (Entrada)
                </button>
              ` : `
                <span class="text-[11px] text-emerald-700 font-bold flex items-center gap-1">
                  <i class="bi bi-check2-all text-sm"></i> Mercancía ingresada al inventario
                </span>
              `}
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    cont.innerHTML = '<p class="text-xs text-rose-500 italic text-center py-4">Error cargando órdenes de compra.</p>';
  }
}

function copiarLinkPublicoOC(token) {
  const url = `${window.location.origin}/oc/${token}`;
  navigator.clipboard.writeText(url).then(() => {
    toast('📋 Link del proveedor copiado al portapapeles.');
  });
}

async function aprobarPropuestaCambiosOC(ordenId) {
  if (!confirm('¿Deseas aceptar los cambios de cantidades y/o precios propuestos por el proveedor?')) return;
  try {
    const resp = await fetch(`/api/inventario/${NEGOCIO_ID}/ordenes-compra/${ordenId}/aprobar-cambios`, { method: 'POST' });
    const res = await resp.json();
    if (res.ok) {
      toast('✅ Cambios aprobados. La orden quedó confirmada.');
      cargarOrdenesCompraNegocio();
    } else {
      alert('Error: ' + res.error);
    }
  } catch (e) {
    alert('Error de conexión');
  }
}

async function recibirOrdenEnEntradas(ordenId) {
  try {
    const resp = await fetch(`/api/inventario/${NEGOCIO_ID}/ordenes-compra/${ordenId}/datos-entrada`);
    const data = await resp.json();
    if (!data.ok) {
      alert('Error: ' + data.error);
      return;
    }

    // Inyectar en el formulario de la pestaña Entradas
    const contLineas = document.getElementById('entrada-lineas');
    if (contLineas) contLineas.innerHTML = '';
    entradaLineas = [];

    const inpProvId = document.getElementById('entrada-proveedor-id');
    if (inpProvId) inpProvId.value = data.proveedor.proveedor_id || '';

    const inpProvNom = document.getElementById('entrada-proveedor');
    if (inpProvNom) inpProvNom.value = data.proveedor.proveedor_nombre || '';

    const inpDoc = document.getElementById('entrada-num-doc');
    if (inpDoc) inpDoc.value = data.documento || '';

    const inpFecha = document.getElementById('entrada-fecha-doc');
    if (inpFecha) inpFecha.value = data.fecha || '';

    (data.productos || []).forEach(prod => {
      agregarLineaEntradaConDatos(
        prod.producto_id,
        prod.producto_nombre,
        prod.cantidad_sugerida_unidades,
        prod.costo_unitario,
        prod.iva_pct || 0,
        prod.presentacion_id,
        prod.presentacion_nombre,
        prod.unidades_presentacion,
        prod.cantidad_sugerida_usuario,
        prod.costo_empaque_usuario,
        prod.total_costo
      );
    });

    calcularTotalesEntrada();
    mostrarTab('entradas');
    toast(`✅ Datos de la orden ${data.documento} transferidos a Entradas para su recepción.`);
  } catch (e) {
    alert('Error cargando datos para recepción: ' + e);
  }
}

// Cargar órdenes cuando se abra la pestaña de compras
const _orig_mostrarTab = window.mostrarTab;
window.mostrarTab = function(tabName) {
  if (typeof _orig_mostrarTab === 'function') _orig_mostrarTab(tabName);
  if (tabName === 'compras_sugerencias') {
    cargarOrdenesCompraNegocio();
  }
};
"""

if "</body>" in html:
    html = html.replace("</body>", f"<script>\n{js_logic}\n</script>\n</body>", 1)

with open("templates/inventario_admin.html", "w", encoding="utf-8") as f:
    f.write(html)

print("inventario_admin.html updated successfully.")
