import json
from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for
from ..db import get_db_connection

bp = Blueprint('negocios', __name__)

MODALIDADES_CATALOGO = [
    {'codigo': 'domicilio', 'nombre': 'Domicilio',    'icono': '🛵', 'desc': 'El pedido llega a la dirección del cliente'},
    {'codigo': 'recoger',   'nombre': 'Para recoger', 'icono': '🏪', 'desc': 'El cliente recoge en el local'},
    {'codigo': 'mesa',      'nombre': 'Mesa',         'icono': '🍽️', 'desc': 'Pedidos en mesa (restaurantes)'},
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
    conn.commit()


def _get_config(conn, tercero_id):
    row = conn.execute(
        "SELECT modalidades, metodos_pago, aviso_pedido FROM config_negocio WHERE tercero_id=%s",
        (tercero_id,)
    ).fetchone()
    if row:
        return {
            'modalidades':  row['modalidades'],
            'metodos_pago': row['metodos_pago'],
            'aviso_pedido': row['aviso_pedido'],
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
            }
    except Exception:
        pass
    return {'modalidades': ['domicilio', 'recoger'], 'metodos_pago': ['efectivo'], 'aviso_pedido': None}


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
                "SELECT id, nombre, codigo, icono FROM metodos_pago_catalogo WHERE activo=TRUE ORDER BY orden, id"
            ).fetchall()
            catalogo = [dict(m) for m in catalogo]
        except Exception:
            catalogo = [{'id': 0, 'nombre': 'Efectivo', 'codigo': 'efectivo', 'icono': '💵'}]
        return jsonify({'ok': True, 'config': config, 'catalogo_metodos': catalogo})
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
        return jsonify({
            'ok': True,
            'modalidades':  config['modalidades'],
            'metodos_pago': metodos,
            'aviso_pedido': config['aviso_pedido'],
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
