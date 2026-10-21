import re

file_path = "app/blueprints/inventarios.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Patch api_inventario_producto_crear
crear_target = """        dias_max = data.get('dias_max_stock')
        dias_max = int(dias_max) if (dias_max is not None and str(dias_max).strip() != '') else None
        st_min = data.get('stock_minimo')
        st_min = float(st_min) if (st_min is not None and str(st_min).strip() != '') else None

        row = conn.execute(\"\"\"
            INSERT INTO productos (negocio_id, nombre, categoria, precio, costo,
                                   descripcion, codigo_barra, iva_pct, orden,
                                   dias_min_stock, dias_max_stock, stock_minimo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        \"\"\", (
            negocio_id, nombre,
            data.get('categoria') or None,
            float(data.get('precio') or 0),
            float(data.get('costo') or 0),
            data.get('descripcion') or None,
            data.get('codigo_barra') or None,
            float(data.get('iva_pct') or 0),
            int(data.get('orden') or 0),
            dias_min, dias_max, st_min
        )).fetchone()"""

crear_replacement = """        dias_max = data.get('dias_max_stock')
        dias_max = int(dias_max) if (dias_max is not None and str(dias_max).strip() != '') else None
        st_min = data.get('stock_minimo')
        st_min = float(st_min) if (st_min is not None and str(st_min).strip() != '') else None
        peso_variable = bool(data.get('peso_variable', False))
        tol_peso = float(data.get('tolerancia_peso_pct') or 10.0)

        row = conn.execute(\"\"\"
            INSERT INTO productos (negocio_id, nombre, categoria, precio, costo,
                                   descripcion, codigo_barra, iva_pct, orden,
                                   dias_min_stock, dias_max_stock, stock_minimo,
                                   peso_variable, tolerancia_peso_pct)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        \"\"\", (
            negocio_id, nombre,
            data.get('categoria') or None,
            float(data.get('precio') or 0),
            float(data.get('costo') or 0),
            data.get('descripcion') or None,
            data.get('codigo_barra') or None,
            float(data.get('iva_pct') or 0),
            int(data.get('orden') or 0),
            dias_min, dias_max, st_min,
            peso_variable, tol_peso
        )).fetchone()"""

assert crear_target in content, "crear_target not found in inventarios.py"
content = content.replace(crear_target, crear_replacement, 1)

# 2. Patch api_inventario_productos (consolidated and bodega queries)
query_cons_target = """                SELECT p.id, p.nombre, p.categoria, p.precio,
                       {sql_costo_fallback} AS costo,
                       {sql_costo_origen} AS costo_origen,
                       p.codigo_barra, p.iva_pct, p.disponible, p.orden,
                       p.dias_min_stock, p.dias_max_stock, p.stock_minimo,
                       COALESCE(s.stock, 0) AS stock,"""

query_cons_replacement = """                SELECT p.id, p.nombre, p.categoria, p.precio,
                       {sql_costo_fallback} AS costo,
                       {sql_costo_origen} AS costo_origen,
                       p.codigo_barra, p.iva_pct, p.disponible, p.orden,
                       p.dias_min_stock, p.dias_max_stock, p.stock_minimo,
                       COALESCE(p.peso_variable, FALSE) AS peso_variable,
                       COALESCE(p.tolerancia_peso_pct, 10.0) AS tolerancia_peso_pct,
                       COALESCE(s.stock, 0) AS stock,"""

assert query_cons_target in content, "query_cons_target not found in inventarios.py"
content = content.replace(query_cons_target, query_cons_replacement, 1)

query_bod_target = """                SELECT p.id, p.nombre, p.categoria, p.precio,
                       {sql_costo_fallback} AS costo,
                       {sql_costo_origen} AS costo_origen,
                       p.codigo_barra, p.iva_pct, p.disponible, p.orden,
                       p.dias_min_stock, p.dias_max_stock, p.stock_minimo,
                       COALESCE(s.stock, 0) AS stock,"""

query_bod_replacement = """                SELECT p.id, p.nombre, p.categoria, p.precio,
                       {sql_costo_fallback} AS costo,
                       {sql_costo_origen} AS costo_origen,
                       p.codigo_barra, p.iva_pct, p.disponible, p.orden,
                       p.dias_min_stock, p.dias_max_stock, p.stock_minimo,
                       COALESCE(p.peso_variable, FALSE) AS peso_variable,
                       COALESCE(p.tolerancia_peso_pct, 10.0) AS tolerancia_peso_pct,
                       COALESCE(s.stock, 0) AS stock,"""

assert query_bod_target in content, "query_bod_target not found in inventarios.py"
content = content.replace(query_bod_target, query_bod_replacement, 1)

# 3. Patch api_inventario_producto_editar
editar_target = """        dias_max = data.get('dias_max_stock')
        dias_max = int(dias_max) if (dias_max is not None and str(dias_max).strip() != '') else None
        st_min = data.get('stock_minimo')
        st_min = float(st_min) if (st_min is not None and str(st_min).strip() != '') else None

        conn.execute(\"\"\"
            UPDATE productos SET
                nombre=%s, categoria=%s, precio=%s, costo=%s,
                descripcion=%s, codigo_barra=%s, iva_pct=%s, disponible=%s,
                dias_min_stock=%s, dias_max_stock=%s, stock_minimo=%s
            WHERE id=%s
        \"\"\", (
            nombre,
            data.get('categoria') or None,
            float(data.get('precio') or 0),
            float(data.get('costo') or 0),
            data.get('descripcion') or None,
            data.get('codigo_barra') or None,
            float(data.get('iva_pct') or 0),
            bool(data.get('disponible', True)),
            dias_min,
            dias_max,
            st_min,
            producto_id,
        ))"""

editar_replacement = """        dias_max = data.get('dias_max_stock')
        dias_max = int(dias_max) if (dias_max is not None and str(dias_max).strip() != '') else None
        st_min = data.get('stock_minimo')
        st_min = float(st_min) if (st_min is not None and str(st_min).strip() != '') else None
        peso_variable = bool(data.get('peso_variable', False))
        tol_peso = float(data.get('tolerancia_peso_pct') or 10.0)

        conn.execute(\"\"\"
            UPDATE productos SET
                nombre=%s, categoria=%s, precio=%s, costo=%s,
                descripcion=%s, codigo_barra=%s, iva_pct=%s, disponible=%s,
                dias_min_stock=%s, dias_max_stock=%s, stock_minimo=%s,
                peso_variable=%s, tolerancia_peso_pct=%s
            WHERE id=%s
        \"\"\", (
            nombre,
            data.get('categoria') or None,
            float(data.get('precio') or 0),
            float(data.get('costo') or 0),
            data.get('descripcion') or None,
            data.get('codigo_barra') or None,
            float(data.get('iva_pct') or 0),
            bool(data.get('disponible', True)),
            dias_min,
            dias_max,
            st_min,
            peso_variable,
            tol_peso,
            producto_id,
        ))"""

assert editar_target in content, "editar_target not found in inventarios.py"
content = content.replace(editar_target, editar_replacement, 1)

# 4. Patch api_inventario_compras_sugerencias
sug_prod_query_target = """            SELECT p.id, p.nombre, COALESCE(p.costo, 0) AS costo, p.dias_max_stock, p.dias_min_stock, p.stock_minimo,
                   COALESCE(s.stock, 0) AS stock_actual,
                   COALESCE(p.iva_pct, 0) AS iva_pct
            FROM productos p"""

sug_prod_query_replacement = """            SELECT p.id, p.nombre, COALESCE(p.costo, 0) AS costo, p.dias_max_stock, p.dias_min_stock, p.stock_minimo,
                   COALESCE(s.stock, 0) AS stock_actual,
                   COALESCE(p.iva_pct, 0) AS iva_pct,
                   COALESCE(p.peso_variable, FALSE) AS peso_variable,
                   COALESCE(p.tolerancia_peso_pct, 10.0) AS tolerancia_peso_pct
            FROM productos p"""

assert sug_prod_query_target in content, "sug_prod_query_target not found in inventarios.py"
content = content.replace(sug_prod_query_target, sug_prod_query_replacement, 1)

quotes_query_target = """                SELECT c.id, c.tercero_id, t.nombre AS proveedor_nombre, t.telefono AS proveedor_telefono,
                       COALESCE(c.unidades_item, 1) AS unidades_item, COALESCE(c.precio, 0) AS precio,"""

quotes_query_replacement = """                SELECT c.id, c.tercero_id, t.nombre AS proveedor_nombre, t.telefono AS proveedor_telefono,
                       t.forma_pago_defecto, t.dias_credito, t.modalidad_entrega_defecto, t.direccion_recogida,
                       COALESCE(c.unidades_item, 1) AS unidades_item, COALESCE(c.precio, 0) AS precio,"""

assert quotes_query_target in content, "quotes_query_target not found in inventarios.py"
content = content.replace(quotes_query_target, quotes_query_replacement, 1)

last_purch_target = """            # Obtener el último proveedor histórico como respaldo
            last_purchase = conn.execute(\"\"\"
                SELECT m.proveedor_id, m.proveedor_nombre, t.telefono AS proveedor_telefono
                FROM movimientos_inventario m
                LEFT JOIN terceros t ON t.id = m.proveedor_id"""

last_purch_replacement = """            # Obtener el último proveedor histórico como respaldo
            last_purchase = conn.execute(\"\"\"
                SELECT m.proveedor_id, m.proveedor_nombre, t.telefono AS proveedor_telefono,
                       t.forma_pago_defecto, t.dias_credito, t.modalidad_entrega_defecto, t.direccion_recogida
                FROM movimientos_inventario m
                LEFT JOIN terceros t ON t.id = m.proveedor_id"""

assert last_purch_target in content, "last_purch_target not found in inventarios.py"
content = content.replace(last_purch_target, last_purch_replacement, 1)

prov_init_target = """            prov_id = 0
            prov_nombre = "Sin Proveedor Registrado"
            prov_telefono = ""
            costo_unitario = p_costo
            presentacion_nombre = "Unidad"
            unidades_presentacion = 1.0
            precio_presentacion = p_costo
            
            if selected_quote:
                prov_id = selected_quote['tercero_id']
                prov_nombre = selected_quote['proveedor_nombre']
                prov_telefono = selected_quote['proveedor_telefono'] or ""
                unidades_presentacion = float(selected_quote['unidades_item'])
                precio_presentacion = float(selected_quote['precio'])
                costo_unitario = precio_presentacion / unidades_presentacion
                presentacion_nombre = selected_quote['descripcion_presentacion']
            elif last_purchase:
                prov_id = last_purchase['proveedor_id']
                prov_nombre = last_purchase['proveedor_nombre']
                prov_telefono = last_purchase['proveedor_telefono'] or """

prov_init_replacement = """            prov_id = 0
            prov_nombre = "Sin Proveedor Registrado"
            prov_telefono = ""
            prov_forma_pago = "contado"
            prov_dias_credito = 15
            prov_modalidad = "sede"
            prov_direccion_recogida = ""
            costo_unitario = p_costo
            presentacion_nombre = "Unidad"
            unidades_presentacion = 1.0
            precio_presentacion = p_costo
            
            if selected_quote:
                prov_id = selected_quote['tercero_id']
                prov_nombre = selected_quote['proveedor_nombre']
                prov_telefono = selected_quote['proveedor_telefono'] or ""
                prov_forma_pago = selected_quote['forma_pago_defecto'] or "contado"
                prov_dias_credito = selected_quote['dias_credito'] or 15
                prov_modalidad = selected_quote['modalidad_entrega_defecto'] or "sede"
                prov_direccion_recogida = selected_quote['direccion_recogida'] or ""
                unidades_presentacion = float(selected_quote['unidades_item'])
                precio_presentacion = float(selected_quote['precio'])
                costo_unitario = precio_presentacion / unidades_presentacion
                presentacion_nombre = selected_quote['descripcion_presentacion']
            elif last_purchase:
                prov_id = last_purchase['proveedor_id']
                prov_nombre = last_purchase['proveedor_nombre']
                prov_telefono = last_purchase['proveedor_telefono'] or ""
                prov_forma_pago = last_purchase['forma_pago_defecto'] or "contado"
                prov_dias_credito = last_purchase['dias_credito'] or 15
                prov_modalidad = last_purchase['modalidad_entrega_defecto'] or "sede"
                prov_direccion_recogida = last_purchase['direccion_recogida'] or """

assert prov_init_target in content, "prov_init_target not found in inventarios.py"
content = content.replace(prov_init_target, prov_init_replacement, 1)

prov_map_target = """            if prov_id not in proveedores_map:
                proveedores_map[prov_id] = {
                    'proveedor_id': prov_id,
                    'proveedor_nombre': prov_nombre,
                    'proveedor_telefono': prov_telefono,
                    'total_compras': 0.0,
                    'fecha_limite': 'Sin límite',
                    'fecha_limite_comparable': 99999.0,
                    'productos': []
                }"""

prov_map_replacement = """            if prov_id not in proveedores_map:
                proveedores_map[prov_id] = {
                    'proveedor_id': prov_id,
                    'proveedor_nombre': prov_nombre,
                    'proveedor_telefono': prov_telefono,
                    'forma_pago_defecto': prov_forma_pago,
                    'dias_credito': prov_dias_credito,
                    'modalidad_entrega_defecto': prov_modalidad,
                    'direccion_recogida': prov_direccion_recogida,
                    'total_compras': 0.0,
                    'fecha_limite': 'Sin límite',
                    'fecha_limite_comparable': 99999.0,
                    'productos': []
                }"""

assert prov_map_target in content, "prov_map_target not found in inventarios.py"
content = content.replace(prov_map_target, prov_map_replacement, 1)

item_data_target = """                'iva_pct': float(prod['iva_pct'] or 0.0),"""
item_data_replacement = """                'iva_pct': float(prod['iva_pct'] or 0.0),
                'peso_variable': bool(prod.get('peso_variable', False)),
                'tolerancia_peso_pct': float(prod.get('tolerancia_peso_pct') or 10.0),"""

assert item_data_target in content, "item_data_target not found in inventarios.py"
content = content.replace(item_data_target, item_data_replacement, 1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("inventarios.py successfully patched.")
