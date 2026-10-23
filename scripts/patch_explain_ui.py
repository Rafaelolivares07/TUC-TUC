import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/inventario_admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Enhance the labels and explanations in the side-by-side inputs (Cantidad a Simular & Cantidad Real Obtenida)
old_side_by_side = """        <!-- Fila 3: Cantidad a Simular y Cantidad Real Obtenida (Lado a Lado) -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3.5">
          <!-- Col 1: Cantidad a Simular -->
          <div class="bg-white border-2 border-slate-200/90 rounded-xl p-3 shadow-2xs hover:border-slate-300 transition">
            <div class="flex items-center justify-between gap-2 mb-1">
              <label class="text-xs font-black text-slate-700 uppercase tracking-wide flex items-center gap-1">
                <span>🔢</span> Cantidad a Simular <span class="text-rose-500">*</span>
              </label>
              <span class="text-[10px] font-bold text-slate-400">Calcula receta teórica</span>
            </div>
            <div class="flex items-center gap-2">
              <input id="prod-cantidad" type="number" min="0.0001" step="0.0001" value="1"
                     oninput="onInputProdCantidad(this.value)"
                     onkeydown="if(event.key==='Enter'){event.preventDefault();previsualizarProduccion(true, true);}"
                     placeholder="0"
                     class="w-full border-2 border-slate-200 rounded-lg px-3 py-1.5 text-base sm:text-lg bg-slate-50/50 font-mono font-black text-slate-900 text-right outline-none focus:bg-white focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition shadow-2xs">
              <span class="text-xs font-bold text-slate-500 shrink-0">Und/g</span>
            </div>
            <p class="text-[10px] text-slate-400 mt-1">Modifica esta cantidad para calcular insumos proporcionalmente</p>
          </div>

          <!-- Col 2: Cantidad Real Obtenida -->
          <div class="bg-gradient-to-r from-rose-50/70 via-pink-50/50 to-amber-50/40 border-2 border-rose-300/80 rounded-xl p-3 shadow-2xs flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between gap-2 mb-1">
                <label class="text-xs font-black text-rose-800 uppercase tracking-wide flex items-center gap-1">
                  <span>🔥</span> Cantidad Real Obtenida
                </label>
                <span class="text-[10px] font-black bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded border border-emerald-300/60" title="Al editar esta cantidad final, los insumos de la tabla se mantienen fijos">🔒 Insumos fijos</span>
              </div>
              <div class="flex items-center gap-2">
                <input id="prod-preview-cant-input" type="number" min="0.0001" step="any"
                       oninput="ajustarCantidadRealProducida(this.value, 'preview')"
                       placeholder="Resultado real"
                       class="w-full text-right border-2 border-rose-300 focus:border-rose-600 rounded-lg px-3 py-1.5 text-base sm:text-lg font-black text-rose-700 font-mono bg-white outline-none transition shadow-2xs"
                       title="Ajusta la cantidad real producida sin recalcular los insumos">
                <span class="text-xs font-bold text-rose-600 shrink-0">Und/g</span>
              </div>
            </div>
            <span id="prod-preview-cant-badge" class="hidden"></span>
            <div id="prod-preview-rendimiento-info" class="w-full mt-1 text-[11px] font-bold text-slate-600 flex items-center justify-between gap-1 flex-wrap">
              <span class="text-[10px] text-slate-400">Total físico que ingresará al inventario</span>
            </div>
          </div>
        </div>"""

new_side_by_side = """        <!-- Fila 3: Cantidad a Simular y Cantidad Real Obtenida (Lado a Lado con Explicación Clara) -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3.5">
          <!-- Col 1: Cantidad a Simular -->
          <div class="bg-white border-2 border-slate-200/90 rounded-xl p-3.5 shadow-2xs hover:border-slate-300 transition flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between gap-2 mb-1">
                <label class="text-xs font-black text-slate-800 uppercase tracking-wide flex items-center gap-1.5">
                  <span>🔢</span> 1. Cantidad a Simular (Teórica) <span class="text-rose-500">*</span>
                </label>
                <span class="text-[10px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">Calcula Receta</span>
              </div>
              <div class="flex items-center gap-2">
                <input id="prod-cantidad" type="number" min="0.0001" step="0.0001" value="1"
                       oninput="onInputProdCantidad(this.value)"
                       onkeydown="if(event.key==='Enter'){event.preventDefault();previsualizarProduccion(true, true);}"
                       placeholder="0"
                       class="w-full border-2 border-slate-200 rounded-lg px-3 py-2 text-base sm:text-lg bg-slate-50/60 font-mono font-black text-slate-900 text-right outline-none focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition shadow-2xs">
                <span class="text-xs font-bold text-slate-500 shrink-0">Und/g</span>
              </div>
            </div>
            <p class="text-[11px] text-slate-500 mt-2 leading-tight">
              <b>¿Para qué sirve?:</b> Es tu plan o lote teórico. Al cambiar este valor, el sistema calcula automáticamente cuánta materia prima requieres según la receta oficial.
            </p>
          </div>

          <!-- Col 2: Cantidad Real Obtenida -->
          <div class="bg-gradient-to-r from-rose-50/70 via-pink-50/50 to-amber-50/40 border-2 border-rose-300/80 rounded-xl p-3.5 shadow-2xs flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between gap-2 mb-1">
                <label class="text-xs font-black text-rose-800 uppercase tracking-wide flex items-center gap-1.5">
                  <span>🔥</span> 2. Cantidad Real Obtenida (Física)
                </label>
                <span class="text-[10px] font-black bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded border border-emerald-300/60" title="Al editar esta cantidad final, los insumos de la tabla se mantienen fijos">🔒 Insumos fijos</span>
              </div>
              <div class="flex items-center gap-2">
                <input id="prod-preview-cant-input" type="number" min="0.0001" step="any"
                       oninput="ajustarCantidadRealProducida(this.value, 'preview')"
                       placeholder="Resultado real de paila/cocina"
                       class="w-full text-right border-2 border-rose-300 focus:border-rose-600 rounded-lg px-3 py-2 text-base sm:text-lg font-black text-rose-700 font-mono bg-white outline-none transition shadow-2xs"
                       title="Ajusta la cantidad real producida sin recalcular los insumos">
                <span class="text-xs font-bold text-rose-600 shrink-0">Und/g</span>
              </div>
            </div>
            <span id="prod-preview-cant-badge" class="hidden"></span>
            <div>
              <div id="prod-preview-rendimiento-info" class="w-full mt-1.5 text-[11px] font-bold text-slate-600 flex items-center justify-between gap-1 flex-wrap">
                <!-- Indicador dinámico de rendimiento/merma -->
              </div>
              <p class="text-[11px] text-rose-900/80 mt-1 leading-tight">
                <b>¿Para qué sirve?:</b> Lo que efectivamente se pesó/contó al salir de cocina. Esto es lo que ingresará a bodega terminado (sin alterar los insumos consumidos).
              </p>
            </div>
          </div>
        </div>"""

if old_side_by_side in html:
    html = html.replace(old_side_by_side, new_side_by_side, 1)
    print('Side-by-side inputs enhanced with explanations successfully')
else:
    old_side_n = old_side_by_side.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_side_n in html_n:
        html = html_n.replace(old_side_n, new_side_by_side.replace('\r\n', '\n'), 1)
        print('Side-by-side inputs enhanced with explanations successfully (normalized)')
    else:
        print('ERROR: old_side_by_side not found')

# 2. Clarify the bottom buttons with dedicated explanation cards
old_bottom_buttons = """        <div class="flex flex-wrap items-center justify-between gap-3 pt-1">
          <button id="prod-btn-receta" onclick="abrirAjusteReceta()"
                  class="px-4 py-2.5 border border-indigo-200 text-indigo-700 bg-indigo-50/50 font-bold rounded-xl hover:bg-indigo-100 text-xs transition">
            🔄 Ajustar Receta Estándar (Permanente)
          </button>

          <button id="prod-btn-registrar" onclick="registrarProduccion()" disabled
                  class="px-8 py-3 bg-rose-600 text-white font-black rounded-xl hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed text-sm sm:text-base transition shadow-md flex items-center gap-2">
            <span>✨</span> Registrar producción
          </button>
        </div>"""

new_bottom_buttons = """        <!-- Explicación Didáctica y Botones de Acción -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-2">
          
          <!-- Tarjeta Acción 1: Ajuste Permanente de Receta Oficial -->
          <div class="p-3.5 rounded-2xl bg-indigo-50/70 border-2 border-indigo-200 flex flex-col justify-between gap-2.5 shadow-2xs">
            <div>
              <div class="flex items-center gap-1.5 font-bold text-indigo-950 text-xs sm:text-sm mb-1">
                <span>🔄</span>
                <span>¿Modificaste insumos y quieres cambiar la fórmula oficial?</span>
              </div>
              <p class="text-[11px] text-indigo-900/80 leading-relaxed">
                Si en la tabla ajustaste las cantidades (ej. más salsa o menos sal) y quieres que esa sea la <b>nueva receta estándar para siempre</b>, este botón actualiza la base de datos oficial. Las futuras órdenes usarán esta nueva proporción por unidad.
              </p>
            </div>
            <button id="prod-btn-receta" onclick="abrirAjusteReceta()" type="button"
                    class="w-full px-4 py-2.5 border-2 border-indigo-300 text-indigo-900 bg-white hover:bg-indigo-100 font-bold rounded-xl text-xs transition flex items-center justify-center gap-2 shadow-2xs cursor-pointer">
              <span>🔄</span> Ajustar Receta Estándar (Permanente)
            </button>
          </div>

          <!-- Tarjeta Acción 2: Registrar Lote del Día -->
          <div class="p-3.5 rounded-2xl bg-rose-50/70 border-2 border-rose-200 flex flex-col justify-between gap-2.5 shadow-2xs">
            <div>
              <div class="flex items-center gap-1.5 font-bold text-rose-950 text-xs sm:text-sm mb-1">
                <span>✨</span>
                <span>¿Solo vas a asentar la producción realizada hoy?</span>
              </div>
              <p class="text-[11px] text-rose-900/80 leading-relaxed">
                Descuenta del inventario los insumos consumidos en la tabla e ingresa la <b>Cantidad Real Obtenida</b> como producto terminado en bodega. <b>No modifica</b> la receta maestra futura.
              </p>
            </div>
            <button id="prod-btn-registrar" onclick="registrarProduccion()" disabled type="button"
                    class="w-full px-6 py-2.5 bg-rose-600 hover:bg-rose-700 active:scale-98 text-white font-black rounded-xl disabled:opacity-40 disabled:cursor-not-allowed text-xs sm:text-sm transition shadow-md flex items-center justify-center gap-2 cursor-pointer">
              <span>✨</span> Registrar producción (Solo este lote)
            </button>
          </div>

        </div>"""

if old_bottom_buttons in html:
    html = html.replace(old_bottom_buttons, new_bottom_buttons, 1)
    print('Bottom buttons replaced with explanatory cards successfully')
else:
    old_btn_n = old_bottom_buttons.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_btn_n in html_n:
        html = html_n.replace(old_btn_n, new_bottom_buttons.replace('\r\n', '\n'), 1)
        print('Bottom buttons replaced with explanatory cards successfully (normalized)')
    else:
        print('ERROR: old_bottom_buttons not found')

# 3. Enhance modal header in overlay-ajuste-receta
old_modal_warn = """    <!-- Warnings / Info -->

    <div class="flex-shrink-0 bg-yellow-50 border border-yellow-100 rounded-xl p-3 mb-4 text-[11px] text-yellow-800">

      <span class="font-bold block mb-1">⚠️ Ajuste de Proporciones:</span>

      Se recalcularán las cantidades de la receta estándar para <strong>1 unidad</strong> de producto terminado, dividiendo la cantidad real consumida por la cantidad total producida (<strong><span id="ajuste-cant-producir"></span> unidades</strong>).

    </div>"""

new_modal_warn = """    <!-- Warnings / Info -->
    <div class="flex-shrink-0 bg-indigo-50 border-2 border-indigo-200 rounded-xl p-3.5 mb-4 text-xs text-indigo-950 space-y-1 shadow-2xs">
      <div class="font-bold flex items-center gap-1.5 text-indigo-900 text-xs sm:text-sm">
        <span>💡</span> ¿Cómo se recalcula la fórmula oficial?
      </div>
      <p class="text-[11px] text-indigo-900/90 leading-relaxed">
        Cada insumo consumido en la tabla se dividirá entre las <strong><span id="ajuste-cant-producir" class="font-mono font-black text-indigo-950"></span> unidades</strong> producidas para fijar la nueva proporción por <strong>1 unidad</strong> de producto terminado.
      </p>
      <p class="text-[10px] text-indigo-700 font-bold bg-white/80 rounded-lg p-2 border border-indigo-200">
        ⚠️ <b>Importante:</b> Al confirmar, se reescribe la Tarjeta Estándar maestra en la base de datos. De aquí en adelante, todas las futuras producciones usarán estas nuevas cantidades y costos.
      </p>
    </div>"""

if old_modal_warn in html:
    html = html.replace(old_modal_warn, new_modal_warn, 1)
    print('Modal warning enhanced successfully')
else:
    old_mod_n = old_modal_warn.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_mod_n in html_n:
        html = html_n.replace(old_mod_n, new_modal_warn.replace('\r\n', '\n'), 1)
        print('Modal warning enhanced successfully (normalized)')
    else:
        print('ERROR: old_modal_warn not found')

with open('templates/inventario_admin.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('All UI explanation enhancements applied!')
