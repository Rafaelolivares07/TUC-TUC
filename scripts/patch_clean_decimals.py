import sys, os

def patch_compras_py():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\compras.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_block = """        # Establecer sesión para que el chat nativo de TUC TUC reconozca al proveedor
        session['chat_tercero_id'] = oc['proveedor_id']
        session['chat_token'] = oc['conversacion_token']

        return render_template('orden_compra_publica.html',
                               orden=dict(oc),
                               items=[dict(it) for it in items],
                               token=token,
                               conversacion_token=oc['conversacion_token'] or '')"""

    new_block = """        # Establecer sesión para que el chat nativo de TUC TUC reconozca al proveedor
        session['chat_tercero_id'] = oc['proveedor_id']
        session['chat_token'] = oc['conversacion_token']

        oc_dict = dict(oc)
        total_estimado_num = int(round(float(oc_dict.get('total_estimado') or 0)))
        total_confirmado_num = int(round(float(oc_dict['total_confirmado']))) if oc_dict.get('total_confirmado') is not None else None
        
        oc_dict['total_estimado_fmt'] = f"{total_estimado_num:,.0f}".replace(',', '.')
        oc_dict['total_confirmado_fmt'] = f"{total_confirmado_num:,.0f}".replace(',', '.') if total_confirmado_num is not None else None
        oc_dict['total_display_fmt'] = oc_dict['total_confirmado_fmt'] or oc_dict['total_estimado_fmt']

        clean_items = []
        for it in items:
            d = dict(it)
            prec_sol = int(round(float(d.get('precio_unitario') or 0)))
            prec_conf = int(round(float(d['precio_confirmado']))) if d.get('precio_confirmado') is not None else None
            tot_sol = int(round(float(d.get('total_solicitado') or 0)))
            tot_conf = int(round(float(d['total_confirmado']))) if d.get('total_confirmado') is not None else None

            # Cantidad solicitada y confirmada sin decimales innecesarios
            c_sol_raw = float(d.get('cantidad_solicitada') or 0)
            c_sol = int(c_sol_raw) if c_sol_raw.is_integer() else round(c_sol_raw, 2)
            
            c_conf = None
            if d.get('cantidad_confirmada') is not None:
                c_conf_raw = float(d['cantidad_confirmada'])
                c_conf = int(c_conf_raw) if c_conf_raw.is_integer() else round(c_conf_raw, 2)

            u_pres = None
            if d.get('unidades_presentacion') is not None:
                u_raw = float(d['unidades_presentacion'])
                u_pres = int(u_raw) if u_raw.is_integer() else round(u_raw, 1)

            tol = 10
            if d.get('tolerancia_peso_pct') is not None:
                tol_raw = float(d['tolerancia_peso_pct'])
                tol = int(tol_raw) if tol_raw.is_integer() else round(tol_raw, 1)

            # Rango min y max si peso variable
            r_min = round(c_sol_raw * (1.0 - (tol / 100.0)), 2)
            r_min_clean = int(r_min) if r_min.is_integer() else r_min
            r_max = round(c_sol_raw * (1.0 + (tol / 100.0)), 2)
            r_max_clean = int(r_max) if r_max.is_integer() else r_max

            d['precio_unitario'] = prec_sol
            d['precio_unitario_fmt'] = f"{prec_sol:,.0f}".replace(',', '.')
            d['precio_confirmado'] = prec_conf
            d['precio_confirmado_fmt'] = f"{prec_conf:,.0f}".replace(',', '.') if prec_conf is not None else None
            d['total_solicitado'] = tot_sol
            d['total_solicitado_fmt'] = f"{tot_sol:,.0f}".replace(',', '.')
            d['total_confirmado'] = tot_conf
            d['total_confirmado_fmt'] = f"{tot_conf:,.0f}".replace(',', '.') if tot_conf is not None else None
            d['total_display_fmt'] = d['total_confirmado_fmt'] or d['total_solicitado_fmt']

            d['cantidad_solicitada'] = c_sol
            d['cantidad_confirmada'] = c_conf
            d['unidades_presentacion'] = u_pres
            d['tolerancia_peso_pct'] = tol
            d['rango_min'] = r_min_clean
            d['rango_max'] = r_max_clean

            clean_items.append(d)

        return render_template('orden_compra_publica.html',
                               orden=oc_dict,
                               items=clean_items,
                               token=token,
                               conversacion_token=oc['conversacion_token'] or '')"""

    if old_block in content:
        content = content.replace(old_block, new_block, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("compras.py patched successfully")
    else:
        print("compras.py target block not found")


def patch_template():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\orden_compra_publica.html'
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # 1. Unidades presentación
    old_pres = """                {% if it.unidades_presentacion and it.unidades_presentacion > 1 %}
                  <span class="text-slate-400">({{ it.unidades_presentacion|round(1) }} und/paq)</span>
                {% endif %}"""
    new_pres = """                {% if it.unidades_presentacion and it.unidades_presentacion > 1 %}
                  <span class="text-slate-400">({{ it.unidades_presentacion }} und/paq)</span>
                {% endif %}"""
    if old_pres in c:
        c = c.replace(old_pres, new_pres, 1)

    # 2. Precio unitario y Solicitado
    old_sol = """            <!-- Precio unitario solicitado -->
            <div class="text-right">
              <span class="text-xs font-black text-slate-800 block">${{ "{:,.0f}".format((it.precio_unitario or 0)|float) }}</span>
              <span class="text-[10px] text-slate-600 font-bold">Solicitado: <b>{{ it.cantidad_solicitada|round(2) }}</b></span>
            </div>"""
    new_sol = """            <!-- Precio unitario solicitado -->
            <div class="text-right">
              <span class="text-xs font-black text-slate-800 block">${{ it.precio_unitario_fmt }}</span>
              <span class="text-[10px] text-slate-600 font-bold">Solicitado: <b>{{ it.cantidad_solicitada }}</b></span>
            </div>"""
    if old_sol in c:
        c = c.replace(old_sol, new_sol, 1)

    # 3. Badge tolerancia peso variable
    old_tol = """          <!-- Badge Tolerancia de Peso Variable si aplica -->
          {% if it.peso_variable %}
            <div class="bg-amber-50/80 border border-amber-200/90 rounded-lg px-2.5 py-1 text-[11px] text-amber-900 flex items-center justify-between">
              <span class="font-bold flex items-center gap-1">
                ⚖️ Peso Variable (±{{ it.tolerancia_peso_pct|round(0) }}%)
              </span>
              <span class="font-mono font-semibold text-[10px] text-amber-800">
                Rango: {{ (it.cantidad_solicitada * (1.0 - (it.tolerancia_peso_pct/100.0)))|round(2) }} — {{ (it.cantidad_solicitada * (1.0 + (it.tolerancia_peso_pct/100.0)))|round(2) }}
              </span>
            </div>
          {% endif %}"""
    new_tol = """          <!-- Badge Tolerancia de Peso Variable si aplica -->
          {% if it.peso_variable %}
            <div class="bg-amber-50/80 border border-amber-200/90 rounded-lg px-2.5 py-1 text-[11px] text-amber-900 flex items-center justify-between">
              <span class="font-bold flex items-center gap-1">
                ⚖️ Peso Variable (±{{ it.tolerancia_peso_pct }}%)
              </span>
              <span class="font-mono font-semibold text-[10px] text-amber-800">
                Rango: {{ it.rango_min }} — {{ it.rango_max }}
              </span>
            </div>
          {% endif %}"""
    if old_tol in c:
        c = c.replace(old_tol, new_tol, 1)

    # 4. Inputs de Cantidad y Precio
    old_inputs = """          <!-- Inputs de confirmación: Cantidad y Precio -->
          <div class="bg-slate-50 border border-slate-150 rounded-xl p-2 grid grid-cols-2 gap-2 text-xs">
            <div>
              <label class="block text-[10px] font-extrabold uppercase text-slate-600 mb-0.5">Cant. a Despachar</label>
              {% set max_val = (it.cantidad_solicitada * (1.0 + (it.tolerancia_peso_pct/100.0)))|round(2) if it.peso_variable else it.cantidad_solicitada %}
              <input type="number" step="any" min="0" max="{{ max_val }}"
                     value="{{ it.cantidad_confirmada if it.cantidad_confirmada is not none else it.cantidad_solicitada }}"
                     {% if orden.estado in ['confirmada', 'recibida'] %}disabled{% endif %}
                     oninput="recalcularFila(this)"
                     class="inp-cant w-full text-xs font-bold text-slate-800 bg-white border border-slate-200 rounded-lg px-2 py-1 outline-none focus:border-indigo-500">
            </div>

            <div>
              <label class="block text-[10px] font-extrabold uppercase text-slate-600 mb-0.5">Precio Unitario ($)</label>
              <input type="number" step="any" min="0"
                     value="{{ it.precio_confirmado if it.precio_confirmado is not none else it.precio_unitario }}"
                     {% if orden.estado in ['confirmada', 'recibida'] %}disabled{% endif %}
                     oninput="recalcularFila(this)"
                     class="inp-prec w-full text-xs font-bold text-slate-800 bg-white border border-slate-200 rounded-lg px-2 py-1 outline-none focus:border-indigo-500">
            </div>
          </div>"""

    new_inputs = """          <!-- Inputs de confirmación: Cantidad y Precio -->
          <div class="bg-slate-50 border border-slate-150 rounded-xl p-2 grid grid-cols-2 gap-2 text-xs">
            <div>
              <label class="block text-[10px] font-extrabold uppercase text-slate-600 mb-0.5">Cant. a Despachar</label>
              <input type="number" step="any" min="0" max="{{ it.rango_max if it.peso_variable else it.cantidad_solicitada }}"
                     value="{{ it.cantidad_confirmada if it.cantidad_confirmada is not none else it.cantidad_solicitada }}"
                     {% if orden.estado in ['confirmada', 'recibida'] %}disabled{% endif %}
                     oninput="recalcularFila(this)"
                     class="inp-cant w-full text-xs font-bold text-slate-800 bg-white border border-slate-200 rounded-lg px-2 py-1 outline-none focus:border-indigo-500">
            </div>

            <div>
              <label class="block text-[10px] font-extrabold uppercase text-slate-600 mb-0.5">Precio Unitario ($)</label>
              <input type="number" step="1" min="0"
                     value="{{ it.precio_confirmado if it.precio_confirmado is not none else it.precio_unitario }}"
                     {% if orden.estado in ['confirmada', 'recibida'] %}disabled{% endif %}
                     oninput="recalcularFila(this)"
                     class="inp-prec w-full text-xs font-bold text-slate-800 bg-white border border-slate-200 rounded-lg px-2 py-1 outline-none focus:border-indigo-500">
            </div>
          </div>"""
    if old_inputs in c:
        c = c.replace(old_inputs, new_inputs, 1)

    # 5. Subtotal fila
    old_subt = """<span class="subtotal-val font-black text-indigo-900">${{ "{:,.0f}".format(((it.total_confirmado if it.total_confirmado is not none else it.total_solicitado) or 0)|float) }}</span>"""
    new_subt = """<span class="subtotal-val font-black text-indigo-900">${{ it.total_display_fmt }}</span>"""
    if old_subt in c:
        c = c.replace(old_subt, new_subt, 1)

    # 6. Total general
    old_tot = """          <span id="total-general-conf" class="text-lg font-black text-slate-900 font-mono">
            ${{ "{:,.0f}".format(((orden.total_confirmado if orden.total_confirmado is not none else orden.total_estimado) or 0)|float) }}
          </span>"""
    new_tot = """          <span id="total-general-conf" class="text-lg font-black text-slate-900 font-mono">
            ${{ orden.total_display_fmt }}
          </span>"""
    if old_tot in c:
        c = c.replace(old_tot, new_tot, 1)

    # 7. In JS: format with maximumFractionDigits: 0, minimumFractionDigits: 0
    old_js_sub = "subtotalEl.textContent = '$' + subtotal.toLocaleString('es-CO', { maximumFractionDigits: 0 });"
    new_js_sub = "subtotalEl.textContent = '$' + Math.round(subtotal).toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });"
    if old_js_sub in c:
        c = c.replace(old_js_sub, new_js_sub, 1)

    old_js_tot = "if (totEl) totEl.textContent = '$' + totalGral.toLocaleString('es-CO', { maximumFractionDigits: 0 });"
    new_js_tot = "if (totEl) totEl.textContent = '$' + Math.round(totalGral).toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });"
    if old_js_tot in c:
        c = c.replace(old_js_tot, new_js_tot, 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print("orden_compra_publica.html patched successfully")

if __name__ == '__main__':
    patch_compras_py()
    patch_template()
