import sys, os

def patch():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\inventario_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # Find the block starting at "<!-- Controles de simulación por materia prima -->" until "<!-- Micro-guía explicativa para el usuario -->"
    start_marker = "<!-- Controles de simulación por materia prima -->"
    end_marker = "<!-- Micro-guía explicativa para el usuario -->"

    start_pos = c.find(start_marker)
    end_pos = c.find(end_marker)

    if start_pos == -1 or end_pos == -1:
        print("Markers not found!")
        return

    new_section = """<!-- Controles de simulación por materia prima -->
          <div class="bg-white/90 border border-amber-200/90 rounded-xl p-3.5 mb-2.5 shadow-2xs space-y-3">
            
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

            <!-- Fila inferior: 2. Variación / Simulación de MP y 3. Cantidad Real Obtenida -->
            <div class="pt-2.5 border-t border-amber-200/70 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs items-end">
              
              <!-- 2. Cantidad MP si desea variar -->
              <div>
                <label class="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">
                  2. ¿Vas a usar una cantidad diferente de MP? <span class="font-normal text-slate-500 lowercase">(opcional)</span>
                </label>
                <div class="flex items-center gap-2">
                  <input id="prod-sug-mp-cant" type="number" min="0" step="any" placeholder="Digita cant. a usar" onkeydown="if(event.key==='Enter'){event.preventDefault();sugerenciaDesdeMP();}" class="w-36 border border-amber-300 rounded-xl px-3 py-2 text-sm sm:text-base bg-white font-mono font-black text-slate-900 text-right outline-none shadow-sm focus:border-amber-500">
                  <span id="prod-sug-mp-nombre" class="text-xs text-slate-600 font-semibold truncate max-w-[130px]"></span>
                  <button type="button" onclick="sugerenciaDesdeMP()" class="px-3.5 py-2 rounded-xl border border-amber-400 bg-amber-500 hover:bg-amber-600 active:scale-95 text-white font-bold text-xs transition shadow-xs whitespace-nowrap">
                    Recalcular Insumos
                  </button>
                </div>
              </div>

              <!-- 3. Cantidad Final Real Obtenida -->
              <div class="md:border-l md:border-amber-200/80 md:pl-3">
                <label class="block text-xs font-extrabold text-rose-700 uppercase tracking-wide mb-1 flex items-center gap-1">
                  <span>🔥</span> 3. Cantidad Final Real Obtenida <span class="text-[10px] font-bold bg-rose-100 text-rose-800 px-1.5 py-0.2 rounded">🔒 Fija insumos</span>
                </label>
                <div class="flex items-center gap-2">
                  <input id="prod-sug-real-cant" type="number" min="0.0001" step="any" placeholder="Peso/Cant real" oninput="ajustarCantidadRealProducida(this.value, 'sug')" class="w-36 border-2 border-rose-400 rounded-xl px-3 py-2 text-sm sm:text-base bg-rose-50/40 font-mono font-black text-rose-700 text-right outline-none shadow-sm focus:border-rose-600 focus:bg-white" title="Digita la cantidad real que salió del proceso. Los insumos ya calculados no se moverán.">
                  <span class="text-[11px] text-slate-500 font-semibold leading-tight flex-1">Ajusta lo que realmente salió del horno/proceso</span>
                </div>
              </div>

            </div>

          </div>

          """

    c = c[:start_pos] + new_section + c[end_pos:]

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)

    print("inventario_admin.html patched with full-width select and refined workflow")

if __name__ == '__main__':
    patch()
