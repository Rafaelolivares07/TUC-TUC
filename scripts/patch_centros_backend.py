import sys, os

def patch_restaurantes():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\restaurantes.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update SELECT in admin_restaurante_lista
    old_sel = "SELECT id, nombre, slug, admin_nombre, admin_telefono, token_acceso, dias_pagados "
    new_sel = "SELECT id, nombre, slug, admin_nombre, admin_telefono, token_acceso, dias_pagados, COALESCE(max_centros_utilidad, 1) as max_centros_utilidad "
    if old_sel in content:
        content = content.replace(old_sel, new_sel, 1)
        print("restaurantes.py: SELECT updated")
    else:
        print("restaurantes.py: SELECT already updated or not found")

    # 2. Add endpoint api_admin_restaurante_max_centros
    endpoint_code = """
@bp.route('/api/admin/restaurante/<slug>/max-centros', methods=['POST'])
def api_admin_restaurante_max_centros(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    try:
        max_centros = int(data.get('max_centros_utilidad', 1))
        if max_centros < 1:
            max_centros = 1
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'Número inválido'}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE restaurantes SET max_centros_utilidad = %s WHERE slug = %s",
            (max_centros, slug)
        )
        conn.commit()
        return jsonify({'ok': True, 'max_centros_utilidad': max_centros})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
"""
    if '/api/admin/restaurante/<slug>/max-centros' not in content:
        # Insert before @bp.route('/admin/restaurante/<slug>')
        target = "@bp.route('/admin/restaurante/<slug>')"
        if target in content:
            content = content.replace(target, endpoint_code + "\n\n" + target, 1)
            print("restaurantes.py: max-centros endpoint added")
        else:
            print("restaurantes.py: target for endpoint not found")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_tiendas():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\tiendas.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update SELECT in admin_tienda_lista
    old_sel = "SELECT id, nombre, slug, admin_nombre, admin_telefono, token_acceso, dias_pagados FROM tiendas WHERE activo = TRUE ORDER BY nombre"
    new_sel = "SELECT id, nombre, slug, admin_nombre, admin_telefono, token_acceso, dias_pagados, COALESCE(max_centros_utilidad, 1) as max_centros_utilidad FROM tiendas WHERE activo = TRUE ORDER BY nombre"
    if old_sel in content:
        content = content.replace(old_sel, new_sel, 1)
        print("tiendas.py: SELECT updated")
    else:
        print("tiendas.py: SELECT already updated or not found")

    # 2. Add endpoint api_admin_tienda_max_centros
    endpoint_code = """
@bp.route('/api/admin/tienda/<slug>/max-centros', methods=['POST'])
def api_admin_tienda_max_centros(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    try:
        max_centros = int(data.get('max_centros_utilidad', 1))
        if max_centros < 1:
            max_centros = 1
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'Número inválido'}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE tiendas SET max_centros_utilidad = %s WHERE slug = %s",
            (max_centros, slug)
        )
        conn.commit()
        return jsonify({'ok': True, 'max_centros_utilidad': max_centros})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
"""
    if '/api/admin/tienda/<slug>/max-centros' not in content:
        target = "@bp.route('/admin/tienda/<slug>')"
        if target in content:
            content = content.replace(target, endpoint_code + "\n\n" + target, 1)
            print("tiendas.py: max-centros endpoint added")
        else:
            print("tiendas.py: target for endpoint not found")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_inventarios():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\inventarios.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Helper function _get_max_centros_negocio
    helper_code = """def _get_max_centros_negocio(conn, negocio_id):
    try:
        row_r = conn.execute(
            "SELECT max_centros_utilidad FROM restaurantes WHERE tercero_id = %s AND activo = TRUE LIMIT 1",
            (negocio_id,)
        ).fetchone()
        if row_r and row_r['max_centros_utilidad'] is not None:
            return max(1, int(row_r['max_centros_utilidad']))

        row_t = conn.execute(
            "SELECT max_centros_utilidad FROM tiendas WHERE tercero_id = %s AND activo = TRUE LIMIT 1",
            (negocio_id,)
        ).fetchone()
        if row_t and row_t['max_centros_utilidad'] is not None:
            return max(1, int(row_t['max_centros_utilidad']))
    except Exception:
        pass
    return 1


"""
    if 'def _get_max_centros_negocio' not in content:
        target = "def _mismo_id(a, b):"
        if target in content:
            content = content.replace(target, helper_code + target, 1)
            print("inventarios.py: _get_max_centros_negocio added")

    # 2. In inventario_admin template render (around line 8740)
    old_cu_sel = """        centros_rows = conn.execute(\"\"\"
            SELECT id, codigo, nombre, tipo, color_badge, imagen_url
            FROM centros_utilidad"""
    new_cu_sel = """        centros_rows = conn.execute(\"\"\"
            SELECT id, codigo, nombre, tipo, color_badge, imagen_url, telefono, direccion
            FROM centros_utilidad"""
    if old_cu_sel in content:
        content = content.replace(old_cu_sel, new_cu_sel, 1)
        print("inventarios.py: centros_rows SELECT updated")

    old_render = """        return render_template('inventario_admin.html',
                               negocio_id=negocio_id,
                               negocio_nombre=contexto['negocio_nombre'],
                               volver_url=contexto['volver_url'],
                               volver_label=contexto['volver_label'],
                               centros_utilidad=centros,
                               centro_activo=centro_activo,"""
    new_render = """        max_centros_utilidad = _get_max_centros_negocio(conn, negocio_id)
        return render_template('inventario_admin.html',
                               negocio_id=negocio_id,
                               negocio_nombre=contexto['negocio_nombre'],
                               volver_url=contexto['volver_url'],
                               volver_label=contexto['volver_label'],
                               centros_utilidad=centros,
                               centro_activo=centro_activo,
                               max_centros_utilidad=max_centros_utilidad,"""
    if old_render in content:
        content = content.replace(old_render, new_render, 1)
        print("inventarios.py: render_template updated with max_centros_utilidad")

    # 3. In api_listar_centros_utilidad: add max_centros_utilidad, total_centros, puede_crear
    old_resp = """        return jsonify({
            'ok': True,
            'centros': centros_res,
            'centro_activo': centro_activo,
            'es_multisede': len([c for c in centros_res if c['autorizado']]) > 1
        })"""
    new_resp = """        max_centros = _get_max_centros_negocio(conn, negocio_id)
        return jsonify({
            'ok': True,
            'centros': centros_res,
            'centro_activo': centro_activo,
            'es_multisede': len([c for c in centros_res if c['autorizado']]) > 1,
            'max_centros_utilidad': max_centros,
            'total_centros': len(centros_db),
            'puede_crear': len(centros_db) < max_centros
        })"""
    if old_resp in content:
        content = content.replace(old_resp, new_resp, 1)
        print("inventarios.py: api_listar_centros_utilidad response updated")

    # 4. In api_editar_centro_utilidad: add telefono, direccion
    old_edit = """    color_badge = (data.get('color_badge') or '').strip()
    telegram_chat_id = (data.get('telegram_chat_id') or '').strip() or None"""
    new_edit = """    color_badge = (data.get('color_badge') or '').strip()
    telegram_chat_id = (data.get('telegram_chat_id') or '').strip() or None
    telefono = (data.get('telefono') or '').strip() or None
    direccion = (data.get('direccion') or '').strip() or None"""
    if old_edit in content:
        content = content.replace(old_edit, new_edit, 1)
        print("inventarios.py: api_editar_centro_utilidad inputs updated")

    old_update = """        conn.execute(\"\"\"
            UPDATE centros_utilidad
            SET nombre = %s,
                codigo = %s,
                tipo = %s,
                color_badge = COALESCE(NULLIF(%s, ''), color_badge),
                telegram_chat_id = %s
            WHERE id = %s AND negocio_id = %s
        \"\"\", (nombre, codigo, tipo, color_badge, telegram_chat_id, centro_id, negocio_id))"""
    new_update = """        conn.execute(\"\"\"
            UPDATE centros_utilidad
            SET nombre = %s,
                codigo = %s,
                tipo = %s,
                telefono = %s,
                direccion = %s,
                color_badge = COALESCE(NULLIF(%s, ''), color_badge),
                telegram_chat_id = %s
            WHERE id = %s AND negocio_id = %s
        \"\"\", (nombre, codigo, tipo, telefono, direccion, color_badge, telegram_chat_id, centro_id, negocio_id))"""
    if old_update in content:
        content = content.replace(old_update, new_update, 1)
        print("inventarios.py: api_editar_centro_utilidad UPDATE query updated")

    old_edit_ret = """            'centro': {
                'id': centro_id,
                'nombre': nombre,
                'codigo': codigo,
                'tipo': tipo,
                'color_badge': color_badge,
                'telegram_chat_id': telegram_chat_id
            }"""
    new_edit_ret = """            'centro': {
                'id': centro_id,
                'nombre': nombre,
                'codigo': codigo,
                'tipo': tipo,
                'telefono': telefono,
                'direccion': direccion,
                'color_badge': color_badge,
                'telegram_chat_id': telegram_chat_id
            }"""
    if old_edit_ret in content:
        content = content.replace(old_edit_ret, new_edit_ret, 1)
        print("inventarios.py: api_editar_centro_utilidad return dict updated")

    # 5. Add api_crear_centro_utilidad endpoint
    crear_endpoint = """
@bp.route('/api/centros_utilidad/crear', methods=['POST'])
def api_crear_centro_utilidad():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    negocio_id = data.get('negocio_id')
    nombre = (data.get('nombre') or '').strip()
    codigo = (data.get('codigo') or '').strip().upper()
    tipo = (data.get('tipo') or 'local').strip().lower()
    telefono = (data.get('telefono') or '').strip() or None
    direccion = (data.get('direccion') or '').strip() or None
    color_badge = (data.get('color_badge') or '#0284c7').strip()
    telegram_chat_id = (data.get('telegram_chat_id') or '').strip() or None

    if not negocio_id or not nombre:
        return jsonify({'ok': False, 'error': 'El nombre del centro de utilidad es obligatorio'}), 400

    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        if not _puede_gestionar_negocio(_contexto):
            return jsonify({'ok': False, 'error': 'Solo administradores pueden crear centros de utilidad'}), 403

        # Validar cupo
        max_centros = _get_max_centros_negocio(conn, negocio_id)
        conteo = conn.execute(
            "SELECT COUNT(*) as total FROM centros_utilidad WHERE negocio_id = %s AND activo = TRUE",
            (negocio_id,)
        ).fetchone()['total']

        if conteo >= max_centros:
            return jsonify({
                'ok': False,
                'error': f'Límite alcanzado: Tienes {conteo} de {max_centros} centro(s) permitidos. Solicita a administración ampliar tu cupo.'
            }), 400

        # Si no se pasó código, autogenerar
        if not codigo:
            prefijo = "MOV" if tipo == 'movil' else "SEDE"
            codigo = f"{prefijo}-{conteo + 1:02d}"

        # Validar unicidad de código dentro del negocio
        duplicado = conn.execute(\"\"\"
            SELECT id FROM centros_utilidad
            WHERE negocio_id = %s AND UPPER(codigo) = %s AND activo = TRUE
        \"\"\", (negocio_id, codigo)).fetchone()
        if duplicado:
            return jsonify({'ok': False, 'error': f'El código \"{codigo}\" ya está registrado para este negocio'}), 400

        # Sincronizar secuencia antes de insertar
        conn.execute("SELECT setval('centros_utilidad_id_seq', (SELECT COALESCE(MAX(id), 1) FROM centros_utilidad))")

        nuevo = conn.execute(\"\"\"
            INSERT INTO centros_utilidad (negocio_id, codigo, nombre, tipo, telefono, direccion, color_badge, telegram_chat_id, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id, codigo, nombre, tipo, telefono, direccion, color_badge
        \"\"\", (negocio_id, codigo, nombre, tipo, telefono, direccion, color_badge, telegram_chat_id)).fetchone()

        # Asignar permiso a usuario_id actual si no lo tiene
        u_id = session.get('usuario_id')
        if u_id and nuevo:
            conn.execute(\"\"\"
                INSERT INTO usuarios_centros_utilidad (usuario_id, centro_utilidad_id, rol_en_centro, es_predeterminado)
                VALUES (%s, %s, 'administrador', FALSE)
            \"\"\", (u_id, nuevo['id']))

        conn.commit()

        return jsonify({
            'ok': True,
            'mensaje': f'Centro de utilidad \"{nombre}\" creado exitosamente.',
            'centro': dict(nuevo)
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
"""
    if '/api/centros_utilidad/crear' not in content:
        target = "@bp.route('/api/dispositivos/identificar', methods=['POST'])"
        if target in content:
            content = content.replace(target, crear_endpoint + "\n\n" + target, 1)
            print("inventarios.py: api_crear_centro_utilidad endpoint added")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


if __name__ == '__main__':
    patch_restaurantes()
    patch_tiendas()
    patch_inventarios()
    print("Backend patching finished.")
