import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'inventario_admin.html')
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update prod-fecha block to be strictly readonly and locked to current date
t1 = '''          <div>
            <label class="block text-sm font-bold text-slate-600 uppercase tracking-wide mb-1.5">Fecha documento</label>
            <input id="prod-fecha" type="date" class="w-full border-2 border-slate-200 rounded-xl px-3.5 py-2.5 text-sm sm:text-base bg-white font-semibold text-slate-800 outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition">
            <div id="aviso-prod-reemplazo" class="hidden mt-1.5 text-xs font-bold text-amber-900 bg-amber-50 border border-amber-300 rounded-xl p-2 cursor-pointer hover:bg-amber-100 transition shadow-xs flex items-center justify-between" onclick="aplicarFechaProduccionReemplazo()">
              <span>⚠️ Reemplazo de producción: Clic para aplicar fecha original (<b id="aviso-prod-reemplazo-fecha"></b>)</span>
              <span class="text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded-lg shrink-0">Usar</span>
            </div>
          </div>'''

r1 = '''          <div>
            <label class="block text-sm font-bold text-slate-600 uppercase tracking-wide mb-1.5 flex items-center justify-between">
              <span>Fecha documento</span>
              <span class="text-[10px] font-extrabold text-emerald-700 bg-emerald-100 border border-emerald-300 px-2 py-0.5 rounded-full">🔒 Solo Fecha Actual</span>
            </label>
            <input id="prod-fecha" type="date" readonly tabindex="-1" class="w-full border-2 border-slate-200 rounded-xl px-3.5 py-2.5 text-sm sm:text-base bg-slate-100 font-bold text-slate-600 cursor-not-allowed outline-none select-none">
            <div id="aviso-prod-reemplazo" class="hidden"></div>
          </div>'''

# 2. Add Historial de Recosteos table in tab-recosteo
t2 = '''    <div id="recosteo-lista" class="border border-gray-100 rounded-xl divide-y divide-gray-100 overflow-hidden">

      <p class="text-sm text-gray-400 text-center py-8">Cargando auditoría...</p>

    </div>

  </div>'''

r2 = '''    <div id="recosteo-lista" class="border border-gray-100 rounded-xl divide-y divide-gray-100 overflow-hidden">

      <p class="text-sm text-gray-400 text-center py-8">Cargando auditoría...</p>

    </div>

    <!-- Historial y Registro de Procesos de Recosteo -->
    <div class="mt-8 pt-5 border-t border-gray-200">
      <div class="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 class="text-sm font-extrabold text-gray-800 flex items-center gap-1.5">
            <span>📋</span> Historial y Registro de Procesos de Recosteo
          </h3>
          <p class="text-xs text-gray-500">Auditoría detallada de cuándo, quién y qué documento o producto ejecutó un recosteo.</p>
        </div>
        <button type="button" onclick="cargarHistorialRecosteos()" class="px-3 py-1.5 rounded-xl border border-gray-200 text-xs font-bold text-gray-700 hover:bg-gray-50 flex items-center gap-1 shadow-2xs">
          🔄 Actualizar registro
        </button>
      </div>

      <div class="overflow-x-auto border border-gray-200 rounded-xl shadow-xs bg-white">
        <table class="w-full text-left text-xs">
          <thead class="bg-gray-50 text-[11px] uppercase tracking-wider text-gray-500 border-b border-gray-200">
            <tr>
              <th class="px-3 py-2.5">Fecha y Hora</th>
              <th class="px-3 py-2.5">Producto</th>
              <th class="px-3 py-2.5">Origen / Proceso</th>
              <th class="px-3 py-2.5">Documento</th>
              <th class="px-3 py-2.5">Responsable</th>
              <th class="px-3 py-2.5 text-right">Costo Antes</th>
              <th class="px-3 py-2.5 text-right">Costo Nuevo</th>
              <th class="px-3 py-2.5 text-center">Movs Ajustados</th>
            </tr>
          </thead>
          <tbody id="historial-recosteos-body" class="divide-y divide-gray-100">
            <tr><td colspan="8" class="text-center py-6 text-gray-400 italic">Cargando historial de recosteos...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>'''

# 3. Add JS functions for cargarHistorialRecosteos and call it in mostrarTab('recosteo')
t3 = '''  if (t === 'recosteo') {

    cargarAuditoriaRecosteo();

  }'''

r3 = '''  if (t === 'recosteo') {

    cargarAuditoriaRecosteo();
    cargarHistorialRecosteos();

  }'''

t4 = '''function aplicarFechaProduccionReemplazo() {
  const raw = sessionStorage.getItem('tuctuc_produccion_reemplazo');
  if (!raw) return;
  try {
    const data = JSON.parse(raw);
    if (data && data.fecha) {
      const el = document.getElementById('prod-fecha');
      if (el) {
        el.value = data.fecha;
        el.classList.add('ring-4', 'ring-amber-300');
        setTimeout(() => el.classList.remove('ring-4', 'ring-amber-300'), 1500);
        toast(`Fecha original (${data.fecha}) aplicada al documento.`);
      }
    }
  } catch(e) {}
}'''

r4 = '''function aplicarFechaProduccionReemplazo() {
  toast('La fecha de producción está bloqueada estrictamente a la fecha actual.', false);
}

async function cargarHistorialRecosteos() {
  const tbody = document.getElementById('historial-recosteos-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-gray-400 italic">Cargando historial de recosteos...</td></tr>';
  try {
    const r = await fetch(`/api/inventario/${NEGOCIO_ID}/recosteo/historial?limite=50`);
    const d = await r.json();
    if (!d.ok || !d.historial || !d.historial.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-gray-400 italic">No hay registros de recosteo recientes.</td></tr>';
      return;
    }
    tbody.innerHTML = d.historial.map(h => {
      const origLabels = {
        'manual_kardex': '<span class="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-bold text-[10px]">Manual Kardex</span>',
        'recosteo_global': '<span class="bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full font-bold text-[10px]">Recosteo Global</span>',
        'produccion': '<span class="bg-amber-50 text-amber-800 px-2 py-0.5 rounded-full font-bold text-[10px]">Producción</span>',
        'compra': '<span class="bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded-full font-bold text-[10px]">Factura Compra</span>',
        'ajuste': '<span class="bg-rose-50 text-rose-800 px-2 py-0.5 rounded-full font-bold text-[10px]">Ajuste Inv.</span>',
        'anulacion_produccion': '<span class="bg-red-50 text-red-800 px-2 py-0.5 rounded-full font-bold text-[10px]">Anulación Prod.</span>'
      };
      const origBadge = origLabels[h.origen] || `<span class="bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full font-bold text-[10px]">${h.origen || 'Sistema'}</span>`;
      const docStr = (h.documento_tipo || h.documento_numero) ? `${h.documento_tipo || ''} #${h.documento_numero || ''}`.trim() : '—';
      const cantAjust = h.movimientos_afectados > 0 ? `<span class="font-bold text-amber-600">${h.movimientos_afectados}</span>` : '<span class="text-gray-400">0</span>';
      return `
        <tr class="hover:bg-slate-50 transition">
          <td class="px-3 py-2 font-mono text-gray-700 whitespace-nowrap">${h.fecha_hora}</td>
          <td class="px-3 py-2 font-bold text-gray-900">${h.producto_nombre || 'Producto #' + h.producto_id}</td>
          <td class="px-3 py-2">${origBadge}</td>
          <td class="px-3 py-2 font-mono text-gray-600">${docStr}</td>
          <td class="px-3 py-2 text-gray-700">${h.usuario_nombre || 'Sistema'}</td>
          <td class="px-3 py-2 text-right font-mono text-gray-500">$${(Number(h.costo_anterior) || 0).toLocaleString('es-CO', {minimumFractionDigits: 2, maximumFractionDigits: 4})}</td>
          <td class="px-3 py-2 text-right font-mono font-bold text-gray-800">$${(Number(h.costo_nuevo) || 0).toLocaleString('es-CO', {minimumFractionDigits: 2, maximumFractionDigits: 4})}</td>
          <td class="px-3 py-2 text-center">${cantAjust}</td>
        </tr>
      `;
    }).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-red-500 font-bold">Error cargando historial: ${e.message}</td></tr>`;
  }
}'''

# Normalize
content_norm = content.replace('\r\n', '\n')
replacements = [
    (t1, r1, "t1 prod-fecha readonly"),
    (t2, r2, "t2 recosteo table"),
    (t3, r3, "t3 tab recosteo trigger"),
    (t4, r4, "t4 cargarHistorialRecosteos js")
]

for t, r, name in replacements:
    t_norm = t.replace('\r\n', '\n')
    r_norm = r.replace('\r\n', '\n')
    if t_norm in content_norm:
        content_norm = content_norm.replace(t_norm, r_norm, 1)
        print(f"OK: {name}")
    else:
        print(f"ERROR: {name} not found!")

if '\r\n' in content:
    content_norm = content_norm.replace('\n', '\r\n')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content_norm)
print("Finished patching inventario_admin.html")
