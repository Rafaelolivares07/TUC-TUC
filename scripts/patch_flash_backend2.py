import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app/blueprints/tiendas.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update api_caja_validar_factura_flash with 'motivo' and add api_caja_auditoria_flash
old_val = """        resultado = (data.get('resultado') or 'ok').lower()
        items_resumen = data.get('items_resumen', '')
        total = float(data.get('total') or 0)
        cajero = data.get('cajero') or session.get('nombre') or 'Caja'
        
        rest_id = negocio['id'] if negocio['tipo_negocio'] != 'tienda' else None
        tienda_id = negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None
        
        conn.execute(\"\"\"
            INSERT INTO pedido_validaciones_flash 
            (pedido_id, numero_documento, restaurante_id, tienda_id, cajero, resultado, items_resumen, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        \"\"\", (pedido_id, num_doc, rest_id, tienda_id, cajero, resultado, items_resumen, total))"""

new_val = """        resultado = (data.get('resultado') or 'ok').lower()
        motivo = data.get('motivo', '')
        items_resumen = data.get('items_resumen', '')
        total = float(data.get('total') or 0)
        cajero = data.get('cajero') or session.get('nombre') or 'Caja'
        
        rest_id = negocio['id'] if negocio['tipo_negocio'] != 'tienda' else None
        tienda_id = negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None
        
        conn.execute(\"\"\"
            INSERT INTO pedido_validaciones_flash 
            (pedido_id, numero_documento, restaurante_id, tienda_id, cajero, resultado, motivo, items_resumen, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        \"\"\", (pedido_id, num_doc, rest_id, tienda_id, cajero, resultado, motivo, items_resumen, total))"""

if old_val in code:
    code = code.replace(old_val, new_val, 1)
    print("Updated api_caja_validar_factura_flash with motivo")
else:
    print("WARNING: old_val not found")

auditoria_endpoint = """
@bp.route('/api/caja/<slug>/auditoria-flash')
@bp.route('/api/tienda/<slug>/caja/auditoria-flash')
def api_caja_auditoria_flash(slug):
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
            
        fecha_req = request.args.get('fecha') or date.today().isoformat()
        
        if negocio['tipo_negocio'] == 'tienda':
            cond_negocio = "(p.tienda_id = %s OR p.negocio_id = %s)"
            params = [negocio['id'], negocio.get('tercero_id') or negocio['id'], fecha_req]
            neg_cond_val = "tienda_id = %s"
            neg_val_param = negocio['id']
        else:
            cond_negocio = "(p.restaurante_id = %s OR p.negocio_id = %s)"
            params = [negocio['id'], negocio.get('tercero_id') or negocio['id'], fecha_req]
            neg_cond_val = "restaurante_id = %s"
            neg_val_param = negocio['id']
            
        pedidos_rows = conn.execute(f\"\"\"
            SELECT p.id, p.numero_documento, p.total, p.created_at, p.fecha,
                   p.nombre_cajero, p.metodo_pago
            FROM pedidos p
            WHERE {cond_negocio}
              AND DATE(COALESCE(p.fecha, p.created_at)) = %s
              AND COALESCE(p.estado, '') != 'cancelado'
            ORDER BY p.id ASC
        \"\"\", tuple(params)).fetchall()
        
        gran_total = 0.0
        total_unidades = 0
        prods_dict = {}
        metodos_dict = {}
        docs_list = []
        
        for p in pedidos_rows:
            p_dict = dict(p)
            p_id = p_dict['id']
            tot = float(p_dict.get('total') or 0)
            gran_total += tot
            
            doc_str = p_dict.get('numero_documento') or f"#{p_id}"
            docs_list.append(doc_str)
            
            met = p_dict.get('metodo_pago') or 'efectivo'
            metodos_dict[met] = metodos_dict.get(met, 0) + tot
            
            items = conn.execute("SELECT nombre_producto, cantidad, precio_unitario FROM pedido_items WHERE pedido_id = %s", (p_id,)).fetchall()
            for it in items:
                nom = it['nombre_producto']
                cant = it['cantidad'] or 0
                total_unidades += cant
                if nom not in prods_dict:
                    prods_dict[nom] = {'nombre': nom, 'cantidad': 0, 'total': 0.0}
                prods_dict[nom]['cantidad'] += cant
                prods_dict[nom]['total'] += (cant * (it['precio_unitario'] or 0))
                
        # Consultar validaciones de este negocio y fecha
        validaciones_rows = conn.execute(f\"\"\"
            SELECT id, pedido_id, numero_documento, cajero, resultado, motivo, items_resumen, total, created_at
            FROM pedido_validaciones_flash
            WHERE {neg_cond_val}
              AND DATE(created_at) = %s
            ORDER BY id DESC
        \"\"\", (neg_val_param, fecha_req)).fetchall()
        
        validaciones = []
        ok_count = 0
        inc_count = 0
        for v in validaciones_rows:
            vd = dict(v)
            if vd.get('created_at'):
                vd['hora'] = vd['created_at'].strftime('%I:%M %p') if hasattr(vd['created_at'], 'strftime') else str(vd['created_at'])
            if vd['resultado'] == 'ok':
                ok_count += 1
            else:
                inc_count += 1
            validaciones.append(vd)
            
        rango_docs = ''
        if docs_list:
            if len(docs_list) == 1:
                rango_docs = f"Factura {docs_list[0]}"
            else:
                rango_docs = f"De la {docs_list[0]} a la {docs_list[-1]}"
                
        hora_inicio = ''
        hora_fin = ''
        if pedidos_rows:
            p_first = dict(pedidos_rows[0])
            p_last = dict(pedidos_rows[-1])
            f_time = p_first.get('created_at') or p_first.get('fecha')
            l_time = p_last.get('created_at') or p_last.get('fecha')
            hora_inicio = f_time.strftime('%I:%M %p') if hasattr(f_time, 'strftime') else str(f_time)
            hora_fin = l_time.strftime('%I:%M %p') if hasattr(l_time, 'strftime') else str(l_time)
            
        return jsonify({
            'ok': True,
            'fecha': fecha_req,
            'gran_total': gran_total,
            'total_facturas': len(pedidos_rows),
            'total_unidades': total_unidades,
            'rango_documentos': rango_docs,
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
            'resumen_productos': list(prods_dict.values()),
            'resumen_metodos': [{'codigo': k, 'nombre': k.capitalize(), 'total': v} for k, v in metodos_dict.items()],
            'validaciones_totales': {'ok': ok_count, 'incorrecto': inc_count, 'total': len(validaciones)},
            'validaciones': validaciones
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
"""

marker = "@bp.route('/api/caja/<slug>/facturas-guardadas')"
if marker in code and "def api_caja_auditoria_flash" not in code:
    code = code.replace(marker, auditoria_endpoint + "\n" + marker, 1)
    print("Auditoria endpoint added to tiendas.py")

with open('app/blueprints/tiendas.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Finished updating tiendas.py")
