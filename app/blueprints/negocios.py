import json
import re
import socket
from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for
from ..db import get_db_connection
from ..dominios_negocio import (
    asegurar_tabla_dominios_negocio,
    normalizar_dominio_publico,
)

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


def _telegram_label_pago(codigo):
    labels = {
        'efectivo': 'Efectivo',
        'contraentrega': 'Contraentrega en efectivo',
        'llave': 'Llave bancaria',
        'qr_bancolombia': 'QR Bancolombia',
        'transferencia': 'Transferencia',
        'tarjeta_debito': 'Tarjeta debito',
        'tarjeta_credito': 'Tarjeta credito',
        'nequi': 'Nequi',
        'daviplata': 'Daviplata',
        'nequi_movil': 'Nequi celular',
        'nequi_qr': 'Nequi QR',
        'bancolombia': 'Bancolombia',
    }
    key = (codigo or '').strip().lower()
    return labels.get(key, codigo or 'Sin definir')


def _telegram_resumen_pagos(pagos, metodo_pago, total):
    pagos_validos = [
        p for p in (pagos or [])
        if isinstance(p, dict) and float(p.get('monto') or 0) > 0
    ]
    if not pagos_validos:
        pagos_validos = [{'codigo': metodo_pago or 'efectivo', 'nombre': metodo_pago or 'efectivo', 'monto': total}]
    partes = []
    contraentrega = False
    for pago in pagos_validos:
        codigo = (pago.get('codigo') or metodo_pago or '').strip()
        nombre = pago.get('nombre') or _telegram_label_pago(codigo)
        if codigo.lower() == 'contraentrega':
            contraentrega = True
            nombre = 'Contraentrega en efectivo'
        partes.append(f"{nombre}: ${float(pago.get('monto') or 0):,.0f}")
    alerta = "\n⚠️ Contraentrega: cobrar efectivo al entregar." if contraentrega else ""
    return ' + '.join(partes) + alerta


def _telegram_entrega(tipo_entrega, direccion=None, mesa=None):
    if tipo_entrega == 'domicilio':
        return f"Domicilio. Llevar a: {direccion or 'direccion pendiente'}"
    if tipo_entrega == 'recoger':
        return "Cliente recoge en el local."
    if tipo_entrega == 'caja':
        return "Entrega en el local / caja."
    if tipo_entrega == 'mesa':
        return f"Consumo / entrega en mesa: {mesa or 'mesa sin nombre'}"
    return f"{tipo_entrega or 'Pedido'}: {direccion or mesa or 'N/A'}"


def _enviar_telegram_negocio(conn, chat_id, texto):
    if not chat_id:
        return
    try:
        import os
        import requests as req
        token = ''
        try:
            config = conn.execute(
                'SELECT telegram_token FROM "CONFIGURACION_SISTEMA" WHERE id = 1'
            ).fetchone()
            if config:
                token = config['telegram_token'] or ''
        except Exception:
            pass
        token = token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if not token:
            return
        req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception as exc:
        print(f'[telegram pago] envio fallido: {exc}')


def _chat_id_negocio(conn, chat_id=None, admin_id=None):
    if chat_id:
        return chat_id
    if admin_id:
        admin = conn.execute(
            "SELECT telegram_chat_id FROM terceros WHERE id = %s", (admin_id,)
        ).fetchone()
        if admin and admin['telegram_chat_id']:
            return admin['telegram_chat_id']
    try:
        config = conn.execute(
            'SELECT telegram_chat_id FROM "CONFIGURACION_SISTEMA" WHERE id = 1'
        ).fetchone()
        return config['telegram_chat_id'] if config else None
    except Exception:
        return None


def _notificar_pago_pedido(conn, tipo, pedido_id, pagos, metodo_pago):
    if tipo == 'tienda':
        row = conn.execute("""
            SELECT p.id, p.total, p.nombre_cliente, p.telefono_cliente, p.tipo_entrega,
                   p.direccion_cliente, t.nombre AS negocio, t.telegram_chat_id, t.admin_id
            FROM pedidos_tienda p
            JOIN tiendas t ON t.id = p.tienda_id
            WHERE p.id = %s
        """, (pedido_id,)).fetchone()
        if not row:
            return
        total = float(row['total'] or 0)
        entrega = _telegram_entrega(row['tipo_entrega'], row['direccion_cliente'])
    else:
        row = conn.execute("""
            SELECT p.id, COALESCE(p.precio, 0) * COALESCE(p.cantidad, 1) + COALESCE(p.valor_domicilio, 0) AS total,
                   p.nombre_cliente, p.telefono_cliente, p.tipo_entrega, p.direccion_cliente,
                   p.mesa_nombre, r.nombre AS negocio, r.admin_id
            FROM pedidos_restaurante p
            JOIN restaurantes r ON r.id = p.restaurante_id
            WHERE p.id = %s
        """, (pedido_id,)).fetchone()
        if not row:
            return
        total = float(row['total'] or 0)
        entrega = _telegram_entrega(row['tipo_entrega'], row['direccion_cliente'], row['mesa_nombre'])
    try:
        chat_directo = row['telegram_chat_id']
    except Exception:
        chat_directo = None
    chat_id = _chat_id_negocio(conn, chat_directo, row['admin_id'])
    if not chat_id:
        return
    pagos_txt = _telegram_resumen_pagos(pagos, metodo_pago, total)
    msg = (
        f"💳 <b>Pago / forma de pago registrada</b>\n"
        f"🏪 {row['negocio']}\n"
        f"🧾 Pedido #{pedido_id}\n"
        f"👤 {row['nombre_cliente'] or 'Cliente'} - {row['telefono_cliente'] or 'Sin telefono'}\n"
        f"📦 Entrega: {entrega}\n"
        f"💳 Pago elegido: {pagos_txt}\n"
        f"💰 Total: ${total:,.0f}"
    )
    _enviar_telegram_negocio(conn, chat_id, msg)


def _asegurar_domicilio_restaurante(conn):
    alters = [
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS valor_domicilio NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS domicilio_estado VARCHAR(30) DEFAULT 'no_aplica'",
    ]
    for sql in alters:
        conn.execute(sql)


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
    conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS domicilio_tarifa NUMERIC(12,2) DEFAULT 0")
    conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS domicilio_modo_fuera VARCHAR(20) DEFAULT 'por_confirmar'")
    conn.execute("ALTER TABLE config_negocio ADD COLUMN IF NOT EXISTS domicilio_zona JSONB DEFAULT '[]'")

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
        """SELECT modalidades, metodos_pago, aviso_pedido, metodos_info,
                  domicilio_tarifa, domicilio_modo_fuera, domicilio_zona
           FROM config_negocio WHERE tercero_id=%s""",
        (tercero_id,)
    ).fetchone()
    if row:
        return {
            'modalidades':  row['modalidades'],
            'metodos_pago': row['metodos_pago'],
            'aviso_pedido': row['aviso_pedido'],
            'metodos_info': dict(row['metodos_info'] or {}),
            'domicilio_tarifa': float(row['domicilio_tarifa'] or 0),
            'domicilio_modo_fuera': row['domicilio_modo_fuera'] or 'por_confirmar',
            'domicilio_zona': row['domicilio_zona'] or [],
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
                'domicilio_tarifa': 0,
                'domicilio_modo_fuera': 'por_confirmar',
                'domicilio_zona': [],
            }
    except Exception:
        pass
    return {
        'modalidades': ['domicilio', 'recoger'], 'metodos_pago': ['efectivo'],
        'aviso_pedido': None, 'metodos_info': {}, 'domicilio_tarifa': 0,
        'domicilio_modo_fuera': 'por_confirmar', 'domicilio_zona': []
    }


def _negocios_del_tercero(conn, tercero_id):
    negocios = []
    for tipo, tabla in (('tienda', 'tiendas'), ('restaurante', 'restaurantes')):
        try:
            rows = conn.execute(f"""
                SELECT id, nombre, slug
                FROM {tabla}
                WHERE tercero_id = %s AND COALESCE(activo, TRUE) = TRUE
                ORDER BY nombre
            """, (tercero_id,)).fetchall()
            for row in rows:
                negocios.append({
                    'tipo_negocio': tipo,
                    'negocio_id': row['id'],
                    'nombre': row['nombre'],
                    'slug': row['slug'],
                    'url_actual': f"https://{row['slug']}.tuc-tuc.co",
                })
        except Exception:
            pass
    return negocios


def _negocio_pertenece_tercero(conn, tercero_id, tipo_negocio, negocio_id):
    tabla = 'tiendas' if tipo_negocio == 'tienda' else 'restaurantes' if tipo_negocio == 'restaurante' else ''
    if not tabla:
        return False
    row = conn.execute(
        f"SELECT 1 FROM {tabla} WHERE id=%s AND tercero_id=%s LIMIT 1",
        (negocio_id, tercero_id)
    ).fetchone()
    return bool(row)


def _estado_dns(dominio):
    try:
        ip = socket.gethostbyname(dominio)
        return {'ok': True, 'ip': ip, 'mensaje': f'DNS responde en {ip}'}
    except Exception:
        return {'ok': False, 'ip': None, 'mensaje': 'Aun no responde en DNS'}


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
        init_config_negocio(conn)
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


@bp.route('/api/negocio/<int:tercero_id>/dominios', methods=['GET'])
def api_dominios_get(tercero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        asegurar_tabla_dominios_negocio(conn)
        negocios = _negocios_del_tercero(conn, tercero_id)
        rows = conn.execute("""
            SELECT id, tipo_negocio, negocio_id, dominio, activo, verificado,
                   principal, estado, updated_at
            FROM dominios_negocio
            WHERE (tipo_negocio, negocio_id) IN (
                SELECT 'tienda', id FROM tiendas WHERE tercero_id = %s
                UNION ALL
                SELECT 'restaurante', id FROM restaurantes WHERE tercero_id = %s
            )
            ORDER BY principal DESC, id DESC
        """, (tercero_id, tercero_id)).fetchall()
        dominios = []
        for row in rows:
            item = {k: row[k] for k in row.keys()}
            if item.get('updated_at'):
                item['updated_at'] = item['updated_at'].isoformat()
            dominios.append(item)
        return jsonify({
            'ok': True,
            'negocios': negocios,
            'dominios': dominios,
            'dns': {
                'cname': 'tuc-tuc.co',
                'nota': 'Crea un CNAME hacia tuc-tuc.co o apunta el dominio al proxy de Tuc Tuc.',
            }
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/negocio/<int:tercero_id>/dominios', methods=['POST'])
def api_dominios_save(tercero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    tipo_negocio = (data.get('tipo_negocio') or '').strip().lower()
    negocio_id = int(data.get('negocio_id') or 0)
    dominio = normalizar_dominio_publico(data.get('dominio'))
    if tipo_negocio not in ('tienda', 'restaurante') or not negocio_id:
        return jsonify({'ok': False, 'error': 'Selecciona el negocio'}), 400
    if not dominio or not re.match(r'^[a-z0-9.-]+\.[a-z]{2,}$', dominio):
        return jsonify({'ok': False, 'error': 'Dominio no valido'}), 400
    if dominio.endswith('.tuc-tuc.co') or dominio in ('tuc-tuc.co', 'admin.tuc-tuc.co'):
        return jsonify({'ok': False, 'error': 'Usa esta opcion solo para dominios propios'}), 400
    conn = get_db_connection()
    try:
        asegurar_tabla_dominios_negocio(conn)
        if not _negocio_pertenece_tercero(conn, tercero_id, tipo_negocio, negocio_id):
            return jsonify({'ok': False, 'error': 'Ese negocio no pertenece a este usuario'}), 403
        dns = _estado_dns(dominio)
        row = conn.execute("SELECT id, tipo_negocio, negocio_id FROM dominios_negocio WHERE LOWER(dominio)=%s", (dominio,)).fetchone()
        if row and (row['tipo_negocio'] != tipo_negocio or int(row['negocio_id']) != negocio_id):
            return jsonify({'ok': False, 'error': 'Ese dominio ya esta asociado a otro negocio'}), 409
        if row:
            conn.execute("""
                UPDATE dominios_negocio
                SET activo=TRUE, verificado=%s, estado=%s, updated_at=NOW()
                WHERE id=%s
            """, (dns['ok'], 'verificado' if dns['ok'] else 'pendiente_dns', row['id']))
            dominio_id = row['id']
        else:
            inserted = conn.execute("""
                INSERT INTO dominios_negocio (
                    tipo_negocio, negocio_id, dominio, activo, verificado, principal, estado, updated_at
                )
                VALUES (%s, %s, %s, TRUE, %s, FALSE, %s, NOW())
                RETURNING id
            """, (tipo_negocio, negocio_id, dominio, dns['ok'], 'verificado' if dns['ok'] else 'pendiente_dns')).fetchone()
            dominio_id = inserted['id']
        conn.commit()
        return jsonify({'ok': True, 'id': dominio_id, 'dominio': dominio, 'dns': dns})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/negocio/<int:tercero_id>/dominios/<int:dominio_id>/verificar', methods=['POST'])
def api_dominios_verificar(tercero_id, dominio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        asegurar_tabla_dominios_negocio(conn)
        row = conn.execute("""
            SELECT d.*
            FROM dominios_negocio d
            WHERE d.id = %s AND (d.tipo_negocio, d.negocio_id) IN (
                SELECT 'tienda', id FROM tiendas WHERE tercero_id = %s
                UNION ALL
                SELECT 'restaurante', id FROM restaurantes WHERE tercero_id = %s
            )
        """, (dominio_id, tercero_id, tercero_id)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Dominio no encontrado'}), 404
        dns = _estado_dns(row['dominio'])
        conn.execute("""
            UPDATE dominios_negocio
            SET verificado=%s, estado=%s, updated_at=NOW()
            WHERE id=%s
        """, (dns['ok'], 'verificado' if dns['ok'] else 'pendiente_dns', dominio_id))
        conn.commit()
        return jsonify({'ok': True, 'dns': dns})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/negocio/<int:tercero_id>/dominios/<int:dominio_id>', methods=['DELETE'])
def api_dominios_delete(tercero_id, dominio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        asegurar_tabla_dominios_negocio(conn)
        conn.execute("""
            UPDATE dominios_negocio
            SET activo=FALSE, principal=FALSE, updated_at=NOW()
            WHERE id = %s AND (tipo_negocio, negocio_id) IN (
                SELECT 'tienda', id FROM tiendas WHERE tercero_id = %s
                UNION ALL
                SELECT 'restaurante', id FROM restaurantes WHERE tercero_id = %s
            )
        """, (dominio_id, tercero_id, tercero_id))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
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
    domicilio_tarifa = float(data.get('domicilio_tarifa') or 0)
    domicilio_modo_fuera = (data.get('domicilio_modo_fuera') or 'por_confirmar').strip()
    if domicilio_modo_fuera not in ('por_confirmar', 'rechazar'):
        domicilio_modo_fuera = 'por_confirmar'
    domicilio_zona = data.get('domicilio_zona') or []
    conn = get_db_connection()
    try:
        init_config_negocio(conn)
        conn.execute("""
            INSERT INTO config_negocio (
                tercero_id, modalidades, metodos_pago, aviso_pedido,
                domicilio_tarifa, domicilio_modo_fuera, domicilio_zona, updated_at
            )
            VALUES (%s, %s::jsonb, %s::jsonb, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (tercero_id) DO UPDATE SET
                modalidades  = EXCLUDED.modalidades,
                metodos_pago = EXCLUDED.metodos_pago,
                aviso_pedido = EXCLUDED.aviso_pedido,
                domicilio_tarifa = EXCLUDED.domicilio_tarifa,
                domicilio_modo_fuera = EXCLUDED.domicilio_modo_fuera,
                domicilio_zona = EXCLUDED.domicilio_zona,
                updated_at   = NOW()
        """, (
            tercero_id, json.dumps(modalidades), json.dumps(metodos_pago), aviso_pedido,
            domicilio_tarifa, domicilio_modo_fuera, json.dumps(domicilio_zona)
        ))
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
        init_config_negocio(conn)
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
            'domicilio_tarifa': config.get('domicilio_tarifa', 0),
            'domicilio_modo_fuera': config.get('domicilio_modo_fuera', 'por_confirmar'),
            'domicilio_zona': config.get('domicilio_zona', []),
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
            _asegurar_domicilio_restaurante(conn)
            row = conn.execute("""
                SELECT r.tercero_id, r.nombre, r.slug, COALESCE(p.precio, 0) + COALESCE(p.valor_domicilio, 0) AS total
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
            _asegurar_domicilio_restaurante(conn)
            total_row = conn.execute("""
                SELECT COALESCE(precio, 0) * COALESCE(cantidad, 1) + COALESCE(valor_domicilio, 0) AS total
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
        try:
            _notificar_pago_pedido(conn, tipo, pedido_id, pagos, metodo_pago)
        except Exception as exc:
            print(f'[telegram pago] no se pudo notificar pedido {pedido_id}: {exc}')
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
