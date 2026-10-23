import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'blueprints', 'inventarios.py')
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add auditoria_recosteos table to _crear_tablas
t1 = '''"CREATE UNIQUE INDEX IF NOT EXISTS idx_entradas_borradores_neg_user ON entradas_borradores(negocio_id, COALESCE(usuario_id, 0))",'''
r1 = '''"CREATE UNIQUE INDEX IF NOT EXISTS idx_entradas_borradores_neg_user ON entradas_borradores(negocio_id, COALESCE(usuario_id, 0))",
        """CREATE TABLE IF NOT EXISTS auditoria_recosteos (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL REFERENCES terceros(id),
            producto_id INTEGER REFERENCES productos(id),
            producto_nombre VARCHAR(255),
            origen VARCHAR(80),
            documento_tipo VARCHAR(100),
            documento_numero VARCHAR(100),
            usuario_id INTEGER,
            usuario_nombre VARCHAR(150),
            costo_anterior NUMERIC(16, 4),
            costo_nuevo NUMERIC(16, 4),
            stock_final NUMERIC(16, 4),
            movimientos_afectados INTEGER DEFAULT 0,
            detalles JSONB,
            fecha_hora TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_recosteos_negocio ON auditoria_recosteos(negocio_id, fecha_hora DESC)",'''

# 2. Lock fecha in api_produccion_registrar
t2 = '''    fecha_raw   = (_txt(data.get('fecha')) or '').strip()
    hoy_colombia = _hoy_bogota()
    fecha_prod  = _fecha_o_none(fecha_raw) or hoy_colombia'''

r2 = '''    # En la pestaña de producción la fecha está estrictamente bloqueada a la fecha actual
    hoy_colombia = _hoy_bogota()
    fecha_prod  = hoy_colombia'''

# 3. Update calls in api_produccion_registrar
t3 = '''        # Recostear componentes y producto terminado en la bodega
        for c in componentes_datos:
            _recostear_producto(conn, negocio_id, c['componente_id'], bodega=centro_utilidad_id)
        _recostear_producto(conn, negocio_id, producto_id, bodega=centro_utilidad_id)'''

r3 = '''        # Recostear componentes y producto terminado en la bodega con auditoría
        for c in componentes_datos:
            _recostear_producto(conn, negocio_id, c['componente_id'], bodega=centro_utilidad_id, origen='produccion', doc_tipo=tipo_documento, doc_num=documento_numero)
        _recostear_producto(conn, negocio_id, producto_id, bodega=centro_utilidad_id, origen='produccion', doc_tipo=tipo_documento, doc_num=documento_numero)'''

# 4. Update _recostear_producto signature and logging at the end
t4 = '''def _recostear_producto(conn, negocio_id, producto_id, bodega=None):'''
r4 = '''def _recostear_producto(conn, negocio_id, producto_id, bodega=None, origen=None, doc_tipo=None, doc_num=None, usuario_id=None, usuario_nombre=None):'''

t5 = '''    if costo_catalogo > 0:
        conn.execute("""
            UPDATE productos
            SET costo = %s
            WHERE id = %s AND negocio_id = %s
        """, (costo_catalogo, producto_id, negocio_id))

    return {
        'producto_id': producto_id,'''

r5 = '''    if costo_catalogo > 0:
        conn.execute("""
            UPDATE productos
            SET costo = %s
            WHERE id = %s AND negocio_id = %s
        """, (costo_catalogo, producto_id, negocio_id))

    # --- REGISTRO DE AUDITORÍA DE RECOSTEO ---
    u_id = usuario_id
    u_nom = usuario_nombre
    if not u_id:
        try:
            from flask import session as flask_session
            u_id = flask_session.get('usuario_id')
            u_nom = u_nom or flask_session.get('nombre') or flask_session.get('username')
        except Exception:
            pass

    orig = origen or 'sistema'
    try:
        import json
        conn.execute("""
            INSERT INTO auditoria_recosteos 
            (negocio_id, producto_id, producto_nombre, origen, documento_tipo, documento_numero,
             usuario_id, usuario_nombre, costo_anterior, costo_nuevo, stock_final,
             movimientos_afectados, detalles, fecha_hora)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        """, (
            negocio_id, producto_id, prod_nombre, orig, doc_tipo, str(doc_num) if doc_num is not None else None,
            u_id, u_nom, costo_anterior_meta, costo_catalogo, float(total_stk),
            tot_movs_ajust, json.dumps({
                'movimientos_procesados': tot_movs_proc,
                'asientos_14_ajustados': tot_as14_ajust,
                'asientos_cp_ajustados': tot_ascp_ajust,
                'pedidos_ajustados': tot_ped_ajust,
                'cambios_detalle': cambios_detalle[:5]
            })
        ))
    except Exception as _e_aud:
        print(f"[auditoria_recosteo] error registrando: {_e_aud}")

    return {
        'producto_id': producto_id,'''

# 5. Update api_ejecutar_recosteo calls
t6 = '''            res_p = _recostear_producto(conn, negocio_id, producto_id, bodega=bodega_id)'''
r6 = '''            res_p = _recostear_producto(conn, negocio_id, producto_id, bodega=bodega_id, origen='manual_kardex', doc_tipo='MANUAL_KARDEX', doc_num=f'Prod #{producto_id}')'''

t7 = '''        for extra_pid in prods_recostear_extra:
            _recostear_producto(conn, negocio_id, extra_pid, bodega=bodega_id)'''
r7 = '''        for extra_pid in prods_recostear_extra:
            _recostear_producto(conn, negocio_id, extra_pid, bodega=bodega_id, origen='propagacion_produccion', doc_tipo='PRODUCCION_LOTE', doc_num=f'Prod #{extra_pid}')'''

# 6. Add api_historial_recosteo route
t8 = '''@bp.route('/api/inventario/<int:negocio_id>/documento/verificar-cambio-fecha', methods=['POST'])
def api_verificar_cambio_fecha_documento(negocio_id):'''

r8 = '''@bp.route('/api/inventario/<int:negocio_id>/recosteo/historial', methods=['GET'])
def api_historial_recosteo(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        _crear_tablas(conn)
        limite = min(100, max(10, int(request.args.get('limite', 50))))
        producto_id = request.args.get('producto_id', type=int)

        params = [negocio_id]
        where_p = ""
        if producto_id:
            where_p = "AND ar.producto_id = %s"
            params.append(producto_id)

        params.append(limite)
        rows = conn.execute(f"""
            SELECT ar.id, ar.producto_id, ar.producto_nombre, ar.origen,
                   ar.documento_tipo, ar.documento_numero, ar.usuario_nombre,
                   ar.costo_anterior, ar.costo_nuevo, ar.stock_final,
                   ar.movimientos_afectados, ar.detalles,
                   TO_CHAR(ar.fecha_hora AT TIME ZONE 'America/Bogota', 'YYYY-MM-DD HH24:MI:SS') AS fecha_hora
            FROM auditoria_recosteos ar
            WHERE ar.negocio_id = %s {where_p}
            ORDER BY ar.id DESC
            LIMIT %s
        """, params).fetchall()

        return jsonify({
            'ok': True,
            'historial': [dict(r) for r in rows]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/documento/verificar-cambio-fecha', methods=['POST'])
def api_verificar_cambio_fecha_documento(negocio_id):'''

# Normalize
content_norm = content.replace('\r\n', '\n')
replacements = [
    (t1, r1, "t1 _crear_tablas"),
    (t2, r2, "t2 lock fecha_prod"),
    (t3, r3, "t3 recostear produccion"),
    (t4, r4, "t4 def _recostear_producto"),
    (t5, r5, "t5 auditoria logging"),
    (t6, r6, "t6 manual_kardex call"),
    (t7, r7, "t7 extra_pid call"),
    (t8, r8, "t8 api_historial_recosteo route")
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
print("Finished patching inventarios.py")
