import sys, os

def patch():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\inventario_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # 1. Fix header icon ?? to 🏭
    old_h2_icon = """<span class="w-8 h-8 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center text-base shadow-2xs">??</span>"""
    new_h2_icon = """<span class="w-8 h-8 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center text-base shadow-2xs">🏭</span>"""
    if old_h2_icon in c:
        c = c.replace(old_h2_icon, new_h2_icon, 1)
        print("Header icon fixed")

    # 2. Fix historial toggle icon and text
    old_hist = """<span id="historial-toggle-icon">?</span><span>??</span> Historial Reciente de Producci?n"""
    new_hist = """<span id="historial-toggle-icon">▼</span><span>📋</span> Historial Reciente de Producción"""
    if old_hist in c:
        c = c.replace(old_hist, new_hist, 1)
        print("Historial text fixed to clean text and emoji")

    # 3. Replace upper Fila 3 (remove prod-notas from top, leave clean 'Generar Vista Previa' button)
    old_fila3 = """        <!-- Fila 3: Notas y Botón Generar Vista Previa con tipografía destacada -->
        <div class="flex flex-col sm:flex-row items-end gap-4 pt-1">
          <div class="w-full sm:flex-1">
            <label class="block text-sm font-bold text-slate-600 uppercase tracking-wide mb-1.5">Notas u observaciones (opcional)</label>
            <input id="prod-notas" type="text" placeholder="Ej. Lote matutino, ajuste de fórmula..." class="w-full border-2 border-slate-200 rounded-xl px-3.5 py-2.5 text-sm sm:text-base bg-white text-slate-800 outline-none focus:border-rose-400 focus:ring-1 focus:ring-rose-300 transition">
          </div>
          <div class="w-full sm:w-auto">
            <button type="button" onclick="previsualizarProduccion(true, true)" class="w-full sm:w-auto px-7 py-3 rounded-xl bg-gradient-to-r from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 text-white font-bold text-sm sm:text-base flex items-center justify-center gap-2 shadow hover:shadow-md transition transform active:scale-98">
              <span>👁️</span> Generar Vista Previa
            </button>
          </div>
        </div>"""

    new_fila3 = """        <!-- Botón Generar Vista Previa -->
        <div class="flex justify-end pt-2">
          <button type="button" onclick="previsualizarProduccion(true, true)" class="w-full sm:w-auto px-8 py-3 rounded-xl bg-gradient-to-r from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 text-white font-bold text-sm sm:text-base flex items-center justify-center gap-2 shadow hover:shadow-md transition transform active:scale-98">
            <span>👁️</span> Generar Vista Previa
          </button>
        </div>"""

    if old_fila3 in c:
        c = c.replace(old_fila3, new_fila3, 1)
        print("Removed prod-notas from top calculation section")
    else:
        print("old_fila3 not found")

    # 4. Insert prod-notas into the bottom section of prod-preview, right next to prod-btn-registrar
    old_bottom = """      <div class="flex justify-between items-center mt-5 pt-4 border-t border-gray-150">

        <button id="prod-btn-receta" onclick="abrirAjusteReceta()"

                class="px-4 py-2 border border-indigo-200 text-indigo-600 font-bold rounded-xl hover:bg-indigo-50 text-xs transition">

          🔄 Ajustar Receta Estándar (Permanente)

        </button>

        <button id="prod-btn-registrar" onclick="registrarProduccion()" disabled

                class="px-5 py-2.5 bg-rose-500 text-white font-bold rounded-xl hover:bg-rose-600 disabled:opacity-40 disabled:cursor-not-allowed text-xs transition">

          Registrar producción

        </button>

      </div>"""

    new_bottom = """      <!-- Notas finales de producción y Botones de Registro -->
      <div class="mt-5 pt-4 border-t border-gray-200 space-y-3">
        <div>
          <label class="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1 flex items-center gap-1.5">
            <span>📝</span> Notas u observaciones de esta producción <span class="font-normal text-slate-500 lowercase">(opcional)</span>
          </label>
          <input id="prod-notas" type="text" placeholder="Ej. Lote matutino, ajuste de fórmula, textura obtenida..." class="w-full border-2 border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white text-slate-800 outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition shadow-2xs">
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 pt-1">
          <button id="prod-btn-receta" onclick="abrirAjusteReceta()"
                  class="px-4 py-2.5 border border-indigo-200 text-indigo-700 bg-indigo-50/50 font-bold rounded-xl hover:bg-indigo-100 text-xs transition">
            🔄 Ajustar Receta Estándar (Permanente)
          </button>

          <button id="prod-btn-registrar" onclick="registrarProduccion()" disabled
                  class="px-8 py-3 bg-rose-600 text-white font-black rounded-xl hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed text-sm sm:text-base transition shadow-md flex items-center gap-2">
            <span>✨</span> Registrar producción
          </button>
        </div>
      </div>"""

    if old_bottom in c:
        c = c.replace(old_bottom, new_bottom, 1)
        print("Moved prod-notas to final registration section")
    else:
        print("old_bottom not found")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)

    print("inventario_admin.html patched successfully")

if __name__ == '__main__':
    patch()
