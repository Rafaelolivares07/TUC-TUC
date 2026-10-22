import sys, os

def patch():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\inventario_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # 1. Update HTML controls in prod-sugerencia
    old_html = """          <!-- Controles de simulación por materia prima -->
          <div class="bg-white/80 border border-amber-200/90 rounded-xl p-3 mb-2.5 shadow-2xs">
            <div class="flex flex-wrap items-center gap-2.5 text-xs">
              <div class="flex flex-col">
                <label class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-1">1. Ingrediente Guía (Materia Prima)</label>
                <select id="prod-sug-guia" onchange="sugerenciaCambioGuia()" onwheel="this.blur()" class="border border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-bold text-slate-800 outline-none shadow-sm focus:border-amber-500 cursor-pointer"></select>
              </div>
              <div class="flex flex-col">
                <label class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-1">2. Cantidad MP a consumir</label>
                <div class="flex items-center gap-2">
                  <input id="prod-sug-mp-cant" type="number" min="0" step="any" placeholder="máx stock" onkeydown="if(event.key==='Enter'){event.preventDefault();sugerenciaDesdeMP();}" class="w-36 border border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-mono font-black text-slate-900 text-right outline-none shadow-sm focus:border-amber-500">
                  <span id="prod-sug-mp-nombre" class="text-xs sm:text-sm text-slate-600 font-semibold truncate max-w-[160px]"></span>
                </div>
              </div>
              <div class="flex items-end gap-2 pt-3 sm:pt-0">
                <button type="button" onclick="sugerenciaDesdeMP()" class="px-4 py-2 rounded-xl border border-amber-400 bg-amber-500 hover:bg-amber-600 text-white font-bold text-sm transition shadow">
                  Recalcular Insumos
                </button>
                <button type="button" onclick="sugerenciaUsarMaximo()" class="px-3.5 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-bold text-sm transition shadow-sm">
                  Usar Máximo
                </button>
              </div>"""

    new_html = """          <!-- Controles de simulación por materia prima -->
          <div class="bg-white/80 border border-amber-200/90 rounded-xl p-3 mb-2.5 shadow-2xs">
            <div class="flex flex-wrap items-start gap-3 text-xs">
              <div class="flex flex-col flex-1 min-w-[280px]">
                <label class="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1 flex items-center justify-between">
                  <span>1. Ingrediente Guía (Materia Prima)</span>
                  <span id="prod-sug-stock-guia-badge" class="text-[11px] font-mono font-bold text-amber-900 bg-amber-100 px-2 py-0.5 rounded border border-amber-300"></span>
                </label>
                <select id="prod-sug-guia" onchange="sugerenciaCambioGuia()" onwheel="this.blur()" class="w-full border border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-bold text-slate-800 outline-none shadow-sm focus:border-amber-500 cursor-pointer"></select>
                <p id="prod-sug-guia-helper" class="text-[11px] text-amber-900 font-medium mt-1.5 leading-tight"></p>
              </div>
              <div class="flex flex-col">
                <label class="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">2. Cantidad MP a consumir</label>
                <div class="flex items-center gap-2">
                  <input id="prod-sug-mp-cant" type="number" min="0" step="any" placeholder="Ej. 1000" onkeydown="if(event.key==='Enter'){event.preventDefault();sugerenciaDesdeMP();}" class="w-36 border border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-mono font-black text-slate-900 text-right outline-none shadow-sm focus:border-amber-500">
                  <span id="prod-sug-mp-nombre" class="text-xs sm:text-sm text-slate-600 font-semibold truncate max-w-[150px]"></span>
                </div>
                <div class="flex items-center gap-1.5 mt-2">
                  <button type="button" onclick="sugerenciaDesdeMP()" class="px-3 py-1.5 rounded-xl border border-amber-400 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs transition shadow-xs">
                    Recalcular Insumos
                  </button>
                  <button type="button" onclick="sugerenciaUsarMaximo()" class="px-2.5 py-1.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs transition shadow-xs">
                    Usar Todo el Stock
                  </button>
                </div>
              </div>"""

    if old_html in c:
        c = c.replace(old_html, new_html, 1)
        print("HTML controls replaced successfully")
    else:
        print("HTML controls block not found")

    # 2. Update renderSugerencia and sugerenciaUsarMaximo in JS
    old_js = """function renderSugerencia(autoPreview = true) {
  const d = prodSugerenciaData;
  if (!d) return;
  const comps = d.componentes || [];
  const guia = comps.find(c => c.id === d.guia_id) || {};
  const lim = comps.find(c => c.id === d.limitante_id) || {};
  document.getElementById('prod-sug-max').textContent = _fmtProdNum(d.sugerida);
  if (d.modo === 'desde_mp') {
    const cantMP = parseFloat(document.getElementById('prod-sug-mp-cant').value) || 0;
    document.getElementById('prod-sug-limita').textContent = `Simulación activa: ${_fmtProdNum(cantMP)} de ${guia.nombre || 'guía'} → Esperado: ${_fmtProdNum(d.sugerida)} und`;
  } else {
    document.getElementById('prod-sug-limita').textContent = `Insumo limitante: ${lim.nombre || '-'} (Stock: ${_fmtProdNum(lim.stock)})`;
  }
  const sel = document.getElementById('prod-sug-guia');
  sel.innerHTML = comps.map(c => `<option value="${c.id}"${c.id === d.guia_id ? ' selected' : ''}>${c.nombre} → Permite hasta ${_fmtProdNum(c.max_qty)} und</option>`).join('');
  document.getElementById('prod-sug-mp-nombre').textContent = guia.nombre ? `de ${guia.nombre}` : '';
  document.getElementById('prod-cantidad').value = d.sugerida;
  const sugRealEl = document.getElementById('prod-sug-real-cant');
  if (sugRealEl) sugRealEl.value = d.sugerida;
  document.getElementById('prod-sugerencia').classList.remove('hidden');
  if (autoPreview && d.sugerida > 0) {
    previsualizarProduccion(false, false);
  } else {
    limpiarPreview();
  }
}"""

    new_js = """function renderSugerencia(autoPreview = true) {
  const d = prodSugerenciaData;
  if (!d) return;
  const comps = d.componentes || [];
  const guia = comps.find(c => c.id === d.guia_id) || comps[0] || {};
  const lim = comps.find(c => c.id === d.limitante_id) || comps[0] || {};
  const prodNombre = d.producto || 'producto a fabricar';

  document.getElementById('prod-sug-max').textContent = _fmtProdNum(d.sugerida);
  if (d.modo === 'desde_mp') {
    const cantMP = parseFloat(document.getElementById('prod-sug-mp-cant').value) || 0;
    document.getElementById('prod-sug-limita').textContent = `Simulación: ${_fmtProdNum(cantMP)} de ${guia.nombre || 'guía'} → Rinde para: ${_fmtProdNum(d.sugerida)} und de ${prodNombre}`;
  } else {
    document.getElementById('prod-sug-limita').textContent = `Insumo limitante: ${lim.nombre || '-'} (Stock: ${_fmtProdNum(lim.stock)})`;
  }

  // 1. Opciones del selector: Mostrar el nombre de la MP y su stock disponible en bodega
  const sel = document.getElementById('prod-sug-guia');
  sel.innerHTML = comps.map(c => {
    const esSel = (c.id === d.guia_id);
    return `<option value="${c.id}"${esSel ? ' selected' : ''}>${c.nombre} (Stock en bodega: ${_fmtProdNum(c.stock)})</option>`;
  }).join('');

  // 2. Badge de stock de la materia prima seleccionada
  const stockBadge = document.getElementById('prod-sug-stock-guia-badge');
  if (stockBadge) {
    stockBadge.textContent = `Stock disponible: ${_fmtProdNum(guia.stock)}`;
  }

  // 3. Explicación clara de rendimiento: cuánto producto final permite fabricar
  const helperEl = document.getElementById('prod-sug-guia-helper');
  if (helperEl) {
    helperEl.innerHTML = `💡 Con tu stock de <b>${guia.nombre}</b> (${_fmtProdNum(guia.stock)}) puedes fabricar hasta: <span class="text-amber-950 font-black">${_fmtProdNum(guia.max_qty)} und</span> de <i>${prodNombre}</i>.`;
  }

  // 4. Placeholder del input MP
  const mpCantInput = document.getElementById('prod-sug-mp-cant');
  if (mpCantInput && !mpCantInput.value) {
    mpCantInput.placeholder = `Máx: ${_fmtProdNum(guia.stock)}`;
  }
  document.getElementById('prod-sug-mp-nombre').textContent = guia.nombre ? `de ${guia.nombre}` : '';

  // 5. Asignar cantidad esperada a producir
  document.getElementById('prod-cantidad').value = d.sugerida;
  const sugRealEl = document.getElementById('prod-sug-real-cant');
  if (sugRealEl) sugRealEl.value = d.sugerida;

  document.getElementById('prod-sugerencia').classList.remove('hidden');
  if (autoPreview && d.sugerida > 0) {
    previsualizarProduccion(false, false);
  } else {
    limpiarPreview();
  }
}"""

    if old_js in c:
        c = c.replace(old_js, new_js, 1)
        print("renderSugerencia JS replaced successfully")
    else:
        print("renderSugerencia JS block not found")

    old_usar_max = """function sugerenciaUsarMaximo() {
  document.getElementById('prod-sug-mp-cant').value = '';
  sugerenciaCambioGuia();
}"""

    new_usar_max = """function sugerenciaUsarMaximo() {
  const d = prodSugerenciaData;
  if (d && d.componentes) {
    const guia = d.componentes.find(c => c.id === d.guia_id) || d.componentes[0];
    if (guia && guia.stock > 0) {
      document.getElementById('prod-sug-mp-cant').value = guia.stock;
      sugerenciaDesdeMP();
      return;
    }
  }
  document.getElementById('prod-sug-mp-cant').value = '';
  sugerenciaCambioGuia();
}"""

    if old_usar_max in c:
        c = c.replace(old_usar_max, new_usar_max, 1)
        print("sugerenciaUsarMaximo JS replaced successfully")
    else:
        print("sugerenciaUsarMaximo JS block not found")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print("Done patching inventario_admin.html")

if __name__ == '__main__':
    patch()
