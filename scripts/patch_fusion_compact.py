import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/inventario_admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Replace the old Row 2 (Producto y Cantidad) with the unified rows:
# Row 2: Producto a Producir (Full width, single input)
# Row 3: Cantidad a Simular y Cantidad Real Obtenida lado a lado (50% / 50%)
old_row2 = """        <!-- Fila 2: Ítem y Cantidad con tipografía ampliada -->
        <div class="grid grid-cols-1 md:grid-cols-12 gap-4 mb-4">
          <div class="md:col-span-8 relative">
            <label class="block text-sm font-bold text-slate-700 uppercase tracking-wide mb-1.5">
              <span>🔍</span> Producto a producir <span class="text-rose-500">*</span>
            </label>
            <div class="relative">
              <input id="prod-ac-input" type="text" placeholder="Escribe para buscar producto con tarjeta estándar…" autocomplete="off" class="w-full border-2 border-slate-300 rounded-xl px-4 py-3 text-base sm:text-lg bg-white font-bold text-slate-900 placeholder:text-slate-400 placeholder:font-normal outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition shadow-sm">
              <div id="prod-ac-list" class="ac-list hidden"></div>
              <input type="hidden" id="prod-ac-id">
            </div>
          </div>
          <div class="md:col-span-4">
            <label class="block text-sm font-bold text-slate-700 uppercase tracking-wide mb-1.5 flex items-center justify-between">
              <span><span>🔢</span> Cantidad a Simular <span class="text-rose-500">*</span></span>
              <span class="text-[10px] font-bold text-slate-500 normal-case">Calcula receta teórica</span>
            </label>
            <input id="prod-cantidad" type="number" min="0.0001" step="0.0001" value="1"
                   oninput="onInputProdCantidad(this.value)"
                   onkeydown="if(event.key==='Enter'){event.preventDefault();previsualizarProduccion(true, true);}"
                   class="w-full border-2 border-slate-300 rounded-xl px-4 py-3 text-base sm:text-lg bg-white font-mono font-black text-slate-900 text-right outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition shadow-sm">
          </div>
        </div>"""

new_unified_inputs = """        <!-- Fila 2: Producto a Producir (Unico input de producto) -->
        <div class="mb-3.5">
          <label class="block text-xs font-black text-slate-700 uppercase tracking-wide mb-1.5 flex items-center justify-between">
            <span><span>🔍</span> Producto a Preparar / Producir <span class="text-rose-500">*</span></span>
            <span class="text-[10px] text-slate-400 font-normal">Escribe el nombre del producto estándar</span>
          </label>
          <div class="relative">
            <input id="prod-ac-input" type="text" placeholder="Buscar producto con tarjeta estándar…" autocomplete="off" class="w-full border-2 border-slate-300 rounded-xl px-3.5 py-2.5 text-base sm:text-lg bg-white font-black text-slate-900 placeholder:text-slate-400 placeholder:font-normal outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition shadow-xs">
            <div id="prod-ac-list" class="ac-list hidden"></div>
            <input type="hidden" id="prod-ac-id">
          </div>
        </div>

        <!-- Fila 3: Cantidad a Simular y Cantidad Real Obtenida (Lado a Lado) -->
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

if old_row2 in html:
    html = html.replace(old_row2, new_unified_inputs, 1)
    print('Unified Row 2 and Row 3 replaced successfully')
else:
    # try normalized
    old_row2_n = old_row2.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_row2_n in html_n:
        html = html_n.replace(old_row2_n, new_unified_inputs.replace('\r\n', '\n'), 1)
        print('Unified Row 2 and Row 3 replaced successfully (normalized)')
    else:
        print('ERROR: old_row2 not found')

# 2. In prod-preview, remove the duplicate pink card header:
# The pink card had:
# - PRODUCTO A FABRICAR / PRODUCIR (nombre repetido)
# - Cantidad Real Obtenida (moved above)
# - Centro / Sede
# - Desglose de insumos bar
# We will replace that whole pink block with a sleek, compact toolbar directly attached to the table:

old_pink_card = """    <div id="prod-preview" class="hidden mb-6" style="scroll-margin-top: 90px;">
      <!-- Tarjeta Destacada del Producto a Producir -->
      <div class="bg-gradient-to-r from-rose-50 via-pink-50/60 to-amber-50/70 border-2 border-rose-300 p-4 sm:p-5 rounded-2xl mb-4 shadow-sm">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div class="space-y-1">
            <span class="text-xs font-black uppercase tracking-wider text-rose-600 flex items-center gap-1.5">
              <span>🏭</span> PRODUCTO A FABRICAR / PRODUCIR
            </span>
            <h3 id="prod-preview-nombre-prod" class="text-xl sm:text-2xl font-black text-gray-900 m-0 tracking-tight">
              <!-- Nombre del producto -->
            </h3>
          </div>
          <div class="flex items-center gap-3 flex-wrap sm:flex-nowrap">
            <!-- Cantidad Real Obtenida Editable -->
            <div class="bg-white border-2 border-rose-400 rounded-xl px-3.5 py-2 shadow-xs flex flex-col items-end min-w-[220px]">
              <div class="w-full flex items-center justify-between gap-2 mb-1">
                <span class="text-[10px] font-black uppercase text-rose-700 tracking-wider flex items-center gap-1">
                  <span>🔥</span> Cantidad Real Obtenida
                </span>
                <span class="text-[10px] font-extrabold bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded" title="Al editar esta cantidad final, los insumos de la tabla se mantienen fijos">🔒 Insumos fijos</span>
              </div>
              <div class="flex items-center gap-1.5 w-full justify-end">
                <input id="prod-preview-cant-input" type="number" min="0.0001" step="any"
                       oninput="ajustarCantidadRealProducida(this.value, 'preview')"
                       class="w-36 sm:w-40 text-right border-2 border-rose-300 focus:border-rose-600 rounded-lg px-2.5 py-1 text-base sm:text-xl font-black text-rose-600 font-mono bg-rose-50/30 focus:bg-white outline-none transition shadow-2xs"
                       title="Ajusta la cantidad real producida sin recalcular los insumos">
                <span class="text-xs font-bold text-slate-500">Und/g</span>
              </div>
              <span id="prod-preview-cant-badge" class="hidden"></span>
              <div id="prod-preview-rendimiento-info" class="w-full mt-1 text-[11px] font-bold text-slate-600 flex items-center justify-end gap-1.5 flex-wrap">
                <!-- Esperado y merma/rendimiento -->
              </div>
            </div>
            <!-- Sede / Centro -->
            <div class="bg-white border border-gray-200 rounded-xl px-3.5 py-2 shadow-xs flex flex-col">
              <span class="text-[10px] font-bold uppercase text-gray-400">Centro / Sede</span>
              <div id="prod-preview-centro-badge" class="text-xs font-black text-gray-800 flex items-center gap-1 mt-0.5">
                <!-- loaded dynamically -->
              </div>
            </div>
          </div>
        </div>
        <div class="mt-3 pt-2.5 border-t border-rose-200/70 flex items-center justify-between text-xs text-gray-700 flex-wrap gap-2">
          <span class="font-bold flex items-center gap-1 text-gray-800">
            <span>📋</span> Desglose de Insumos y Materia Prima requerida:
          </span>
          <div class="flex items-center gap-3">
            <!-- Selector de Decimales -->
            <div class="flex items-center gap-1.5 bg-white border border-rose-200 rounded-lg px-2.5 py-1 shadow-2xs">
              <label for="prod-preview-decimales" class="font-bold text-[11px] text-gray-700 flex items-center gap-1">
                <span>🔢</span> Decimales:
              </label>
              <input id="prod-preview-decimales" type="number" min="0" max="6" step="1" value="2"
                     oninput="cambiarDecimalesPreviewProduccion(this.value)"
                     onchange="cambiarDecimalesPreviewProduccion(this.value)"
                     onblur="validarDecimalesPreviewProduccionInput(this)"
                     class="w-12 text-center font-mono font-bold text-xs bg-rose-50/50 border border-rose-300 rounded px-1 py-0.5 outline-none text-rose-900 focus:border-rose-500 focus:ring-1 focus:ring-rose-400"
                     title="Número de decimales visibles en la vista previa (0 a 6)">
            </div>
            <span id="prod-preview-items-count" class="font-bold text-rose-700 bg-rose-100 px-2.5 py-1 rounded-lg text-xs">
              <!-- 5 insumos -->
            </span>
          </div>
        </div>
      </div>"""

new_table_toolbar = """    <div id="prod-preview" class="hidden mb-6" style="scroll-margin-top: 90px;">
      <!-- Hidden element to keep JS backward compatible -->
      <span id="prod-preview-nombre-prod" class="hidden"></span>

      <!-- Barra compacta sobre la tabla de insumos -->
      <div class="bg-gradient-to-r from-slate-100 via-rose-50/40 to-slate-100 border border-slate-200 rounded-xl px-3.5 py-2 mb-2 shadow-2xs flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-sm">📋</span>
          <span class="font-bold text-xs sm:text-sm text-slate-800">Insumos y Materias Primas Requeridas:</span>
          <span id="prod-preview-items-count" class="font-black text-rose-700 bg-rose-100/90 border border-rose-200 px-2 py-0.5 rounded-lg text-xs">
            0 insumos
          </span>
        </div>

        <div class="flex items-center gap-2.5">
          <!-- Sede / Centro -->
          <div id="prod-preview-centro-badge" class="text-xs font-black px-2.5 py-0.5 rounded-lg border"></div>

          <!-- Selector de Decimales Ultra Compacto -->
          <div class="flex items-center gap-1 bg-white border border-slate-300 rounded-lg px-2 py-0.5 shadow-2xs">
            <label for="prod-preview-decimales" class="font-bold text-[11px] text-slate-600">
              Dec:
            </label>
            <input id="prod-preview-decimales" type="number" min="0" max="6" step="1" value="2"
                   oninput="cambiarDecimalesPreviewProduccion(this.value)"
                   onchange="cambiarDecimalesPreviewProduccion(this.value)"
                   onblur="validarDecimalesPreviewProduccionInput(this)"
                   class="w-9 text-center font-mono font-bold text-xs bg-slate-50 border border-slate-200 rounded px-1 py-0.2 outline-none text-slate-800 focus:border-rose-500">
          </div>
        </div>
      </div>"""

if old_pink_card in html:
    html = html.replace(old_pink_card, new_table_toolbar, 1)
    print('Pink card replaced by sleek toolbar successfully')
else:
    old_pink_n = old_pink_card.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_pink_n in html_n:
        html = html_n.replace(old_pink_n, new_table_toolbar.replace('\r\n', '\n'), 1)
        print('Pink card replaced by sleek toolbar successfully (normalized)')
    else:
        print('ERROR: old_pink_card not found')

# 3. Reduce row height of the table to 1/3 in table header and renderTablaPrevisualizacion:
# Header:
old_thead = """            <tr class="bg-gray-100 text-xs uppercase font-black text-gray-600 border-b border-gray-200">

              <th class="px-3 py-2 text-left">Componente / Insumo</th>

              <th class="px-3 py-2 text-right">Stock actual</th>

              <th class="px-3 py-2 text-right w-44 sm:w-48">A consumir</th>

              <th class="px-3 py-2 text-right">Costo unit.</th>

              <th class="px-3 py-2 text-right">Total Línea</th>

              <th class="px-3 py-2 text-center">Estado</th>

            </tr>"""

new_thead = """            <tr class="bg-slate-100 text-[11px] uppercase font-black text-slate-600 border-b border-slate-200">
              <th class="px-2.5 py-1 text-left">Componente / Insumo</th>
              <th class="px-2 py-1 text-right">Stock actual</th>
              <th class="px-2 py-1 text-right w-36 sm:w-40">A consumir</th>
              <th class="px-2 py-1 text-right">Costo unit.</th>
              <th class="px-2 py-1 text-right">Total Línea</th>
              <th class="px-2 py-1 text-center">Estado</th>
            </tr>"""

if old_thead in html:
    html = html.replace(old_thead, new_thead, 1)
    print('Table header height reduced successfully')
else:
    old_thead_n = old_thead.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_thead_n in html_n:
        html = html_n.replace(old_thead_n, new_thead.replace('\r\n', '\n'), 1)
        print('Table header height reduced successfully (normalized)')
    else:
        print('ERROR: old_thead not found')

# Footer height:
old_tfoot = """            <tr class="bg-gray-50 border-t border-gray-200 font-bold text-gray-800 text-xs sm:text-sm">

              <td class="px-3 py-2.5 text-left">Total costo producción</td>

              <td colspan="3"></td>

              <td id="prod-resumen-total" class="px-3 py-2.5 text-right text-rose-600 font-mono font-black text-sm sm:text-base"></td>

              <td></td>

            </tr>

            <tr class="bg-gray-50 border-t border-gray-100 font-bold text-gray-800 text-xs sm:text-sm">

              <td class="px-3 py-2.5 text-left">Costo unitario estimado</td>

              <td colspan="3"></td>

              <td id="prod-resumen-unitario" class="px-3 py-2.5 text-right text-rose-600 font-mono font-black text-sm sm:text-base"></td>

              <td></td>

            </tr>"""

new_tfoot = """            <tr class="bg-slate-50 border-t border-slate-200 font-black text-slate-800 text-xs">
              <td class="px-2.5 py-1 text-left">Total costo producción</td>
              <td colspan="3"></td>
              <td id="prod-resumen-total" class="px-2 py-1 text-right text-rose-600 font-mono font-black text-sm"></td>
              <td></td>
            </tr>
            <tr class="bg-slate-50 border-t border-slate-100 font-bold text-slate-700 text-xs">
              <td class="px-2.5 py-1 text-left">Costo unitario estimado</td>
              <td colspan="3"></td>
              <td id="prod-resumen-unitario" class="px-2 py-1 text-right text-rose-600 font-mono font-black text-sm"></td>
              <td></td>
            </tr>"""

if old_tfoot in html:
    html = html.replace(old_tfoot, new_tfoot, 1)
    print('Table footer height reduced successfully')
else:
    old_tfoot_n = old_tfoot.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_tfoot_n in html_n:
        html = html_n.replace(old_tfoot_n, new_tfoot.replace('\r\n', '\n'), 1)
        print('Table footer height reduced successfully (normalized)')
    else:
        print('ERROR: old_tfoot not found')

# 4. In renderTablaPrevisualizacion, reduce row padding and height to 1/3:
old_render_row = """      <tr id="prod-preview-row-${l.id}" class="border-b border-gray-100 hover:bg-gray-50/80 transition">
        <td class="px-3 py-1.5 text-left font-bold text-gray-800 text-xs sm:text-sm">${l.nombre}</td>
        <td id="prod-stock-${l.id}" class="px-3 py-1.5 text-right num text-xs sm:text-sm font-mono font-bold ${suf ? 'text-green-600' : 'text-red-500'}">${_fmtProdNum(l.stock_actual)}</td>
        <td class="px-3 py-1.5 text-right">
          <input type="number" step="any" min="0" value="${aConsumirFmt}"
                 oninput="actualizarConsumoPrevisualizacion(${l.id}, this.value)"
                 onblur="this.value = Number(this.value || 0).toFixed(_prodPreviewDecimales); actualizarConsumoPrevisualizacion(${l.id}, this.value);"
                 class="w-44 sm:w-48 text-right border border-gray-300 rounded-md px-2.5 py-0.5 text-xs sm:text-sm font-mono font-bold focus:outline-none focus:ring-2 focus:ring-rose-500 bg-white shadow-2xs">
        </td>
        <td class="px-3 py-1.5 text-right num font-mono text-xs sm:text-sm text-gray-600">${_fmtProdMon(l.costo_und)}</td>
        <td id="prod-subtotal-${l.id}" class="px-3 py-1.5 text-right num font-mono font-black text-xs sm:text-sm text-gray-900">${_fmtProdMon(l.costo_total)}</td>
        <td id="prod-badge-${l.id}" class="px-3 py-1.5 text-center">
          ${suf
            ? '<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-green-800">✓ OK</span>'
            : '<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-red-100 text-red-800">✗ Insuficiente</span>'}
        </td>
      </tr>"""

new_render_row = """      <tr id="prod-preview-row-${l.id}" class="border-b border-slate-100 hover:bg-amber-50/40 transition">
        <td class="px-2.5 py-0.5 text-left font-bold text-slate-800 text-xs leading-tight">${l.nombre}</td>
        <td id="prod-stock-${l.id}" class="px-2 py-0.5 text-right num text-xs font-mono font-bold ${suf ? 'text-emerald-700' : 'text-rose-600'}">${_fmtProdNum(l.stock_actual)}</td>
        <td class="px-2 py-0.5 text-right">
          <input type="number" step="any" min="0" value="${aConsumirFmt}"
                 oninput="actualizarConsumoPrevisualizacion(${l.id}, this.value)"
                 onblur="this.value = Number(this.value || 0).toFixed(_prodPreviewDecimales); actualizarConsumoPrevisualizacion(${l.id}, this.value);"
                 class="w-36 sm:w-40 text-right border border-slate-300 rounded px-2 py-0 h-6 text-xs font-mono font-black focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-400 bg-white shadow-2xs">
        </td>
        <td class="px-2 py-0.5 text-right num font-mono text-xs text-slate-600">${_fmtProdMon(l.costo_und)}</td>
        <td id="prod-subtotal-${l.id}" class="px-2 py-0.5 text-right num font-mono font-black text-xs text-slate-900">${_fmtProdMon(l.costo_total)}</td>
        <td id="prod-badge-${l.id}" class="px-2 py-0.5 text-center">
          ${suf
            ? '<span class="px-1.5 py-0.2 rounded-md text-[10px] font-black bg-emerald-100 text-emerald-800">✓ OK</span>'
            : '<span class="px-1.5 py-0.2 rounded-md text-[10px] font-black bg-rose-100 text-rose-800">✗ Insuficiente</span>'}
        </td>
      </tr>"""

if old_render_row in html:
    html = html.replace(old_render_row, new_render_row, 1)
    print('Row height in renderTablaPrevisualizacion reduced to 1/3 successfully')
else:
    old_row_n = old_render_row.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_row_n in html_n:
        html = html_n.replace(old_row_n, new_render_row.replace('\r\n', '\n'), 1)
        print('Row height in renderTablaPrevisualizacion reduced to 1/3 successfully (normalized)')
    else:
        print('ERROR: old_render_row not found')

with open('templates/inventario_admin.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Patch applied successfully!')
