import json
from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for
from ..db import get_db_connection

bp = Blueprint('negocios', __name__)

MODALIDADES_CATALOGO = [
    {'codigo': 'domicilio', 'nombre': 'Domicilio',    'icono': '🛵', 'desc': 'El pedido llega a la dirección del cliente'},
    {'codigo': 'recoger',   'nombre': 'Para recoger', 'icono': '🏪', 'desc': 'El cliente recoge en el local'},
]


_METODOS_PAGO_CATALOGO = [
    ('Efectivo',       'efectivo',       '💵', 1,  None),
    ('Nequi Celular',  'nequi_movil',    '📱', 22, 'nequi'),
    ('Nequi QR',       'nequi_qr',       '📲', 21, 'nequi'),
    ('Bancolombia',    'bancolombia',    '🏦', 3,  None),
    ('Daviplata',      'daviplata',      '📲', 4,  None),
    ('Tarjeta débito', 'tarjeta_debito', '💳', 5,  None),
    ('Tarjeta crédito','tarjeta_credito','💳', 6,  None),
    ('Transferencia',  'transferencia',  '🔄', 7,  None),
    ('Contraentrega',  'contraentrega',  '📦', 8,  None),
]


def init_config_negocio(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_negocio (
            tercero_id   INTEGER PRIMARY KEY REFERENCES terceros(id),
            modalidades  JSONB NOT NULL DEFAULT '["domicilio","recoger"]',
            metodos_pago JSONB NOT NULL DEFAULT '["efectivo"]',
            aviso_pedido TEXT,
            updated_at   TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS metodos_info JSONB DEFAULT '{}'")

    # Garantizar que el catálogo de métodos de pago esté completo en prod
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metodos_pago_catalogo (
            id     SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL,
            codigo VARCHAR(30) UNIQUE NOT NULL,
            icono  VARCHAR(10) DEFAULT '💳',
            orden  INTEGER DEFAULT 99,
            activo BOOLEAN DEFAULT TRUE
        )
    """)
    conn.execute("ALTER TABLE metodos_pago_catalogo ADD COLUMN IF NOT EXISTS grupo VARCHAR(30)")
    for nombre, codigo, icono, orden, grupo in _METODOS_PAGO_CATALOGO:
        conn.execute("""
            INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (codigo) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                icono  = EXCLUDED.icono,
                orden  = EXCLUDED.orden,
                grupo  = EXCLUDED.grupo
        """, (nombre, codigo, icono, orden, grupo))
    # 'nequi' legacy desactivado — reemplazado por nequi_movil y nequi_qr
    conn.execute("""
        INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo)
        VALUES ('Bancolombia QR', 'bancolombia_qr', '🏦', 31, 'bancolombia')
        ON CONFLICT (codigo) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            icono = EXCLUDED.icono,
            orden = EXCLUDED.orden,
            grupo = EXCLUDED.grupo,
            activo = TRUE
    """)
    conn.execute("""
        INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo)
        VALUES ('Llave bancaria', 'llave', '🔑', 32, NULL)
        ON CONFLICT (codigo) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            icono = EXCLUDED.icono,
            orden = EXCLUDED.orden,
            grupo = EXCLUDED.grupo,
            activo = TRUE
    """)
    conn.execute("""
        UPDATE metodos_pago_catalogo
        SET nombre = 'Contraentrega en efectivo'
        WHERE codigo = 'contraentrega'
    """)
    conn.execute("UPDATE metodos_pago_catalogo SET activo = FALSE WHERE codigo = 'nequi'")
    conn.commit()


def _get_config(conn, tercero_id):
    row = conn.execute(
        "SELECT modalidades, metodos_pago, aviso_pedido, metodos_info FROM config_negocio WHERE tercero_id=%s",
        (tercero_id,)
    ).fetchone()
    if row:
        return {
            'modalidades':  row['modalidades'],
            'metodos_pago': row['metodos_pago'],
            'aviso_pedido': row['aviso_pedido'],
            'metodos_info': dict(row['metodos_info'] or {}),
        }
    # Migrar datos existentes de metodos_pago_tienda si los hay
    try:
        existentes = conn.execute("""
            SELECT c.codigo FROM metodos_pago_tienda t
            JOIN metodos_pago_catalogo c ON c.id = t.catalogo_id
            JOIN tiendas ti ON ti.id = t.tienda_id
            WHERE ti.tercero_id = %s AND t.activo = TRUE AND c.activo = TRUE
        """, (tercero_id,)).fetchall()
        if existentes:
            return {
                'modalidades':  ['domicilio', 'recoger'],
                'metodos_pago': [m['codigo'] for m in existentes],
                'aviso_pedido': None,
                'metodos_info': {},
            }
    except Exception:
        pass
    return {'modalidades': ['domicilio', 'recoger'], 'metodos_pago': ['efectivo'], 'aviso_pedido': None, 'metodos_info': {}}


@bp.route('/admin/negocio/<int:tercero_id>/config')
def admin_config_negocio(tercero_id):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        negocio = conn.execute("SELECT nombre FROM terceros WHERE id=%s", (tercero_id,)).fetchone()
        nombre = negocio['nombre'] if negocio else f'Negocio #{tercero_id}'
    finally:
        conn.close()
    return render_template('negocio_config.html',
                           tercero_id=tercero_id,
                           nombre=nombre,
                           modalidades_catalogo=MODALIDADES_CATALOGO)


@bp.route('/api/negocio/<int:tercero_id>/config', methods=['GET'])
def api_config_get(tercero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        config = _get_config(conn, tercero_id)
        try:
            catalogo = conn.execute(
                "SELECT id, nombre, codigo, icono, grupo FROM metodos_pago_catalogo WHERE activo=TRUE ORDER BY orden, id"
            ).fetchall()
            catalogo = [dict(m) for m in catalogo]
        except Exception:
            catalogo = [{'id': 0, 'nombre': 'Efectivo', 'codigo': 'efectivo', 'icono': '💵'}]
        return jsonify({'ok': True, 'config': config, 'catalogo_metodos': catalogo, 'metodos_info': config.get('metodos_info', {})})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/negocio/<int:tercero_id>/config', methods=['POST'])
def api_config_save(tercero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    modalidades  = data.get('modalidades', ['domicilio', 'recoger'])
    metodos_pago = data.get('metodos_pago', ['efectivo'])
    aviso_pedido = (data.get('aviso_pedido') or '').strip() or None
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO config_negocio (tercero_id, modalidades, metodos_pago, aviso_pedido, updated_at)
            VALUES (%s, %s::jsonb, %s::jsonb, %s, NOW())
            ON CONFLICT (tercero_id) DO UPDATE SET
                modalidades  = EXCLUDED.modalidades,
                metodos_pago = EXCLUDED.metodos_pago,
                aviso_pedido = EXCLUDED.aviso_pedido,
                updated_at   = NOW()
        """, (tercero_id, json.dumps(modalidades), json.dumps(metodos_pago), aviso_pedido))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/negocio/<int:tercero_id>/config/publica')
def api_config_publica(tercero_id):
    conn = get_db_connection()
    try:
        config = _get_config(conn, tercero_id)
        try:
            catalogo = conn.execute(
                "SELECT nombre, codigo, icono FROM metodos_pago_catalogo WHERE activo=TRUE"
            ).fetchall()
            catalogo_dict = {m['codigo']: dict(m) for m in catalogo}
        except Exception:
            catalogo_dict = {'efectivo': {'nombre': 'Efectivo', 'codigo': 'efectivo', 'icono': '💵'}}
        metodos = [catalogo_dict[c] for c in config['metodos_pago'] if c in catalogo_dict]
        metodos_info = config.get('metodos_info', {})
        # No exponer imágenes QR completas en la respuesta pública — sólo indicar si existe
        info_publica = {}
        for codigo, info in metodos_info.items():
            entrada = {}
            if 'imagen' in info:
                entrada['imagen'] = info['imagen']
            if 'numero' in info:
                entrada['numero'] = info['numero']
            if entrada:
                info_publica[codigo] = entrada
        return jsonify({
            'ok': True,
            'modalidades':  config['modalidades'],
            'metodos_pago': metodos,
            'aviso_pedido': config['aviso_pedido'],
            'metodos_info': info_publica,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/pagar/<int:pedido_id>')
def pagar(pedido_id):
    tipo = request.args.get('tipo', '')
    conn = get_db_connection()
    try:
        if tipo == 'tienda':
            row = conn.execute("""
                SELECT t.tercero_id, t.nombre, t.slug, p.total
                FROM pedidos_tienda p JOIN tiendas t ON t.id = p.tienda_id
                WHERE p.id = %s
            """, (pedido_id,)).fetchone()
        else:
            row = conn.execute("""
                SELECT r.tercero_id, r.nombre, r.slug, p.precio AS total
                FROM pedidos_restaurante p JOIN restaurantes r ON r.id = p.restaurante_id
                WHERE p.id = %s
            """, (pedido_id,)).fetchone()
        if not row:
            return "Pedido no encontrado", 404
        return render_template('pagar.html',
                               pedido_id=pedido_id,
                               tipo=tipo,
                               tercero_id=row['tercero_id'],
                               negocio_nombre=row['nombre'],
                               negocio_slug=row['slug'],
                               total=float(row['total'] or 0))
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/api/pagar/<int:pedido_id>', methods=['POST'])
def api_pagar(pedido_id):
    data = request.get_json() or {}
    tipo        = data.get('tipo', '')
    pagos       = data.get('pagos') or []
    comprobante = data.get('comprobante') or None
    metodo_pago = (pagos[0].get('codigo') if pagos and isinstance(pagos[0], dict) else None) or (data.get('metodo_pago') or '').strip() or None
    if not metodo_pago:
        return jsonify({'ok': False, 'error': 'Selecciona un método de pago'}), 400
    conn = get_db_connection()
    try:
        if tipo == 'tienda':
            total_row = conn.execute("SELECT total FROM pedidos_tienda WHERE id=%s", (pedido_id,)).fetchone()
            total_pedido = float(total_row['total'] or 0) if total_row else 0
            conn.execute(
                "UPDATE pedidos_tienda SET metodo_pago=%s, comprobante_pago=%s WHERE id=%s",
                (metodo_pago, comprobante, pedido_id)
            )
            conn.execute("DELETE FROM pedido_pagos_tienda WHERE pedido_id=%s", (pedido_id,))
            pagos_validos = [p for p in pagos if isinstance(p, dict) and float(p.get('monto') or 0) > 0]
            if pagos_validos:
                for pago in pagos_validos:
                    conn.execute("""
                        INSERT INTO pedido_pagos_tienda (pedido_id, metodo_codigo, metodo_nombre, monto)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        pedido_id,
                        pago.get('codigo') or metodo_pago,
                        pago.get('nombre') or pago.get('codigo') or metodo_pago,
                        float(pago.get('monto') or 0),
                    ))
            else:
                conn.execute("""
                    INSERT INTO pedido_pagos_tienda (pedido_id, metodo_codigo, metodo_nombre, monto)
                    VALUES (%s, %s, %s, %s)
                """, (pedido_id, metodo_pago, metodo_pago, total_pedido))
        else:
            _asegurar_pagos_restaurante(conn)
            total_row = conn.execute("""
                SELECT COALESCE(precio, 0) * COALESCE(cantidad, 1) AS total
                FROM pedidos_restaurante
                WHERE id=%s
            """, (pedido_id,)).fetchone()
            total_pedido = float(total_row['total'] or 0) if total_row else 0
            conn.execute(
                "UPDATE pedidos_restaurante SET metodo_pago=%s, comprobante_pago=%s WHERE id=%s",
                (metodo_pago, comprobante, pedido_id)
            )
            conn.execute("DELETE FROM pedido_pagos_restaurante WHERE pedido_id=%s", (pedido_id,))
            pagos_validos = [p for p in pagos if isinstance(p, dict) and float(p.get('monto') or 0) > 0]
            if pagos_validos:
                for pago in pagos_validos:
                    conn.execute("""
                        INSERT INTO pedido_pagos_restaurante (pedido_id, metodo_codigo, metodo_nombre, monto)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        pedido_id,
                        pago.get('codigo') or metodo_pago,
                        pago.get('nombre') or pago.get('codigo') or metodo_pago,
                        float(pago.get('monto') or 0),
                    ))
            else:
                conn.execute("""
                    INSERT INTO pedido_pagos_restaurante (pedido_id, metodo_codigo, metodo_nombre, monto)
                    VALUES (%s, %s, %s, %s)
                """, (pedido_id, metodo_pago, metodo_pago, total_pedido))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


def _asegurar_pagos_restaurante(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pedido_pagos_restaurante (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL,
            metodo_codigo VARCHAR(50),
            metodo_nombre VARCHAR(100),
            monto NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedido_pagos_restaurante_pedido
        ON pedido_pagos_restaurante(pedido_id)
    """)


@bp.route('/api/negocio/<int:tercero_id>/metodo-info', methods=['POST'])
def api_metodo_info(tercero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    codigo = (data.get('codigo') or '').strip()
    info   = data.get('info', {})
    if not codigo:
        return jsonify({'ok': False, 'error': 'Código requerido'}), 400
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT metodos_info FROM config_negocio WHERE tercero_id=%s", (tercero_id,)
        ).fetchone()
        actual = dict(row['metodos_info'] or {}) if row else {}
        if info:
            actual[codigo] = info
        else:
            actual.pop(codigo, None)
        conn.execute("""
            INSERT INTO config_negocio (tercero_id, metodos_info, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (tercero_id) DO UPDATE
            SET metodos_info = EXCLUDED.metodos_info, updated_at = NOW()
        """, (tercero_id, json.dumps(actual)))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
