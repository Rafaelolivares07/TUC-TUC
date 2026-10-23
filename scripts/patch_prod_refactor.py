import sys, os

def patch_backend():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\inventarios.py'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    old_ret = """        return jsonify({
            'ok': True,
            'producto_id': producto_id,
            'producto': producto['nombre'],
            'bodega': bodega_id,
            'modo': modo,
            'componentes': items,
            'limitante_id': limitante['id'],
            'guia_id': guia['id'],
            'sugerida': sugerida,
            'derivada': derivada,
            'tope_maximo': limitante['max_qty'],
            'excede_stock_guia': excede,
        })"""

    new_ret = """        return jsonify({
            'ok': True,
            'producto_id': producto_id,
            'producto': producto['nombre'],
            'bodega': bodega_id,
            'modo': modo,
            'componentes': items,
            'limitante_id': limitante['id'],
            'limitante_nombre': limitante['nombre'],
            'limitante_stock': limitante['stock'],
            'limitante_max_qty': limitante['max_qty'],
            'guia_id': guia['id'],
            'guia_nombre': guia['nombre'],
            'guia_stock': guia['stock'],
            'guia_max_qty': guia['max_qty'],
            'sugerida': sugerida,
            'derivada': derivada,
            'tope_maximo': limitante['max_qty'],
            'excede_stock_guia': excede,
        })"""

    if old_ret in c:
        c = c.replace(old_ret, new_ret, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c)
        print("Backend inventarios.py patched with limitante details")
    else:
        print("Backend target block already updated or not found")


def patch_frontend():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\inventario_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # 1. Rename 'Cantidad a producir' to 'Cantidad a Simular'
    old_label = """              <span><span>🔢</span> Cantidad a producir <span class="text-rose-500">*</span></span>
              <span class="text-[10px] font-bold text-slate-500 normal-case">Calcula toda la receta</span>"""
    new_label = """              <span><span>🔢</span> Cantidad a Simular <span class="text-rose-500">*</span></span>
              <span class="text-[10px] font-bold text-slate-500 normal-case">Calcula receta teórica</span>"""
    if old_label in c:
        c = c.replace(old_label, new_label, 1)
        print("Renamed to Cantidad a Simular")

    # 2. Replace #prod-sugerencia HTML with the Compact Warning Bar and Collapsible Body
    # Find from '<div id="prod-sugerencia"' to '<!-- Botón Generar Vista Previa -->'
    start_marker = '<div id="prod-sugerencia"'
    end_marker = '<!-- Botón Generar Vista Previa -->'

    s_idx = c.find(start_marker)
    e_idx = c.find(end_marker)

    if s_idx != -1 and e_idx != -1:
        # Also remove the '<!-- Botón Generar Vista Previa -->' container
        btn_end_marker = '</div>\n\n      </div>\n    </div>\n\n    <div id="prod-preview"'
        btn_end_idx = c.find(btn_end_marker, e_idx)

        new_sug_and_no_btn = """<div id="prod-sugerencia" class="hidden mb-3 rounded-xl border border-amber-300 bg-gradient-to-r from-amber-50/95 via-yellow-50/90 to-amber-50/70 p-3.5 shadow-2xs transition-all">
          
          <!-- Barra fija de Advertencia y Tope Real (Siempre visible) -->
          <div class="flex flex-wrap items-center justify-between gap-2.5 text-xs">
            <div class="flex items-center gap-2">
              <span class="text-lg">⚡</span>
              <div>
                <span class="font-bold text-amber-950 text-xs sm:text-sm">
                  Tope máximo por inventario: <span id="prod-sug-max-real" class="font-mono font-black text-amber-900 text-sm sm:text-base">0</span> und
                </span>
                <p class="text-[11px] text-amber-900/80 font-normal">
                  Insumo limitante: <b id="prod-sug-limita-nombre" class="text-amber-950">-</b> (Stock en bodega: <span id="prod-sug-limita-stock" class="font-mono font-bold">0</span>)
                </p>
              </div>
            </div>
            
            <div class="flex items-center gap-2">
              <span id="prod-sug-sim-info" class="hidden text-[11px] font-bold text-amber-900 bg-amber-200/80 px-2.5 py-1 rounded-lg border border-amber-300 shadow-2xs"></span>
              <button type="button" id="btn-toggle-mp-sim" onclick="toggleSimulacionMP()" class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-300 bg-white hover:bg-amber-100 text-amber-900 font-bold text-xs transition shadow-2xs cursor-pointer">
                <span>🧪 Simular por Materia Prima</span>
                <span id="prod-mp-toggle-icon" class="text-[10px] transition-transform">▼</span>
              </button>
            </div>
          </div>

          <!-- Cuerpo Desplegable de Simulación por Materia Prima (Colapsado por defecto) -->
          <div id="prod-sugerencia-body" class="hidden mt-3 pt-3 border-t border-amber-200/80 space-y-3">
            
            <!-- 1. Ingrediente Guía a Ancho Completo -->
            <div>
              <div class="flex items-center justify-between gap-2 mb-1">
                <label class="text-xs font-black text-slate-800 uppercase tracking-wide">
                  1. Ingrediente Guía (Materia Prima)
                </label>
                <span id="prod-sug-stock-guia-badge" class="text-[11px] font-mono font-bold text-amber-900 bg-amber-100 px-2 py-0.5 rounded-lg border border-amber-300"></span>
              </div>
              <select id="prod-sug-guia" onchange="sugerenciaCambioGuia()" onwheel="this.blur()" class="w-full border-2 border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-bold text-slate-900 outline-none shadow-sm focus:border-amber-500 cursor-pointer"></select>
              <div class="flex items-center justify-between gap-2 mt-1.5 flex-wrap">
                <p id="prod-sug-guia-helper" class="text-[11px] text-amber-900 font-semibold leading-tight"></p>
                <span class="text-[10px] text-slate-500 font-medium italic">⚡ Por defecto calcula usando todo el stock disponible de esta materia prima</span>
              </div>
            </div>

            <!-- 2. Variación / Simulación de MP -->
            <div class="pt-2 border-t border-amber-200/60">
              <label class="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">
                2. ¿Vas a usar una cantidad diferente de MP? <span class="font-normal text-slate-500 lowercase">(opcional)</span>
              </label>
              <div class="flex items-center gap-2">
                <input id="prod-sug-mp-cant" type="number" min="0" step="any" placeholder="Digita cant. a usar" onkeydown="if(event.key==='Enter'){event.preventDefault();sugerenciaDesdeMP();}" class="w-40 border border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-mono font-black text-slate-900 text-right outline-none shadow-sm focus:border-amber-500">
                <span id="prod-sug-mp-nombre" class="text-xs text-slate-600 font-semibold truncate max-w-[150px]"></span>
                <button type="button" onclick="sugerenciaDesdeMP()" class="px-3.5 py-2 rounded-xl border border-amber-400 bg-amber-500 hover:bg-amber-600 active:scale-95 text-white font-bold text-xs transition shadow-xs whitespace-nowrap">
                  Recalcular Insumos
                </button>
              </div>
            </div>

            <!-- Micro-guía explicativa para el usuario -->
            <div class="flex items-start gap-1.5 text-[11px] text-amber-900/90 bg-amber-100/50 rounded-lg px-3 py-1.5 border border-amber-200/50">
              <span class="text-xs">💡</span>
              <span><b>Flujo por Materia Prima:</b> 1) Elige el ingrediente guía, 2) digita cuánto vas a procesar si no es todo el stock y pulsa <b>Recalcular Insumos</b>. Toda la receta se ajustará en vivo.</span>
            </div>

          </div>

        </div>"""

        if btn_end_idx != -1:
            c = c[:s_idx] + new_sug_and_no_btn + c[btn_end_idx:]
            print("Replaced prod-sugerencia and removed Generar Vista Previa button")
        else:
            print("btn_end_marker not found, checking alternative")

    # 3. Update renderSugerencia in JS and add toggleSimulacionMP
    old_render_js = """function renderSugerencia(autoPreview = true) {
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
  }"""

    new_render_js = """function toggleSimulacionMP() {
  const body = document.getElementById('prod-sugerencia-body');
  const icon = document.getElementById('prod-mp-toggle-icon');
  if (!body) return;
  const colapsado = body.classList.contains('hidden');
  if (colapsado) {
    body.classList.remove('hidden');
    if (icon) icon.textContent = '▲';
  } else {
    body.classList.add('hidden');
    if (icon) icon.textContent = '▼';
  }
}

function renderSugerencia(autoPreview = true) {
  const d = prodSugerenciaData;
  if (!d) return;
  const comps = d.componentes || [];
  const guia = comps.find(c => c.id === d.guia_id) || comps[0] || {};
  const lim = comps.find(c => c.id === d.limitante_id) || comps[0] || {};
  const prodNombre = d.producto || 'producto a fabricar';

  // 1. Cabecera fija: El tope máximo real según el insumo limitante (cuello de botella de inventario)
  const maxReal = (d.tope_maximo !== undefined && d.tope_maximo !== null) ? d.tope_maximo : (lim.max_qty || 0);
  const maxRealEl = document.getElementById('prod-sug-max-real');
  if (maxRealEl) maxRealEl.textContent = _fmtProdNum(maxReal);

  const limNombreEl = document.getElementById('prod-sug-limita-nombre');
  if (limNombreEl) limNombreEl.textContent = d.limitante_nombre || lim.nombre || '-';

  const limStockEl = document.getElementById('prod-sug-limita-stock');
  if (limStockEl) limStockEl.textContent = _fmtProdNum(d.limitante_stock !== undefined ? d.limitante_stock : lim.stock);

  // 2. Información de simulación activa (si está en modo desde_mp)
  const simInfoEl = document.getElementById('prod-sug-sim-info');
  if (simInfoEl) {
    if (d.modo === 'desde_mp') {
      const cantMP = parseFloat(document.getElementById('prod-sug-mp-cant').value) || 0;
      simInfoEl.innerHTML = `🔬 Simulación: <b>${_fmtProdNum(cantMP)}</b> de <i>${guia.nombre}</i> → Esperado: <b>${_fmtProdNum(d.sugerida)} und</b>`;
      simInfoEl.classList.remove('hidden');
    } else {
      simInfoEl.classList.add('hidden');
    }
  }"""

    if old_render_js in c:
        c = c.replace(old_render_js, new_render_js, 1)
        print("Updated renderSugerencia and added toggleSimulacionMP")
    else:
        print("old_render_js not found")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)

    print("Frontend inventario_admin.html patched successfully")

if __name__ == '__main__':
    patch_backend()
    patch_frontend()
