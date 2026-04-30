import re
import uuid
import unicodedata
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template_string, request, session

from ..db import get_db_connection

bp = Blueprint('vendedor', __name__)


def _slug(nombre):
    n = unicodedata.normalize('NFD', nombre)
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    n = n.lower().strip()
    n = re.sub(r'[^a-z0-9\s-]', '', n)
    n = re.sub(r'[\s-]+', '-', n).strip('-')
    return n[:60] or 'negocio'


def _tercero_id_por_tel(tel):
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (tel,)).fetchone()
        conn.close()
        return row['id'] if row else None
    except Exception:
        return None


def _asegurar_tablas(conn):
    for sql in [
        """CREATE TABLE IF NOT EXISTS citas_vendedor (
            id SERIAL PRIMARY KEY, vendedor_cod VARCHAR(50), tipo_negocio VARCHAR(20),
            subtipo VARCHAR(20) DEFAULT 'menu_dia', negocio_slug VARCHAR(100),
            nombre_negocio VARCHAR(200), nombre_dueno VARCHAR(200), telefono VARCHAR(20),
            fecha_hora TIMESTAMP, estado VARCHAR(20) DEFAULT 'pendiente',
            notas TEXT, negocio_id INTEGER, created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS plantillas_crm (
            id SERIAL PRIMARY KEY, tercero_id INTEGER NOT NULL,
            titulo VARCHAR(80) NOT NULL, cuerpo TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS plantillas_crm_envios (
            id SERIAL PRIMARY KEY, plantilla_id INTEGER, contacto_id INTEGER NOT NULL,
            vendedor_id INTEGER NOT NULL, medio VARCHAR(20) DEFAULT 'whatsapp',
            mensaje_enviado TEXT, negocio_id INTEGER, created_at TIMESTAMP DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS vendedor_negocios (
            id SERIAL PRIMARY KEY, vendedor_id INTEGER NOT NULL, negocio_id INTEGER NOT NULL,
            activo BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(vendedor_id, negocio_id))""",
        """CREATE TABLE IF NOT EXISTS contactos (
            id SERIAL PRIMARY KEY, negocio_id INTEGER, tercero_id INTEGER,
            nombre VARCHAR(200), telefono VARCHAR(20), chat_token TEXT,
            created_at TIMESTAMP DEFAULT NOW())""",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass
    for sql in [
        "ALTER TABLE plantillas_crm_envios ALTER COLUMN plantilla_id DROP NOT NULL",
        "ALTER TABLE plantillas_crm_envios ADD COLUMN IF NOT EXISTS medio VARCHAR(20) DEFAULT 'whatsapp'",
        "ALTER TABLE plantillas_crm_envios ADD COLUMN IF NOT EXISTS mensaje_enviado TEXT",
        "ALTER TABLE plantillas_crm_envios ADD COLUMN IF NOT EXISTS negocio_id INTEGER",
        "ALTER TABLE citas_vendedor ADD COLUMN IF NOT EXISTS negocio_id INTEGER",
        "ALTER TABLE contactos ADD COLUMN IF NOT EXISTS chat_token TEXT",
        "ALTER TABLE contactos ADD COLUMN IF NOT EXISTS tercero_id INTEGER",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()


# ── API ───────────────────────────────────────────────────────────────────────

@bp.route('/api/vendedor/identificar', methods=['POST'])
def api_vendedor_identificar():
    data     = request.get_json()
    nombre   = data.get('nombre', '').strip()
    telefono = ''.join(filter(str.isdigit, data.get('telefono', '')))
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 dígitos'}), 400
    try:
        conn = get_db_connection()
        t = conn.execute("SELECT id, nombre FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)).fetchone()
        if t:
            conn.execute("UPDATE terceros SET nombre=%s WHERE id=%s", (nombre, t['id']))
            conn.commit()
            tid, nom = t['id'], t['nombre']
        else:
            cur = conn.execute("INSERT INTO terceros (nombre, telefono) VALUES (%s, %s) RETURNING id", (nombre, telefono))
            tid = cur.fetchone()[0]
            nom = nombre
            conn.commit()
        conn.close()
        return jsonify({'ok': True, 'tercero_id': tid, 'nombre': nom, 'telefono': telefono})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/citas', methods=['GET'])
def api_vendedor_citas_get():
    cod = request.args.get('cod', '').strip()
    if not cod:
        return jsonify({'ok': False, 'error': 'cod requerido'}), 400
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute("""
            SELECT id, tipo_negocio, subtipo, negocio_slug, nombre_negocio,
                   nombre_dueno, telefono, fecha_hora, estado, notas
            FROM citas_vendedor
            WHERE vendedor_cod = %s AND fecha_hora >= NOW() - INTERVAL '2 hours'
            ORDER BY fecha_hora ASC LIMIT 30
        """, (cod,)).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            if d['fecha_hora']:
                d['fecha_hora'] = d['fecha_hora'].strftime('%Y-%m-%dT%H:%M')
            result.append(d)
        return jsonify({'ok': True, 'citas': result})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/cita', methods=['POST'])
def api_vendedor_cita_post():
    data           = request.get_json()
    vendedor_cod   = data.get('vendedor_cod', '').strip()
    tipo           = data.get('tipo', '').strip()
    subtipo        = data.get('subtipo', 'menu_dia').strip()
    nombre_neg     = data.get('nombre_negocio', '').strip()
    nombre_due     = data.get('nombre_dueno', '').strip()
    telefono       = ''.join(filter(str.isdigit, data.get('telefono', '')))
    fecha_hora_str = data.get('fecha_hora', '').strip()
    negocio_id_crm = data.get('negocio_id')

    if not vendedor_cod:
        return jsonify({'ok': False, 'error': 'Código de vendedor requerido'}), 400
    if tipo not in ('restaurante', 'tienda', 'taller'):
        return jsonify({'ok': False, 'error': 'Tipo de negocio inválido'}), 400
    if not nombre_neg or not nombre_due:
        return jsonify({'ok': False, 'error': 'Nombre del negocio y del dueño requeridos'}), 400
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 dígitos'}), 400
    if not fecha_hora_str:
        return jsonify({'ok': False, 'error': 'Fecha y hora requeridas'}), 400
    try:
        fecha_hora = datetime.fromisoformat(fecha_hora_str)
    except Exception:
        return jsonify({'ok': False, 'error': 'Formato de fecha inválido'}), 400

    negocio_slug = _slug(nombre_neg)
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)

        franja_ini = fecha_hora - timedelta(minutes=90)
        franja_fin = fecha_hora + timedelta(minutes=90)
        choque = conn.execute("""
            SELECT nombre_negocio, fecha_hora FROM citas_vendedor
            WHERE vendedor_cod = %s AND estado NOT IN ('descartada','cerrada')
              AND fecha_hora BETWEEN %s AND %s
        """, (vendedor_cod, franja_ini, franja_fin)).fetchone()
        if choque:
            hora_ocup = choque['fecha_hora'].strftime('%H:%M')
            conn.close()
            return jsonify({'ok': False, 'error': f'Horario ocupado: tienes cita con {choque["nombre_negocio"]} a las {hora_ocup}. Deja al menos 1h 30min.'}), 400

        token_acceso = uuid.uuid4().hex
        # Tercero del dueño (persona)
        t = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)).fetchone()
        if t:
            admin_id = t['id']
            conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (nombre_due, admin_id))
        else:
            admin_id = conn.execute(
                "INSERT INTO terceros (nombre, telefono, tipo_tercero) VALUES (%s, %s, 'persona') RETURNING id",
                (nombre_due, telefono)
            ).fetchone()[0]
        conn.commit()

        if tipo == 'restaurante':
            existente = conn.execute("SELECT slug FROM restaurantes WHERE slug = %s", (negocio_slug,)).fetchone()
            if existente:
                negocio_slug = negocio_slug + '-' + uuid.uuid4().hex[:4]
            negocio_tercero_id = conn.execute(
                "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'negocio') RETURNING id", (nombre_neg,)
            ).fetchone()[0]
            conn.execute("""
                INSERT INTO restaurantes (nombre, slug, tipo_restaurante, admin_id, admin_nombre,
                    admin_telefono, token_acceso, dias_pagados, activo, tercero_id, ref_vendedor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, TRUE, %s, %s)
            """, (nombre_neg, negocio_slug, subtipo, admin_id, nombre_due, telefono, token_acceso, negocio_tercero_id, vendedor_cod))
        elif tipo == 'tienda':
            from datetime import date
            existente = conn.execute("SELECT slug FROM tiendas WHERE slug = %s", (negocio_slug,)).fetchone()
            if existente:
                negocio_slug = negocio_slug + '-' + uuid.uuid4().hex[:4]
            negocio_tercero_id = conn.execute(
                "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'negocio') RETURNING id", (nombre_neg,)
            ).fetchone()[0]
            conn.execute("""
                INSERT INTO tiendas (nombre, slug, admin_id, admin_nombre, admin_telefono,
                    token_acceso, dias_pagados, fecha_vence, activo, tercero_id, ref_vendedor)
                VALUES (%s, %s, %s, %s, %s, %s, 0, %s, TRUE, %s, %s)
            """, (nombre_neg, negocio_slug, admin_id, nombre_due, telefono, token_acceso, date.today(), negocio_tercero_id, vendedor_cod))
        conn.commit()

        conn.execute("""
            INSERT INTO citas_vendedor (vendedor_cod, tipo_negocio, subtipo, negocio_slug,
                nombre_negocio, nombre_dueno, telefono, fecha_hora, negocio_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (vendedor_cod, tipo, subtipo, negocio_slug, nombre_neg, nombre_due, telefono, fecha_hora, negocio_id_crm))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'slug': negocio_slug, 'tipo': tipo})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/cita/<int:cita_id>/estado', methods=['POST'])
def api_vendedor_cita_estado(cita_id):
    data   = request.get_json()
    estado = data.get('estado', '').strip()
    notas  = data.get('notas', '').strip()
    if estado not in ('pendiente', 'hecha', 'cerrada', 'descartada'):
        return jsonify({'ok': False, 'error': 'Estado inválido'}), 400
    try:
        conn = get_db_connection()
        conn.execute("UPDATE citas_vendedor SET estado=%s, notas=%s WHERE id=%s", (estado, notas or None, cita_id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/buscar-tercero')
def api_vendedor_buscar_tercero():
    tel = request.args.get('tel', '').strip().replace(' ', '')
    if not tel:
        return jsonify({'ok': False, 'encontrado': False})
    try:
        conn = get_db_connection()
        t = conn.execute(
            "SELECT id, nombre, telefono FROM terceros WHERE REGEXP_REPLACE(telefono,'[^0-9]','','g') ILIKE %s LIMIT 1",
            ('%' + tel[-7:] + '%',)
        ).fetchone()
        conn.close()
        if t:
            return jsonify({'ok': True, 'encontrado': True, 'id': t['id'], 'nombre': t['nombre'] or '', 'telefono': t['telefono'] or ''})
        return jsonify({'ok': True, 'encontrado': False})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'encontrado': False, 'error': str(e)})


@bp.route('/api/vendedor/buscar-terceros')
def api_vendedor_buscar_terceros():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT id, nombre, telefono FROM terceros WHERE nombre ILIKE %s ORDER BY nombre LIMIT 8",
            ('%' + q + '%',)
        ).fetchall()
        conn.close()
        return jsonify([{'id': r['id'], 'nombre': r['nombre'] or '', 'telefono': r['telefono'] or ''} for r in rows])
    except Exception:
        try: conn.close()
        except: pass
        return jsonify([])


@bp.route('/api/vendedor/buscar-negocios')
def api_vendedor_buscar_negocios():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    resultados = []
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute("SELECT id, nombre, 'restaurante' as tipo FROM restaurantes WHERE nombre ILIKE %s ORDER BY nombre LIMIT 5", ('%' + q + '%',)).fetchall()
            resultados.extend([{'id': r['id'], 'nombre': r['nombre'], 'tipo': r['tipo']} for r in rows])
        except Exception:
            pass
        try:
            rows = conn.execute("SELECT id, nombre, 'tienda' as tipo FROM tiendas WHERE nombre ILIKE %s ORDER BY nombre LIMIT 5", ('%' + q + '%',)).fetchall()
            resultados.extend([{'id': r['id'], 'nombre': r['nombre'], 'tipo': r['tipo']} for r in rows])
        except Exception:
            pass
        conn.close()
    except Exception:
        pass
    return jsonify(resultados[:10])


@bp.route('/api/vendedor/contactos')
def api_vendedor_contactos_lista():
    tel = request.args.get('tel', '').strip()
    if not tel:
        return jsonify({'ok': False, 'error': 'tel requerido'}), 400
    tid = _tercero_id_por_tel(tel)
    if not tid:
        return jsonify({'ok': True, 'contactos': []})
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute("""
            SELECT c.id, c.nombre, c.telefono, c.created_at::text,
                   COALESCE(c.chat_token,
                       (SELECT conv.token FROM conversaciones conv
                        JOIN terceros t2 ON t2.id = conv.invitado_id
                        WHERE conv.activa = TRUE AND c.telefono IS NOT NULL
                          AND REGEXP_REPLACE(COALESCE(t2.telefono,''),'[^0-9]','','g')
                              = REGEXP_REPLACE(c.telefono,'[^0-9]','','g')
                        LIMIT 1)
                   ) AS chat_token
            FROM contactos c WHERE c.tercero_id = %s ORDER BY c.nombre NULLS LAST
        """, (tid,)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'contactos': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/contactos/importar', methods=['POST'])
def api_vendedor_contactos_importar():
    data = request.get_json()
    tel_vendedor = (data.get('tel') or '').strip()
    lista = data.get('contactos', [])
    if not tel_vendedor or not lista:
        return jsonify({'ok': False, 'error': 'tel y contactos requeridos'}), 400
    tid = _tercero_id_por_tel(tel_vendedor)
    if not tid:
        return jsonify({'ok': False, 'error': 'Vendedor no encontrado — registrate primero'}), 404
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        insertados = omitidos = 0
        for c in lista:
            nombre = (c.get('nombre') or '').strip()
            telefono = (c.get('telefono') or '').strip()
            if telefono.startswith('00'):
                telefono = '+' + telefono[2:]
            if not (nombre or telefono):
                continue
            if telefono:
                existe = conn.execute("SELECT 1 FROM contactos WHERE tercero_id = %s AND telefono = %s", (tid, telefono)).fetchone()
                if existe:
                    omitidos += 1
                    continue
            conn.execute("INSERT INTO contactos (negocio_id, nombre, telefono, tercero_id) VALUES (%s, %s, %s, %s)", (tid, nombre or None, telefono or None, tid))
            insertados += 1
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'insertados': insertados, 'omitidos': omitidos})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/contactos/reclamar', methods=['POST'])
def api_vendedor_contactos_reclamar():
    data = request.get_json() or {}
    tel  = (data.get('tel') or '').strip()
    if not tel:
        return jsonify({'ok': False, 'error': 'tel requerido'}), 400
    tid = _tercero_id_por_tel(tel)
    if not tid:
        return jsonify({'ok': False, 'error': 'Vendedor no encontrado'}), 404
    try:
        conn = get_db_connection()
        result = conn.execute("UPDATE contactos SET tercero_id = %s WHERE tercero_id IS NULL", (tid,))
        actualizados = result.rowcount
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'actualizados': actualizados})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/contactos/<int:cid>', methods=['DELETE'])
def api_vendedor_contactos_eliminar(cid):
    tel = request.args.get('tel', '').strip()
    tid = _tercero_id_por_tel(tel) if tel else None
    try:
        conn = get_db_connection()
        if tid:
            conn.execute("DELETE FROM contactos WHERE id = %s AND tercero_id = %s", (cid, tid))
        else:
            conn.execute("DELETE FROM contactos WHERE id = %s", (cid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/contactos/<int:cid>/chat', methods=['POST'])
def api_vendedor_contacto_chat(cid):
    data = request.get_json() or {}
    tel_vendedor = (data.get('tel') or '').strip()
    if not tel_vendedor:
        return jsonify({'ok': False, 'error': 'tel requerido'}), 400
    vendedor_tid = _tercero_id_por_tel(tel_vendedor)
    if not vendedor_tid:
        return jsonify({'ok': False, 'error': 'Vendedor no encontrado'}), 404
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        contacto = conn.execute(
            "SELECT id, nombre, telefono, chat_token FROM contactos WHERE id = %s AND tercero_id = %s",
            (cid, vendedor_tid)
        ).fetchone()
        if not contacto:
            conn.close()
            return jsonify({'ok': False, 'error': 'Contacto no encontrado'}), 404

        if contacto['chat_token']:
            conv = conn.execute("SELECT token, activa FROM conversaciones WHERE token = %s", (contacto['chat_token'],)).fetchone()
            if conv and conv['activa']:
                conn.close()
                host = request.host_url.rstrip('/')
                return jsonify({'ok': True, 'token': conv['token'], 'link': f"{host}/chat/{conv['token']}", 'nuevo': False})

        invitado_id = None
        if contacto['telefono']:
            tel_limpio = ''.join(filter(str.isdigit, contacto['telefono']))
            t = conn.execute(
                "SELECT id FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono,''),'[^0-9]','','g') = %s LIMIT 1",
                (tel_limpio,)
            ).fetchone()
            if t:
                invitado_id = t['id']

        if not invitado_id:
            token_chat = secrets.token_urlsafe(12)
            inv = conn.execute(
                "INSERT INTO terceros (nombre, token_chat, tipo_tercero, telefono) VALUES (%s, %s, 'invitado', %s) RETURNING id",
                (contacto['nombre'] or 'Invitado', token_chat, contacto['telefono'])
            ).fetchone()
            invitado_id = inv['id']

        token_conv = secrets.token_urlsafe(12)
        conn.execute(
            "INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, origen) VALUES (%s, %s, %s, %s, 'vendedor') RETURNING id",
            (vendedor_tid, invitado_id, token_conv, contacto['nombre'] or 'Invitado')
        )
        conn.execute("UPDATE contactos SET chat_token = %s WHERE id = %s", (token_conv, cid))
        conn.commit()
        conn.close()
        host = request.host_url.rstrip('/')
        return jsonify({'ok': True, 'token': token_conv, 'link': f"{host}/chat/{token_conv}", 'nuevo': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/plantillas')
def api_vendedor_plantillas_lista():
    tel = request.args.get('tel', '').strip()
    tid = _tercero_id_por_tel(tel) if tel else None
    if not tid:
        return jsonify({'ok': True, 'plantillas': []})
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute("SELECT id, titulo, cuerpo FROM plantillas_crm ORDER BY id").fetchall()
        conn.close()
        return jsonify({'ok': True, 'plantillas': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/plantillas', methods=['POST'])
def api_vendedor_plantillas_crear():
    data   = request.get_json() or {}
    tel    = (data.get('tel') or '').strip()
    titulo = (data.get('titulo') or '').strip()[:80]
    cuerpo = (data.get('cuerpo') or '').strip()
    if not titulo or not cuerpo:
        return jsonify({'ok': False, 'error': 'titulo y cuerpo requeridos'}), 400
    tid = _tercero_id_por_tel(tel) if tel else None
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        existe = conn.execute("SELECT id FROM plantillas_crm WHERE LOWER(TRIM(cuerpo)) = LOWER(TRIM(%s)) LIMIT 1", (cuerpo,)).fetchone()
        if existe:
            conn.close()
            return jsonify({'ok': True, 'id': existe['id'], 'titulo': titulo, 'cuerpo': cuerpo, 'duplicado': True})
        nueva = conn.execute("INSERT INTO plantillas_crm (tercero_id, titulo, cuerpo) VALUES (%s,%s,%s) RETURNING id", (tid, titulo, cuerpo)).fetchone()
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'id': nueva[0], 'titulo': titulo, 'cuerpo': cuerpo})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/plantillas/<int:pid>', methods=['DELETE'])
def api_vendedor_plantillas_eliminar(pid):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM plantillas_crm WHERE id = %s", (pid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/plantillas/<int:pid>', methods=['PUT'])
def api_vendedor_plantillas_editar(pid):
    data   = request.get_json() or {}
    titulo = (data.get('titulo') or '').strip()[:80]
    cuerpo = (data.get('cuerpo') or '').strip()
    if not titulo or not cuerpo:
        return jsonify({'ok': False, 'error': 'titulo y cuerpo requeridos'}), 400
    try:
        conn = get_db_connection()
        conn.execute("UPDATE plantillas_crm SET titulo=%s, cuerpo=%s WHERE id=%s", (titulo, cuerpo, pid))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/plantillas/envio', methods=['POST'])
def api_vendedor_plantillas_envio():
    data            = request.get_json() or {}
    plantilla_id    = data.get('plantilla_id')
    contacto_id     = data.get('contacto_id')
    tel_vendedor    = (data.get('tel_vendedor') or '').strip()
    medio           = (data.get('medio') or 'whatsapp').strip()
    mensaje_enviado = (data.get('mensaje_enviado') or '').strip() or None
    negocio_id      = data.get('negocio_id')
    if not contacto_id:
        return jsonify({'ok': False, 'error': 'contacto_id requerido'}), 400
    vendedor_id = _tercero_id_por_tel(tel_vendedor) if tel_vendedor else None
    if not vendedor_id:
        return jsonify({'ok': False, 'error': 'vendedor no identificado'}), 400
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        conn.execute(
            "INSERT INTO plantillas_crm_envios (plantilla_id, contacto_id, vendedor_id, medio, mensaje_enviado, negocio_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (plantilla_id, contacto_id, vendedor_id, medio, mensaje_enviado, negocio_id)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/envios')
def api_vendedor_envios_general():
    tel        = request.args.get('tel', '').strip()
    negocio_id = request.args.get('negocio_id', type=int)
    vendedor_id = _tercero_id_por_tel(tel) if tel else None
    if not vendedor_id:
        return jsonify({'ok': True, 'envios': []})
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        filtro = "WHERE e.vendedor_id = %s AND (e.negocio_id = %s OR e.negocio_id IS NULL)" if negocio_id else "WHERE e.vendedor_id = %s"
        params = (vendedor_id, negocio_id) if negocio_id else (vendedor_id,)
        rows = conn.execute(f"""
            SELECT e.id, e.medio, e.created_at::text, e.contacto_id,
                   c.nombre AS contacto_nombre, c.telefono AS contacto_tel,
                   p.titulo AS plantilla_titulo,
                   COALESCE(e.mensaje_enviado, p.cuerpo) AS texto_enviado
            FROM plantillas_crm_envios e
            JOIN contactos c ON c.id = e.contacto_id
            LEFT JOIN plantillas_crm p ON p.id = e.plantilla_id
            {filtro} ORDER BY e.created_at DESC LIMIT 100
        """, params).fetchall()
        conn.close()
        return jsonify({'ok': True, 'envios': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/envios/<int:envio_id>', methods=['DELETE'])
def api_vendedor_envio_eliminar(envio_id):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM plantillas_crm_envios WHERE id = %s", (envio_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/envios/contacto/<int:cid>')
def api_vendedor_envios_contacto(cid):
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute("""
            SELECT e.medio, e.created_at::text, tv.nombre AS vendedor_nombre,
                   p.titulo AS plantilla_titulo, p.cuerpo AS plantilla_cuerpo
            FROM plantillas_crm_envios e
            JOIN terceros tv ON tv.id = e.vendedor_id
            LEFT JOIN plantillas_crm p ON p.id = e.plantilla_id
            WHERE e.contacto_id = %s ORDER BY e.created_at DESC
        """, (cid,)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'envios': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/vendedor/mis-negocios')
def api_vendedor_mis_negocios():
    tel = request.args.get('tel', '').strip()
    vendedor_id = _tercero_id_por_tel(tel) if tel else None
    if not vendedor_id:
        return jsonify({'ok': False, 'error': 'vendedor no identificado'}), 400
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute("""
            SELECT vn.negocio_id AS id, t.nombre, 'tercero' AS tipo
            FROM vendedor_negocios vn JOIN terceros t ON t.id = vn.negocio_id
            WHERE vn.vendedor_id = %s AND vn.activo = TRUE ORDER BY vn.created_at ASC
        """, (vendedor_id,)).fetchall()
        negocios = [dict(r) for r in rows]
        try:
            tienda_rows = conn.execute("""
                SELECT tv.tienda_id, ti.nombre, ti.tercero_id, ti.admin_id
                FROM tienda_vendedores tv JOIN tiendas ti ON ti.id = tv.tienda_id
                WHERE tv.vendedor_id = %s AND tv.activo = TRUE ORDER BY tv.created_at ASC
            """, (vendedor_id,)).fetchall()
            for row in tienda_rows:
                d = dict(row)
                tid = d['tercero_id']
                if not tid or tid == d['admin_id']:
                    existing = conn.execute("SELECT id FROM terceros WHERE nombre = %s AND telefono IS NULL LIMIT 1", (d['nombre'],)).fetchone()
                    if existing:
                        tid = existing['id']
                    else:
                        new_t = conn.execute("INSERT INTO terceros (nombre) VALUES (%s) RETURNING id", (d['nombre'],)).fetchone()
                        tid = new_t['id']
                    conn.execute("UPDATE tiendas SET tercero_id = %s WHERE id = %s", (tid, d['tienda_id']))
                negocios.append({'id': tid, 'nombre': d['nombre'], 'tipo': 'tienda'})
            conn.commit()
        except Exception:
            pass
        conn.close()
        vistos = set()
        unicos = []
        for n in negocios:
            if n['id'] not in vistos:
                vistos.add(n['id'])
                unicos.append(n)
        return jsonify({'ok': True, 'negocios': unicos})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Dashboard ─────────────────────────────────────────────────────────────────

@bp.route('/vendedor')
def vendedor_dashboard():
    uid = session.get('usuario_id')
    vendedor_pre = {'nombre': '', 'telefono': ''}
    if uid:
        try:
            conn = get_db_connection()
            t = conn.execute("SELECT nombre, telefono FROM terceros WHERE id=%s", (uid,)).fetchone()
            if t:
                vendedor_pre = {'nombre': t['nombre'] or '', 'telefono': t['telefono'] or ''}
            else:
                nombre_sesion = session.get('nombre', '')
                if nombre_sesion:
                    t2 = conn.execute(
                        "SELECT nombre, telefono FROM terceros WHERE nombre ILIKE %s AND telefono IS NOT NULL LIMIT 1",
                        (nombre_sesion,)
                    ).fetchone()
                    vendedor_pre = {'nombre': t2['nombre'] or '' if t2 else nombre_sesion, 'telefono': t2['telefono'] or '' if t2 else ''}
            conn.close()
        except Exception:
            pass
    return render_template_string(_HTML,
        vd_nombre=vendedor_pre['nombre'],
        vd_telefono=vendedor_pre['telefono'])


_HTML = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vendedor TUC TUC</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">

<div class="bg-indigo-700 text-white px-4 py-4">
  <div class="max-w-2xl mx-auto flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="text-2xl">🚗</div>
      <div>
        <h1 class="text-lg font-extrabold tracking-tight">TUC TUC — Vendedor</h1>
        <p class="text-indigo-200 text-xs" id="txt-vendedor-nombre">Cargando...</p>
      </div>
    </div>
    <button onclick="cambiarCodigo()" class="text-indigo-200 text-xs underline">Cerrar sesión</button>
  </div>
  <div class="max-w-2xl mx-auto mt-3" id="bloque-negocio" style="display:none">
    <div class="bg-indigo-800 rounded-xl px-3 py-2 flex items-center gap-2">
      <span class="text-indigo-300 text-xs font-bold uppercase tracking-wide">Vendiendo para:</span>
      <div class="relative flex-1">
        <select id="sel-negocio" onchange="cambiarNegocioActivo()"
                style="background:#312e81;color:white;height:28px"
                class="w-full text-sm font-bold cursor-pointer focus:outline-none pr-4 rounded"></select>
        <span class="pointer-events-none absolute right-0 top-0 text-indigo-300 text-xs">▾</span>
      </div>
    </div>
  </div>
</div>

<div class="max-w-2xl mx-auto px-4 py-4 space-y-4">

  <div>
    <div class="flex items-center justify-between mb-2 px-1">
      <p class="text-xs font-bold text-gray-500 uppercase tracking-wide">Mis citas</p>
      <button onclick="abrirModalCita()" class="bg-indigo-600 text-white text-xs font-bold px-3 py-1.5 rounded-full shadow hover:bg-indigo-700 transition active:scale-95">+ Nueva cita</button>
    </div>
    <div id="lista-citas" class="space-y-2">
      <p class="text-xs text-gray-400 text-center py-4" id="txt-citas-vacio">Cargando agenda...</p>
    </div>
  </div>

  <div id="sec-demo" class="hidden">
    <div class="bg-indigo-50 border border-indigo-200 rounded-2xl px-4 py-3 mb-2 flex items-center justify-between">
      <div>
        <p class="text-xs text-indigo-500 font-bold uppercase">Demo en curso</p>
        <p class="font-bold text-indigo-800 text-sm" id="txt-demo-nombre">—</p>
      </div>
      <button onclick="verNegocio()" class="text-xs text-indigo-600 underline">Ver página →</button>
    </div>
    <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2 px-1">¿Cuál es la situación del negocio?</p>
    <div class="space-y-2">
      <div class="bg-white rounded-2xl shadow border border-transparent transition-all" id="sit-1">
        <button class="w-full text-left p-4 flex items-center gap-3" onclick="abrirSituacion(1)">
          <span class="text-2xl">🧍</span>
          <div class="flex-1">
            <p class="font-bold text-gray-800 text-sm">El mesero viaja a cocina</p>
            <p class="text-xs text-gray-400">El pedido llega solo — el mesero no tiene que ir a entregarlo</p>
          </div>
          <span class="text-gray-300 text-lg" id="arr-1">›</span>
        </button>
        <div id="panel-1" class="hidden px-4 pb-4 border-t border-gray-100">
          <div class="pt-3 pb-2 space-y-2">
            <div class="flex gap-2 items-start"><span class="bg-indigo-100 text-indigo-700 font-bold text-xs rounded-full w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">1</span><p class="text-xs text-gray-600"><strong>No abras el celular.</strong> Pregunta: <em>"¿Cuántas veces al día va un mesero a cocina solo a dejar la comanda?"</em></p></div>
            <div class="flex gap-2 items-start"><span class="bg-indigo-100 text-indigo-700 font-bold text-xs rounded-full w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">2</span><p class="text-xs text-gray-600">Pregunta: <em>"¿Quiere jugar de mesero o de cocinero?"</em></p></div>
            <div class="flex gap-2 items-start"><span class="bg-indigo-100 text-indigo-700 font-bold text-xs rounded-full w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">3</span><p class="text-xs text-gray-600">Tocá el botón del rol → WhatsApp se abre con el link listo → el cliente lo abre en su celular.</p></div>
            <div class="flex gap-2 items-start"><span class="bg-indigo-100 text-indigo-700 font-bold text-xs rounded-full w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">4</span><p class="text-xs text-gray-600">Vos tomás el rol contrario. Hacés un pedido. <strong>El cliente lo ve llegar en su celular.</strong></p></div>
          </div>
          <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mt-3 mb-2">¿Quiere jugar de...?</p>
          <div class="grid grid-cols-2 gap-3">
            <button onclick="enviarRol('mesero')" class="bg-blue-50 border-2 border-blue-200 hover:border-blue-500 rounded-xl p-3 text-center transition active:scale-95"><div class="text-2xl mb-1">🙋</div><p class="font-bold text-blue-800 text-sm">Mesero</p><p class="text-xs text-blue-500">Toma la orden</p></button>
            <button onclick="enviarRol('cocina')" class="bg-orange-50 border-2 border-orange-200 hover:border-orange-500 rounded-xl p-3 text-center transition active:scale-95"><div class="text-2xl mb-1">👨‍🍳</div><p class="font-bold text-orange-800 text-sm">Cocinero</p><p class="text-xs text-orange-500">Ve llegar el pedido</p></button>
          </div>
          <p class="text-xs text-center text-gray-400 mt-2" id="txt-rol-aviso">El link se envía por WhatsApp al celular del cliente</p>
        </div>
      </div>
      <div class="bg-white rounded-2xl shadow border border-transparent" id="sit-2">
        <button class="w-full text-left p-4 flex items-center gap-3" onclick="abrirSituacion(2)">
          <span class="text-2xl">📱</span>
          <div class="flex-1">
            <p class="font-bold text-gray-800 text-sm">Me preguntan por WhatsApp todo el día</p>
            <p class="text-xs text-gray-400">El cliente ve el menú y pide solo — sin mensajes manuales</p>
          </div>
          <span class="text-gray-300 text-lg" id="arr-2">›</span>
        </button>
        <div id="panel-2" class="hidden px-4 pb-4 border-t border-gray-100">
          <div class="pt-3 space-y-2">
            <div class="flex gap-2 items-start"><span class="bg-indigo-100 text-indigo-700 font-bold text-xs rounded-full w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">1</span><p class="text-xs text-gray-600">Pregunta: <em>"¿Cuántos mensajes de WhatsApp responde al día?"</em></p></div>
            <div class="flex gap-2 items-start"><span class="bg-indigo-100 text-indigo-700 font-bold text-xs rounded-full w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">2</span><p class="text-xs text-gray-600">Mostrá la página pública. El cliente navega la carta y hace su pedido. Sin un solo mensaje.</p></div>
          </div>
          <button onclick="verNegocio()" class="mt-3 w-full bg-indigo-600 text-white rounded-xl py-2.5 text-sm font-bold hover:bg-indigo-700 transition active:scale-95">Abrir página del restaurante →</button>
        </div>
      </div>
    </div>
  </div>

  <div>
    <button onclick="toggleHistorialGeneral()" class="w-full flex items-center justify-between px-1 mb-2">
      <p class="text-xs font-bold text-gray-500 uppercase tracking-wide">Mis envíos recientes</p>
      <span id="ico-historial-toggle" class="text-gray-400 text-sm">▼</span>
    </button>
    <div id="sec-historial-general" class="hidden space-y-1 mb-4">
      <div id="lista-historial-general" class="text-xs text-gray-400 text-center py-2">Cargando...</div>
    </div>
  </div>

  <div>
    <div class="flex items-center justify-between px-1 mb-0">
      <button onclick="toggleContactos()" class="flex items-center gap-2 flex-1 py-2 text-left">
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wide">Mis contactos</p>
        <span id="ico-contactos-toggle" class="text-gray-400 text-sm ml-2">▼</span>
      </button>
      <div class="flex gap-2">
        <button onclick="abrirImportarContactos()" class="bg-gray-100 text-gray-700 text-xs font-bold px-3 py-1.5 rounded-full hover:bg-gray-200 transition">Importar</button>
        <button onclick="abrirAgregarContacto()" class="bg-indigo-600 text-white text-xs font-bold px-3 py-1.5 rounded-full shadow hover:bg-indigo-700 transition active:scale-95">+ Agregar</button>
      </div>
    </div>
    <div id="sec-contactos" class="hidden space-y-2">
      <div class="relative">
        <input id="inp-buscar-contacto" type="search" placeholder="Buscar en mis contactos..."
               oninput="filtrarContactos(this.value)"
               class="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400 bg-white">
      </div>
      <p class="text-xs text-gray-400 text-center py-4" id="txt-contactos-vacio">Cargando...</p>
      <div id="lista-contactos" class="space-y-2"></div>
      <div id="sec-reclamar" class="hidden text-center pt-1">
        <button onclick="reclamarContactos()" class="text-xs text-indigo-600 underline">¿Tenés contactos importados que no aparecen? Vincularlos a tu cuenta</button>
      </div>
    </div>
  </div>

  <details class="bg-white rounded-2xl shadow">
    <summary class="p-4 font-extrabold text-gray-800 text-sm cursor-pointer select-none">🛡️ Objeciones frecuentes</summary>
    <div class="px-4 pb-4 space-y-2 border-t border-gray-100 pt-3">
      <div class="bg-gray-50 rounded-xl p-3"><p class="text-xs text-gray-500 font-bold uppercase">Dice</p><p class="text-sm text-gray-800 font-semibold">"No tengo tiempo para aprender eso"</p><p class="text-xs text-indigo-600 font-bold uppercase mt-1">Respondés</p><p class="text-sm text-gray-600">"Son 2 minutos al día. Se lo muestro ahora mismo."</p></div>
      <div class="bg-gray-50 rounded-xl p-3"><p class="text-xs text-gray-500 font-bold uppercase">Dice</p><p class="text-sm text-gray-800 font-semibold">"Ya tengo Instagram"</p><p class="text-xs text-indigo-600 font-bold uppercase mt-1">Respondés</p><p class="text-sm text-gray-600">"Instagram no recibe pedidos. Aquí el cliente pide directo desde su celular."</p></div>
      <div class="bg-gray-50 rounded-xl p-3"><p class="text-xs text-gray-500 font-bold uppercase">Dice</p><p class="text-sm text-gray-800 font-semibold">"¿Cuánto vale?"</p><p class="text-xs text-indigo-600 font-bold uppercase mt-1">Respondés</p><p class="text-sm text-gray-600">"Primero que lo pruebe — si no funciona no paga nada. ¿Arrancamos?"</p></div>
      <div class="bg-gray-50 rounded-xl p-3"><p class="text-xs text-gray-500 font-bold uppercase">Dice</p><p class="text-sm text-gray-800 font-semibold">"Déjeme pensarlo"</p><p class="text-xs text-indigo-600 font-bold uppercase mt-1">Respondés</p><p class="text-sm text-gray-600">"Claro. ¿Lo dejamos activo gratis mientras lo piensa? No hay compromiso."</p></div>
    </div>
  </details>

  <details class="bg-amber-50 border border-amber-200 rounded-2xl">
    <summary class="p-4 font-extrabold text-amber-800 text-sm cursor-pointer select-none">✅ Antes de entrar al local</summary>
    <div class="px-4 pb-4 space-y-2 text-sm text-amber-900 border-t border-amber-100 pt-3">
      <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" class="rounded"> Cita agendada (no en hora de servicio)</label>
      <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" class="rounded"> Celular cargado y con datos</label>
      <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" class="rounded"> Negocio creado con nombre y al menos 1 producto real</label>
      <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" class="rounded"> Nombre del dueño confirmado</label>
    </div>
  </details>

</div>
<p class="text-center text-xs text-gray-400 py-4">TUC TUC · Kit del Vendedor · 2026</p>

<!-- MODAL NUEVA CITA -->
<div id="modal-cita" class="fixed inset-0 bg-black/50 z-50 hidden flex items-end justify-center">
  <div class="bg-white rounded-t-3xl w-full max-w-lg p-5 pb-8 space-y-4 max-h-[90vh] overflow-y-auto">
    <div class="flex items-center justify-between">
      <h2 class="font-extrabold text-gray-800 text-base">Nueva cita</h2>
      <button onclick="cerrarModalCita()" class="text-gray-400 text-2xl leading-none">&times;</button>
    </div>
    <div>
      <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Tipo de negocio</p>
      <div class="grid grid-cols-3 gap-2" id="sel-tipo">
        <button onclick="selTipo('restaurante','menu_dia')" data-t="restaurante-menu_dia" class="tipo-btn border-2 border-gray-200 rounded-xl p-3 text-center transition"><div class="text-xl mb-1">🍽️</div><p class="text-xs font-bold text-gray-700">Restaurante</p><p class="text-xs text-gray-400">Menú del día</p></button>
        <button onclick="selTipo('restaurante','carta')" data-t="restaurante-carta" class="tipo-btn border-2 border-gray-200 rounded-xl p-3 text-center transition"><div class="text-xl mb-1">📄</div><p class="text-xs font-bold text-gray-700">Restaurante</p><p class="text-xs text-gray-400">Carta</p></button>
        <button onclick="selTipo('tienda','')" data-t="tienda-" class="tipo-btn border-2 border-gray-200 rounded-xl p-3 text-center transition"><div class="text-xl mb-1">🛒</div><p class="text-xs font-bold text-gray-700">Tienda</p><p class="text-xs text-gray-400">Minimercado</p></button>
      </div>
    </div>
    <div class="space-y-3">
      <div class="relative">
        <label class="text-xs font-bold text-gray-500 uppercase tracking-wide block mb-1">Teléfono del dueño</label>
        <input id="cita-telefono" type="tel" placeholder="3001234567" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400">
        <div id="badge-tercero" class="hidden mt-1 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-2 py-1.5"></div>
      </div>
      <div class="relative">
        <label class="text-xs font-bold text-gray-500 uppercase tracking-wide block mb-1">Nombre del dueño</label>
        <input id="cita-nombre-due" type="text" placeholder="Don Carlos" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400">
      </div>
      <div class="relative">
        <label class="text-xs font-bold text-gray-500 uppercase tracking-wide block mb-1">Nombre del negocio</label>
        <input id="cita-nombre-neg" type="text" placeholder="Restaurante El Fogón" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400">
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div><label class="text-xs font-bold text-gray-500 uppercase tracking-wide block mb-1">Fecha</label><input id="cita-fecha" type="date" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400"></div>
        <div><label class="text-xs font-bold text-gray-500 uppercase tracking-wide block mb-1">Hora</label><input id="cita-hora" type="time" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400"></div>
      </div>
    </div>
    <p id="txt-cita-error" class="text-xs text-red-500 hidden"></p>
    <button onclick="guardarCita()" class="w-full bg-indigo-600 text-white rounded-xl py-3 font-bold text-sm hover:bg-indigo-700 transition active:scale-95">Agendar cita y crear negocio</button>
  </div>
</div>

<!-- MODAL IMPORTAR CONTACTOS -->
<div id="modal-importar-contactos" class="fixed inset-0 bg-black/60 z-50 hidden flex items-end justify-center">
  <div class="bg-white rounded-t-3xl w-full max-w-lg p-5 pb-8 space-y-4 max-h-[90vh] overflow-y-auto">
    <div class="flex items-center justify-between">
      <h2 class="font-extrabold text-gray-800 text-base">Importar contactos</h2>
      <button onclick="document.getElementById('modal-importar-contactos').classList.add('hidden')" class="text-gray-400 text-2xl leading-none">&times;</button>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <button onclick="importarVcf()" class="flex flex-col items-center gap-1 border-2 border-gray-200 rounded-2xl p-3 hover:border-indigo-400 transition"><span class="text-2xl">📇</span><span class="text-xs font-bold text-gray-700">Archivo VCF</span><span class="text-xs text-gray-400">Contactos del celular</span></button>
      <button onclick="importarTelegram()" class="flex flex-col items-center gap-1 border-2 border-gray-200 rounded-2xl p-3 hover:border-indigo-400 transition"><span class="text-2xl">✈️</span><span class="text-xs font-bold text-gray-700">Telegram</span><span class="text-xs text-gray-400">HTML o JSON export</span></button>
      <button id="btn-contact-picker" onclick="importarContactPicker()" class="flex flex-col items-center gap-1 border-2 border-gray-200 rounded-2xl p-3 hover:border-indigo-400 transition"><span class="text-2xl">📱</span><span class="text-xs font-bold text-gray-700">Seleccionar</span><span class="text-xs text-gray-400">Android Chrome</span></button>
      <button onclick="document.getElementById('modal-importar-contactos').classList.add('hidden'); abrirAgregarContacto()" class="flex flex-col items-center gap-1 border-2 border-gray-200 rounded-2xl p-3 hover:border-indigo-400 transition"><span class="text-2xl">✏️</span><span class="text-xs font-bold text-gray-700">Manual</span><span class="text-xs text-gray-400">Uno a la vez</span></button>
    </div>
    <input id="inp-vcf" type="file" accept=".vcf" class="hidden" onchange="procesarVcf(this)">
    <input id="inp-telegram" type="file" accept=".html,.json" class="hidden" onchange="procesarTelegram(this)">
    <div id="txt-importar-resultado" class="hidden text-xs text-center font-bold rounded-xl px-3 py-2"></div>
  </div>
</div>

<!-- MODAL AGREGAR CONTACTO -->
<div id="modal-agregar-contacto" class="fixed inset-0 bg-black/60 z-50 hidden flex items-end justify-center">
  <div class="bg-white rounded-t-3xl w-full max-w-lg p-5 pb-8 space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="font-extrabold text-gray-800 text-base">Agregar contacto</h2>
      <button onclick="document.getElementById('modal-agregar-contacto').classList.add('hidden')" class="text-gray-400 text-2xl leading-none">&times;</button>
    </div>
    <input id="inp-ac-nombre" type="text" placeholder="Nombre completo" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400">
    <input id="inp-ac-tel" type="tel" placeholder="Celular (ej: 3001234567)" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400">
    <div id="txt-ac-error" class="hidden text-xs text-red-500 font-bold"></div>
    <button onclick="guardarContacto()" class="w-full bg-indigo-600 text-white font-bold py-3 rounded-2xl hover:bg-indigo-700 transition">Guardar</button>
  </div>
</div>

<!-- MODAL CONTACTO -->
<div id="modal-wa-contacto" class="fixed inset-0 bg-black/60 z-50 hidden flex items-end justify-center px-2 pb-2">
  <div class="bg-white rounded-3xl w-full max-w-sm shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
    <div class="flex items-center justify-between px-5 pt-5 pb-3 shrink-0">
      <div><p class="font-extrabold text-gray-800 text-base" id="txt-wa-destinatario">—</p><p class="text-xs text-gray-400">Contacto</p></div>
      <button onclick="cerrarModalContacto()" class="text-gray-400 text-2xl leading-none">&times;</button>
    </div>
    <div class="px-5 pb-2 shrink-0"><p class="text-xs font-bold text-gray-400 uppercase tracking-wide mb-1">Mensajes anteriores</p></div>
    <div id="lista-historial-modal" class="px-5 overflow-y-auto space-y-1.5 shrink-1 min-h-[40px] max-h-40"><p class="text-xs text-gray-400 text-center py-2">Cargando...</p></div>
    <div class="px-5 pt-3 pb-2 shrink-0 border-t border-gray-100 mt-2">
      <p class="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2">Enviar por</p>
      <div class="flex gap-2">
        <button id="btn-canal-wa" onclick="seleccionarCanal('whatsapp')" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border-2 transition" style="border-color:#25D366;background:#25D366;color:white">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
          WhatsApp
        </button>
        <button id="btn-canal-tg" onclick="seleccionarCanal('telegram')" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border-2 transition" style="border-color:#2AABEE;color:#2AABEE;background:white">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
          Telegram
        </button>
      </div>
    </div>
    <div id="zona-envio-wa" class="px-5 pb-5 pt-2 space-y-2 shrink-0">
      <div id="plantillas-wa" class="flex flex-wrap gap-1.5 min-h-[28px]"><span class="text-xs text-gray-400 italic">Cargando...</span></div>
      <div id="form-nueva-plt" class="hidden space-y-2 bg-gray-50 border border-gray-200 rounded-xl p-3">
        <input id="inp-plt-titulo" type="text" placeholder="Nombre del mensaje (ej: Seguimiento)" class="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-indigo-400">
        <textarea id="inp-plt-cuerpo" rows="2" placeholder="Texto del mensaje..." class="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm resize-none focus:outline-none focus:border-indigo-400"></textarea>
        <div class="flex gap-2">
          <button id="btn-guardar-plt" onclick="guardarPlantilla()" class="flex-1 bg-indigo-600 text-white text-xs font-bold py-1.5 rounded-lg hover:bg-indigo-700 transition">Guardar</button>
          <button onclick="cancelarNuevaPlantilla()" class="text-xs text-gray-400 underline px-2">Cancelar</button>
        </div>
      </div>
      <textarea id="inp-wa-mensaje" rows="3" placeholder="Escribe el mensaje o elige uno arriba..." class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:border-green-400" onkeydown="if(event.ctrlKey&&event.key==='Enter') enviarPorCanal()"></textarea>
    </div>
    <div class="px-5 pb-5 shrink-0">
      <button onclick="enviarPorCanal()" id="btn-enviar-canal" class="w-full bg-green-600 text-white font-bold py-3 rounded-2xl hover:bg-green-700 transition active:scale-95">Abrir en WhatsApp →</button>
    </div>
  </div>
</div>

<!-- MODAL IDENTIFICACIÓN -->
<div id="modal-codigo" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
  <div class="bg-white rounded-3xl w-80 p-6 space-y-4 shadow-2xl">
    <h2 class="font-extrabold text-gray-800 text-base text-center">¿Quién eres?</h2>
    <p class="text-xs text-gray-500 text-center">Tu nombre y celular se guardan en este dispositivo.</p>
    <div class="space-y-3">
      <input id="inp-nombre-v" type="text" placeholder="Nombre completo" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400">
      <input id="inp-tel-v" type="tel" placeholder="Celular (ej: 3001234567)" class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-indigo-400" onkeydown="if(event.key==='Enter') confirmarIdentidad()">
    </div>
    <p id="txt-id-error" class="text-xs text-red-500 hidden text-center"></p>
    <button onclick="confirmarIdentidad()" class="w-full bg-indigo-600 text-white rounded-xl py-2.5 font-bold text-sm hover:bg-indigo-700 transition">Entrar</button>
    <button id="btn-cancelar-modal" onclick="cerrarModalCodigo()" class="hidden w-full text-gray-400 text-xs py-1 hover:text-gray-600 transition">Cancelar</button>
  </div>
</div>

<script>
let _slug = '', _tipo = 'restaurante', _subtipo = 'menu_dia', _demoCita = null;
let _negocioActivo = { id: null, nombre: '' };
let _todosContactos = [], _todasPlantillas = [], _plantillaSeleccionadaId = null, _canalActivo = 'whatsapp';
let _wappWin = null;
const _medioLabel = { whatsapp: '💬 WhatsApp', telegram: '✈️ Telegram', otro: '📨 Otro' };

function telVendedor()    { return localStorage.getItem('vd_tel') || ''; }
function nombreVendedor() { return localStorage.getItem('vd_nombre') || ''; }

async function cargarNegocios() {
  const tel = telVendedor(); if (!tel) return;
  try {
    const r = await fetch('/api/vendedor/mis-negocios?tel=' + encodeURIComponent(tel));
    const d = await r.json();
    if (!d.ok || !d.negocios.length) return;
    const vistos = new Set();
    const unicos = d.negocios.filter(n => { if (vistos.has(n.id)) return false; vistos.add(n.id); return true; });
    const sel = document.getElementById('sel-negocio');
    sel.innerHTML = unicos.map(n => `<option value="${n.id}" style="background:#312e81;color:white">${n.nombre}</option>`).join('');
    const guardado = parseInt(localStorage.getItem('vd_negocio_id') || '0');
    _negocioActivo = unicos.find(n => n.id === guardado) || unicos[0];
    sel.value = _negocioActivo.id;
    document.getElementById('bloque-negocio').style.display = '';
  } catch {}
}

function cambiarNegocioActivo() {
  const sel = document.getElementById('sel-negocio');
  _negocioActivo = { id: parseInt(sel.value), nombre: sel.options[sel.selectedIndex].text };
  localStorage.setItem('vd_negocio_id', _negocioActivo.id);
  const sec = document.getElementById('sec-historial-general');
  if (sec && !sec.classList.contains('hidden')) cargarHistorialGeneral();
}

async function confirmarIdentidad() {
  const nombre = document.getElementById('inp-nombre-v').value.trim();
  const telefono = document.getElementById('inp-tel-v').value.trim();
  const err = document.getElementById('txt-id-error');
  if (!nombre || telefono.replace(/\D/g,'').length < 10) {
    err.textContent = 'Completá nombre y celular (mín. 10 dígitos).'; err.classList.remove('hidden'); return;
  }
  try {
    const r = await fetch('/api/vendedor/identificar', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nombre, telefono})});
    const d = await r.json();
    if (!d.ok) { err.textContent = d.error; err.classList.remove('hidden'); return; }
    localStorage.removeItem('vd_negocio_id');
    localStorage.setItem('vd_tel', d.telefono);
    localStorage.setItem('vd_nombre', d.nombre);
    document.getElementById('modal-codigo').classList.add('hidden');
    document.getElementById('txt-vendedor-nombre').textContent = 'Hola, ' + d.nombre.split(' ')[0];
    cargarNegocios(); cargarCitas(); cargarContactos();
  } catch { err.textContent = 'Error de red.'; err.classList.remove('hidden'); }
}

function cambiarCodigo() {
  document.getElementById('inp-nombre-v').value = '';
  document.getElementById('inp-tel-v').value = '';
  document.getElementById('txt-id-error').classList.add('hidden');
  document.getElementById('btn-cancelar-modal').classList.remove('hidden');
  document.getElementById('modal-codigo').classList.remove('hidden');
}

function cerrarModalCodigo() { document.getElementById('modal-codigo').classList.add('hidden'); }

async function cargarCitas() {
  const cod = telVendedor(); if (!cod) return;
  try {
    const r = await fetch('/api/vendedor/citas?cod=' + encodeURIComponent(cod));
    const d = await r.json();
    renderCitas(d.citas || []);
  } catch { document.getElementById('txt-citas-vacio').textContent = 'Error cargando citas.'; }
}

function renderCitas(citas) {
  const c = document.getElementById('lista-citas');
  const v = document.getElementById('txt-citas-vacio');
  if (!citas.length) { v.textContent = 'Sin citas próximas — tocá + Nueva cita para agendar.'; v.classList.remove('hidden'); c.innerHTML = ''; c.appendChild(v); return; }
  v.classList.add('hidden'); c.innerHTML = '';
  citas.forEach(ct => {
    const dt = new Date(ct.fecha_hora);
    const esHoy = dt.toDateString() === new Date().toDateString();
    const hora = dt.toLocaleTimeString('es-CO', {hour:'2-digit', minute:'2-digit'});
    const fecha = esHoy ? 'Hoy ' + hora : dt.toLocaleDateString('es-CO',{weekday:'short',day:'numeric',month:'short'}) + ' ' + hora;
    const badge = {pendiente:'bg-amber-100 text-amber-700', hecha:'bg-green-100 text-green-700', cerrada:'bg-indigo-100 text-indigo-700', descartada:'bg-gray-100 text-gray-500'}[ct.estado] || '';
    const div = document.createElement('div');
    div.className = 'bg-white rounded-2xl shadow p-4 flex items-center gap-3 cursor-pointer hover:shadow-md transition';
    div.innerHTML = `<div class="flex-1" onclick="iniciarDemo(${JSON.stringify(ct).replace(/"/g,'&quot;')})"><div class="flex items-center gap-2 mb-0.5"><p class="font-bold text-gray-800 text-sm">${ct.nombre_negocio}</p><span class="text-xs px-2 py-0.5 rounded-full font-semibold ${badge}">${ct.estado}</span></div><p class="text-xs text-gray-500">${ct.nombre_dueno} · ${ct.telefono}</p><p class="text-xs text-indigo-600 font-semibold mt-0.5">${fecha}</p></div><button onclick="marcarHecha(${ct.id},event)" class="text-green-500 text-xl shrink-0 hover:scale-110 transition" title="Marcar hecha">✓</button>`;
    c.appendChild(div);
  });
}

async function marcarHecha(id, e) {
  e.stopPropagation();
  await fetch('/api/vendedor/cita/' + id + '/estado', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({estado:'hecha'})});
  cargarCitas();
}

function iniciarDemo(ct) {
  _slug = ct.negocio_slug; _demoCita = ct;
  document.getElementById('txt-demo-nombre').textContent = ct.nombre_negocio + ' — ' + ct.nombre_dueno;
  document.getElementById('sec-demo').classList.remove('hidden');
  document.getElementById('sec-demo').scrollIntoView({behavior:'smooth'});
}

function abrirModalCita() {
  const m = new Date(); m.setDate(m.getDate()+1); m.setHours(9,0,0,0);
  document.getElementById('cita-fecha').value = m.toISOString().slice(0,10);
  document.getElementById('cita-hora').value = '09:00';
  document.getElementById('txt-cita-error').classList.add('hidden');
  selTipo('restaurante','menu_dia');
  document.getElementById('modal-cita').classList.remove('hidden');
}

function cerrarModalCita() { document.getElementById('modal-cita').classList.add('hidden'); }

function selTipo(tipo, subtipo) {
  _tipo = tipo; _subtipo = subtipo;
  document.querySelectorAll('.tipo-btn').forEach(b => { b.classList.remove('border-indigo-500','bg-indigo-50'); b.classList.add('border-gray-200'); });
  const sel = document.querySelector('[data-t="' + tipo + '-' + subtipo + '"]');
  if (sel) { sel.classList.remove('border-gray-200'); sel.classList.add('border-indigo-500','bg-indigo-50'); }
}

async function guardarCita() {
  const err = document.getElementById('txt-cita-error');
  const payload = {
    vendedor_cod: telVendedor(), tipo: _tipo, subtipo: _subtipo,
    nombre_negocio: document.getElementById('cita-nombre-neg').value.trim(),
    nombre_dueno: document.getElementById('cita-nombre-due').value.trim(),
    telefono: document.getElementById('cita-telefono').value.trim(),
    fecha_hora: document.getElementById('cita-fecha').value + 'T' + document.getElementById('cita-hora').value,
    negocio_id: _negocioActivo.id || null
  };
  if (!payload.nombre_negocio || !payload.nombre_dueno || !payload.telefono) {
    err.textContent = 'Completá todos los campos.'; err.classList.remove('hidden'); return;
  }
  const btn = document.querySelector('#modal-cita button:last-child');
  btn.disabled = true; btn.textContent = 'Guardando...';
  try {
    const r = await fetch('/api/vendedor/cita', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const d = await r.json();
    if (!d.ok) { err.textContent = d.error; err.classList.remove('hidden'); btn.disabled=false; btn.textContent='Agendar cita y crear negocio'; return; }
    cerrarModalCita(); cargarCitas(); cargarContactos();
  } catch { err.textContent = 'Error de red.'; err.classList.remove('hidden'); btn.disabled=false; btn.textContent='Agendar cita y crear negocio'; }
}

function montarAC(inputEl, fetchFn, onSelect) {
  const list = document.createElement('div');
  list.className = 'absolute left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg z-50 hidden overflow-hidden';
  list.style.cssText = 'top:calc(100% + 2px); max-height:200px; overflow-y:auto';
  inputEl.parentElement.appendChild(list);
  let items = [], idx = -1, tmr;
  function render() { list.innerHTML = ''; if (!items.length) { list.classList.add('hidden'); return; } list.classList.remove('hidden'); items.forEach((it, i) => { const d = document.createElement('div'); d.className = 'px-3 py-2 text-sm cursor-pointer border-b border-gray-100 last:border-0 hover:bg-indigo-50'; d.innerHTML = it._html; d.addEventListener('mousedown', e => { e.preventDefault(); pick(i); }); list.appendChild(d); }); hl(); }
  function hl() { list.querySelectorAll('div').forEach((r, i) => r.classList.toggle('bg-indigo-100', i === idx)); if (idx >= 0) list.querySelectorAll('div')[idx]?.scrollIntoView({block:'nearest'}); }
  function pick(i) { if (i >= 0 && i < items.length) { onSelect(items[i]); list.classList.add('hidden'); idx = -1; } }
  inputEl.addEventListener('input', () => { clearTimeout(tmr); idx = -1; const q = inputEl.value.trim(); if (q.length < 2) { items = []; list.classList.add('hidden'); return; } tmr = setTimeout(async () => { items = await fetchFn(q); render(); }, 280); });
  inputEl.addEventListener('keydown', e => { if (e.key==='ArrowDown'){e.preventDefault();if(!items.length)return;if(list.classList.contains('hidden'))render();idx=Math.min(idx+1,items.length-1);hl();}else if(e.key==='ArrowUp'){e.preventDefault();idx=Math.max(idx-1,-1);hl();}else if(e.key==='Enter'&&idx>=0){e.preventDefault();pick(idx);}else if(e.key==='Escape'){list.classList.add('hidden');idx=-1;} });
  inputEl.addEventListener('blur', () => setTimeout(() => list.classList.add('hidden'), 160));
  inputEl.addEventListener('focus', () => { if (items.length) list.classList.remove('hidden'); });
}

async function fetchTerceros(q) {
  try { const r = await fetch('/api/vendedor/buscar-terceros?q=' + encodeURIComponent(q)); const d = await r.json(); return d.map(t => ({ ...t, _html: '<span class="font-semibold">'+t.nombre+'</span>&nbsp;<span class="text-gray-400 text-xs">'+(t.telefono||'')+'</span>' })); } catch { return []; }
}

async function fetchNegocios(q) {
  try { const r = await fetch('/api/vendedor/buscar-negocios?q=' + encodeURIComponent(q)); const d = await r.json(); const ic={restaurante:'🍽️',tienda:'🛒'}; return d.map(n => ({ ...n, _html: (ic[n.tipo]||'🏪')+' <span class="font-semibold">'+n.nombre+'</span>&nbsp;<span class="text-gray-400 text-xs">'+n.tipo+'</span>' })); } catch { return []; }
}

let sitActiva = null;
function abrirSituacion(n) {
  if (sitActiva && sitActiva !== n) { document.getElementById('panel-'+sitActiva).classList.add('hidden'); document.getElementById('arr-'+sitActiva).textContent='›'; document.getElementById('sit-'+sitActiva).classList.remove('border-indigo-300','shadow-md'); }
  const panel=document.getElementById('panel-'+n), arr=document.getElementById('arr-'+n), card=document.getElementById('sit-'+n);
  if (panel.classList.contains('hidden')) { panel.classList.remove('hidden'); arr.textContent='⌄'; card.classList.add('border-indigo-300','shadow-md'); sitActiva=n; }
  else { panel.classList.add('hidden'); arr.textContent='›'; card.classList.remove('border-indigo-300','shadow-md'); sitActiva=null; }
}

function verNegocio() { if (_slug) window.open('/r/'+_slug,'_blank'); }

function enviarRol(rol) {
  if (!_slug) { alert('Seleccioná una cita primero.'); return; }
  const url = window.location.origin+'/r/'+_slug+'/'+rol;
  window.open('https://wa.me/?text='+encodeURIComponent('Abrí este link 🍽️\n'+url),'_blank');
  document.getElementById('txt-rol-aviso').textContent = '✓ Link de '+rol+' enviado por WhatsApp';
}

window.addEventListener('DOMContentLoaded', () => {
  const srvNombre = {{ vd_nombre | tojson }};
  const srvTel    = {{ vd_telefono | tojson }};
  if (srvTel && srvTel.length >= 10) {
    localStorage.setItem('vd_tel', srvTel); localStorage.setItem('vd_nombre', srvNombre);
  }
  const tel = telVendedor();
  if (tel) {
    document.getElementById('modal-codigo').classList.add('hidden');
    document.getElementById('txt-vendedor-nombre').textContent = 'Hola, ' + (nombreVendedor().split(' ')[0] || tel);
    cargarNegocios(); cargarCitas(); cargarContactos();
  } else {
    const urlTel = new URLSearchParams(window.location.search).get('tel');
    if (urlTel && urlTel.replace(/\D/g,'').length >= 10) document.getElementById('inp-tel-v').value = urlTel;
  }
  document.getElementById('cita-fecha') && (document.getElementById('cita-fecha').min = new Date().toISOString().slice(0,10));
  montarAC(document.getElementById('cita-nombre-due'), fetchTerceros, item => { document.getElementById('cita-nombre-due').value=item.nombre; if(!document.getElementById('cita-telefono').value.trim()&&item.telefono) document.getElementById('cita-telefono').value=item.telefono; });
  montarAC(document.getElementById('cita-nombre-neg'), fetchNegocios, item => { document.getElementById('cita-nombre-neg').value=item.nombre; });
  document.getElementById('cita-telefono').addEventListener('blur', async () => {
    const tel = document.getElementById('cita-telefono').value.replace(/\D/g,'');
    const badge = document.getElementById('badge-tercero');
    if (tel.length < 7) { badge.classList.add('hidden'); return; }
    try { const r = await fetch('/api/vendedor/buscar-tercero?tel='+encodeURIComponent(tel)); const d=await r.json(); if(d.ok&&d.encontrado){badge.innerHTML='✓ Ya registrado: <strong>'+d.nombre+'</strong>';badge.classList.remove('hidden');const inp=document.getElementById('cita-nombre-due');if(!inp.value.trim())inp.value=d.nombre;}else{badge.classList.add('hidden');}} catch{badge.classList.add('hidden');}
  });
});

async function cargarContactos() {
  const tel = telVendedor(); if (!tel) return;
  try { const r=await fetch('/api/vendedor/contactos?tel='+encodeURIComponent(tel)); const d=await r.json(); if(!d.ok){document.getElementById('txt-contactos-vacio').textContent='Error al cargar contactos.';return;} _todosContactos=d.contactos||[]; renderContactos(_todosContactos); }
  catch { document.getElementById('txt-contactos-vacio').textContent='Error de red.'; }
}

function renderContactos(lista) {
  const el=document.getElementById('lista-contactos'), vacio=document.getElementById('txt-contactos-vacio');
  if (!lista.length) { el.innerHTML=''; vacio.textContent='Sin contactos todavía — importá o agregá uno.'; vacio.classList.remove('hidden'); document.getElementById('sec-reclamar').classList.remove('hidden'); return; }
  document.getElementById('sec-reclamar').classList.add('hidden'); vacio.classList.add('hidden');
  el.innerHTML = lista.map(c => `
    <div class="bg-white rounded-2xl shadow-sm border border-gray-100 px-4 py-3 flex items-start gap-3">
      <div class="relative shrink-0 mt-0.5">
        <div class="w-9 h-9 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-600 font-extrabold text-sm">${(c.nombre||c.telefono||'?')[0].toUpperCase()}</div>
        ${c.chat_token ? `<span class="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-green-500 border-2 border-white rounded-full"></span>` : ''}
      </div>
      <div class="flex-1 min-w-0">
        <p class="font-bold text-gray-800 text-sm break-words">${c.nombre||'—'}</p>
        <p class="text-xs text-gray-400">${c.telefono||'Sin número'}</p>
        ${c.chat_token ? `<p class="text-xs text-green-600 font-medium mt-0.5">Chat TUC TUC activo</p>` : ''}
      </div>
      <div class="flex gap-1 shrink-0 mt-0.5">
        ${c.telefono ? `
        <button onclick="llamar('${c.telefono}')" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-green-100 flex items-center justify-center text-base transition">📞</button>
        <button onclick="abrirWa('${(c.nombre||'').replace(/'/g,"\\'")}','${c.telefono}',${c.id})" class="w-8 h-8 rounded-full flex items-center justify-center text-white text-base transition" style="background:#25D366">💬</button>
        ` : ''}
        <button onclick="abrirChatContacto(${c.id},'${(c.nombre||'').replace(/'/g,"\\'")}',${c.chat_token ? `'${c.chat_token}'` : 'null'})" class="w-8 h-8 rounded-full flex items-center justify-center text-base transition ${c.chat_token ? 'bg-green-100 text-green-700' : 'bg-gray-100 hover:bg-green-100 text-gray-400'}">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.253 2 11.5c0 2.304.88 4.41 2.325 6.032L3 21l3.75-1.268A10.054 10.054 0 0012 21c5.523 0 10-4.253 10-9.5S17.523 2 12 2z"/></svg>
        </button>
        <button onclick="agendarDesdeContacto('${(c.nombre||'').replace(/'/g,"\\'")}','${c.telefono||''}')" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-indigo-100 flex items-center justify-center text-base transition">📅</button>
        <button onclick="eliminarContacto(${c.id})" class="w-8 h-8 rounded-full bg-gray-100 hover:bg-red-100 flex items-center justify-center text-base transition text-gray-400 hover:text-red-500">✕</button>
      </div>
    </div>
  `).join('');
}

function filtrarContactos(q) { if (!q.trim()) { renderContactos(_todosContactos); return; } const lo=q.toLowerCase(); renderContactos(_todosContactos.filter(c => (c.nombre||'').toLowerCase().includes(lo)||(c.telefono||'').includes(lo))); }

async function abrirChatContacto(cid, nombre, tokenExistente) {
  if (tokenExistente) { window.open('/chat/'+tokenExistente,'_blank'); return; }
  const tel=telVendedor(); if(!tel){alert('Identificate primero');return;}
  const btn=event.currentTarget; btn.disabled=true;
  try { const r=await fetch(`/api/vendedor/contactos/${cid}/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tel})}); const d=await r.json(); if(!d.ok)throw new Error(d.error); const idx=_todosContactos.findIndex(c=>c.id===cid); if(idx>=0)_todosContactos[idx].chat_token=d.token; renderContactos(_todosContactos); window.open(d.link,'_blank'); }
  catch(e){btn.disabled=false;alert('Error: '+e.message);}
}

function _fmtFecha(iso) { if(!iso)return'—'; const d=new Date(iso); return d.toLocaleDateString('es-CO',{day:'2-digit',month:'short',year:'numeric'})+' '+d.toLocaleTimeString('es-CO',{hour:'2-digit',minute:'2-digit'}); }
function toggleContactos() { const sec=document.getElementById('sec-contactos'),ico=document.getElementById('ico-contactos-toggle'),oculto=sec.classList.toggle('hidden'); ico.textContent=oculto?'▼':'▲'; }
function toggleHistorialGeneral() { const sec=document.getElementById('sec-historial-general'),ico=document.getElementById('ico-historial-toggle'),oculto=sec.classList.toggle('hidden'); ico.textContent=oculto?'▼':'▲'; if(!oculto&&document.getElementById('lista-historial-general').textContent==='Cargando...')cargarHistorialGeneral(); }

async function cargarHistorialGeneral() {
  const tel=telVendedor(), zona=document.getElementById('lista-historial-general');
  if(!tel){zona.innerHTML='<p class="text-center py-2">Ingresa tu teléfono primero.</p>';return;}
  try {
    const nid=_negocioActivo&&_negocioActivo.id?'&negocio_id='+_negocioActivo.id:'';
    const r=await fetch('/api/vendedor/envios?tel='+encodeURIComponent(tel)+nid); const d=await r.json();
    if(!d.ok||!d.envios.length){zona.innerHTML='<p class="text-center py-2 text-gray-400">Aún no hay envíos registrados.</p>';return;}
    zona.innerHTML=d.envios.map(e=>`<div class="bg-gray-50 rounded-xl px-3 py-2 flex items-start gap-2"><span class="text-base mt-0.5">${_medioLabel[e.medio]||'📨'}</span><div class="flex-1 min-w-0"><p class="font-semibold text-gray-800 text-xs truncate">${e.contacto_nombre||e.contacto_tel||'?'}</p>${e.texto_enviado?`<p class="text-xs text-gray-600 leading-snug mt-0.5">${e.texto_enviado}</p>`:''}<p class="text-xs text-gray-400 mt-0.5">${_fmtFecha(e.created_at)}</p></div><button onclick="borrarEnvio(${e.id},this)" class="w-8 h-8 flex items-center justify-center rounded-full bg-red-100 hover:bg-red-200 text-red-500 text-base transition">🗑</button></div>`).join('');
  } catch{zona.innerHTML='<p class="text-center py-2 text-red-400">Error de red.</p>';}
}

async function borrarEnvio(id, btn) { btn.disabled=true; btn.textContent='⏳'; const r=await fetch('/api/vendedor/envios/'+id,{method:'DELETE'}); const d=await r.json(); if(d.ok){btn.closest('.bg-gray-50').remove(); const z=document.getElementById('lista-historial-general'); if(!z.querySelector('.bg-gray-50'))z.innerHTML='<p class="text-center py-2 text-gray-400">Aún no hay envíos registrados.</p>';}else{btn.disabled=false;btn.textContent='🗑';} }

function llamar(tel) { window.location.href='tel:'+tel.replace(/\s/g,''); }

function seleccionarCanal(canal) {
  _canalActivo=canal;
  const bw=document.getElementById('btn-canal-wa'),bt=document.getElementById('btn-canal-tg'),ze=document.getElementById('zona-envio-wa'),be=document.getElementById('btn-enviar-canal');
  if(canal==='whatsapp'){bw.style.background='#25D366';bw.style.color='white';bt.style.background='white';bt.style.color='#2AABEE';ze.classList.remove('hidden');be.textContent='Abrir en WhatsApp →';be.style.background='#16a34a';}
  else{bt.style.background='#2AABEE';bt.style.color='white';bw.style.background='white';bw.style.color='#25D366';ze.classList.add('hidden');be.textContent='Abrir en Telegram →';be.style.background='#2AABEE';}
}

function cerrarModalContacto() { document.getElementById('modal-wa-contacto').classList.add('hidden'); }

async function abrirWa(nombre, tel, contactoId) {
  const modal=document.getElementById('modal-wa-contacto');
  document.getElementById('txt-wa-destinatario').textContent=nombre||tel;
  modal.dataset.tel=tel; modal.dataset.contactoId=contactoId||'';
  document.getElementById('inp-wa-mensaje').value='';
  document.getElementById('form-nueva-plt').classList.add('hidden');
  _plantillaSeleccionadaId=null; seleccionarCanal('whatsapp'); modal.classList.remove('hidden'); cargarPlantillas();
  if(contactoId){
    const zona=document.getElementById('lista-historial-modal');
    zona.innerHTML='<p class="text-xs text-gray-400 text-center py-1">Cargando...</p>';
    try{const r=await fetch('/api/vendedor/envios/contacto/'+contactoId);const d=await r.json();if(!d.ok||!d.envios.length){zona.innerHTML='<p class="text-xs text-gray-400 text-center py-1">Sin mensajes anteriores.</p>';}else{zona.innerHTML=d.envios.map(e=>`<div class="bg-gray-50 rounded-xl px-3 py-1.5 text-xs"><div class="flex items-center gap-1.5 mb-0.5"><span>${_medioLabel[e.medio]||'📨'}</span><span class="font-semibold text-gray-700">${e.vendedor_nombre||'?'}</span><span class="text-gray-400 ml-auto">${_fmtFecha(e.created_at)}</span></div><p class="text-gray-600 leading-snug">${e.plantilla_cuerpo||'(sin texto)'}</p></div>`).join('');}}
    catch{zona.innerHTML='<p class="text-xs text-red-400 text-center py-1">Error.</p>';}
  }
  setTimeout(()=>document.getElementById('inp-wa-mensaje').focus(),100);
}

function rellenarMsgWa(texto) { const inp=document.getElementById('inp-wa-mensaje'); inp.value=texto; inp.focus(); inp.setSelectionRange(texto.length,texto.length); }

async function cargarPlantillas() {
  const tel=telVendedor(), zona=document.getElementById('plantillas-wa');
  if(!tel){renderPlantillas([],zona);return;}
  try{const r=await fetch('/api/vendedor/plantillas?tel='+encodeURIComponent(tel));const d=await r.json();renderPlantillas(d.ok?d.plantillas:[],zona);}catch{renderPlantillas([],zona);}
}

function usarPlantilla(idx) { const p=_todasPlantillas[idx]; if(!p)return; _plantillaSeleccionadaId=p.id; rellenarMsgWa(p.cuerpo); }

function renderPlantillas(lista, zona) {
  _todasPlantillas=lista;
  zona.innerHTML=lista.map((p,i)=>`<span class="inline-flex items-center gap-1 bg-gray-100 hover:bg-green-50 text-gray-700 rounded-full pl-2.5 pr-1 py-1 text-xs transition"><button onclick="usarPlantilla(${i})" class="hover:text-green-700 font-medium">${p.titulo}</button><button onclick="editarPlantilla(${i})" class="text-gray-300 hover:text-indigo-500 px-0.5">✏</button><button onclick="eliminarPlantilla(${p.id})" class="text-gray-300 hover:text-red-500 font-bold px-0.5">✕</button></span>`).join('')+`<button onclick="abrirNuevaPlantilla()" class="text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-full px-2.5 py-1 transition font-bold">＋ Nuevo</button>`;
}

function abrirNuevaPlantilla() { const f=document.getElementById('form-nueva-plt'); document.getElementById('inp-plt-titulo').value=''; document.getElementById('inp-plt-cuerpo').value=''; delete f.dataset.pid; document.getElementById('btn-guardar-plt').textContent='Guardar'; f.classList.remove('hidden'); document.getElementById('inp-plt-titulo').focus(); }
function editarPlantilla(idx) { const p=_todasPlantillas[idx]; if(!p)return; const f=document.getElementById('form-nueva-plt'); document.getElementById('inp-plt-titulo').value=p.titulo; document.getElementById('inp-plt-cuerpo').value=p.cuerpo; f.dataset.pid=p.id; document.getElementById('btn-guardar-plt').textContent='Actualizar'; f.classList.remove('hidden'); document.getElementById('inp-plt-cuerpo').focus(); }
function cancelarNuevaPlantilla() { const f=document.getElementById('form-nueva-plt'); delete f.dataset.pid; f.classList.add('hidden'); }

async function guardarPlantilla() {
  const tel=telVendedor(), titulo=document.getElementById('inp-plt-titulo').value.trim(), cuerpo=document.getElementById('inp-plt-cuerpo').value.trim();
  if(!titulo||!cuerpo)return;
  const f=document.getElementById('form-nueva-plt'), pid=f.dataset.pid;
  try{const r=await fetch(pid?'/api/vendedor/plantillas/'+pid:'/api/vendedor/plantillas',{method:pid?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tel,titulo,cuerpo})});const d=await r.json();if(d.ok){delete f.dataset.pid;f.classList.add('hidden');cargarPlantillas();}}catch{}
}

async function eliminarPlantilla(id) { await fetch('/api/vendedor/plantillas/'+id,{method:'DELETE'}); cargarPlantillas(); }

function enviarPorCanal() {
  if(_canalActivo==='telegram'){
    const modal=document.getElementById('modal-wa-contacto'), tel=modal.dataset.tel||'', cid=modal.dataset.contactoId||'', num=tel.replace(/[^\d]/g,'');
    modal.classList.add('hidden'); window.open('https://t.me/+'+num,'_blank');
    if(cid)fetch('/api/vendedor/plantillas/envio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contacto_id:parseInt(cid),medio:'telegram',tel_vendedor:telVendedor(),mensaje_enviado:document.getElementById('inp-wa-mensaje').value.trim()||null,negocio_id:_negocioActivo.id||null})}).catch(()=>{});
    _plantillaSeleccionadaId=null;
  } else { enviarWaContacto(); }
}

function enviarWaContacto() {
  const modal=document.getElementById('modal-wa-contacto'), tel=modal.dataset.tel||'', cid=modal.dataset.contactoId||'', msg=document.getElementById('inp-wa-mensaje').value.trim(), num=tel.replace(/[^\d+]/g,'');
  modal.classList.add('hidden');
  const txtEnc=msg?encodeURIComponent(msg):'', movilUrl='https://wa.me/'+num+(msg?'?text='+txtEnc:''), appUrl='whatsapp://send?phone='+num+(msg?'&text='+txtEnc:''), webUrl='https://web.whatsapp.com/send?phone='+num+(msg?'&text='+txtEnc:'');
  if(/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)){window.open(movilUrl,'_blank');}
  else{let app=false;const h=()=>{app=true;};document.addEventListener('visibilitychange',h,{once:true});window.location.href=appUrl;setTimeout(()=>{document.removeEventListener('visibilitychange',h);if(!app){if(_wappWin&&!_wappWin.closed){_wappWin.location.href=webUrl;_wappWin.focus();}else{_wappWin=window.open(webUrl,'_blank');}}},1500);}
  if(cid)fetch('/api/vendedor/plantillas/envio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plantilla_id:_plantillaSeleccionadaId||null,contacto_id:parseInt(cid),medio:'whatsapp',tel_vendedor:telVendedor(),mensaje_enviado:msg||null,negocio_id:_negocioActivo.id||null})}).catch(()=>{});
  _plantillaSeleccionadaId=null;
}

function agendarDesdeContacto(nombre, tel) { abrirModalCita(); if(nombre)document.getElementById('cita-nombre-due').value=nombre; if(tel){document.getElementById('cita-telefono').value=tel;document.getElementById('cita-telefono').dispatchEvent(new Event('blur'));} }
function abrirImportarContactos() { document.getElementById('txt-importar-resultado').classList.add('hidden'); const picker=document.getElementById('btn-contact-picker'); if(!('contacts' in navigator&&'ContactsManager' in window))picker.classList.add('opacity-40'); document.getElementById('modal-importar-contactos').classList.remove('hidden'); }
function abrirAgregarContacto() { document.getElementById('inp-ac-nombre').value=''; document.getElementById('inp-ac-tel').value=''; document.getElementById('txt-ac-error').classList.add('hidden'); document.getElementById('modal-agregar-contacto').classList.remove('hidden'); }

async function guardarContacto() {
  const nombre=document.getElementById('inp-ac-nombre').value.trim(), tel=document.getElementById('inp-ac-tel').value.trim(), err=document.getElementById('txt-ac-error');
  if(!nombre&&!tel){err.textContent='Completá al menos nombre o celular.';err.classList.remove('hidden');return;}
  const ok=await _subirContactos([{nombre,telefono:tel}]); if(ok){document.getElementById('modal-agregar-contacto').classList.add('hidden');await cargarContactos();}
}

async function eliminarContacto(id) { if(!confirm('¿Eliminar este contacto?'))return; const tel=telVendedor(); await fetch('/api/vendedor/contactos/'+id+'?tel='+encodeURIComponent(tel),{method:'DELETE'}); await cargarContactos(); }

async function _subirContactos(lista) {
  const tel=telVendedor(), res=document.getElementById('txt-importar-resultado');
  try{const r=await fetch('/api/vendedor/contactos/importar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tel,contactos:lista})});const d=await r.json();if(d.ok){res.textContent=d.insertados+' contacto(s) importado(s)'+(d.omitidos?' · '+d.omitidos+' ya existían':'')+'.';res.className='text-xs text-center font-bold rounded-xl px-3 py-2 bg-green-50 text-green-700';res.classList.remove('hidden');await cargarContactos();return true;}else{res.textContent=d.error||'Error al importar.';res.className='text-xs text-center font-bold rounded-xl px-3 py-2 bg-red-50 text-red-700';res.classList.remove('hidden');return false;}}catch{return false;}
}

async function reclamarContactos() {
  const tel=telVendedor(); if(!tel)return;
  const btn=document.querySelector('#sec-reclamar button'); btn.textContent='Vinculando...'; btn.disabled=true;
  try{const r=await fetch('/api/vendedor/contactos/reclamar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tel})});const d=await r.json();if(d.ok){btn.textContent=d.actualizados+' contacto(s) vinculados.';await cargarContactos();}else{btn.textContent=d.error||'Error.';btn.disabled=false;}}catch{btn.textContent='Error de red.';btn.disabled=false;}
}

function importarVcf() { document.getElementById('inp-vcf').click(); }
async function procesarVcf(input) { const file=input.files[0];if(!file)return; const texto=await file.text(); input.value=''; await _subirContactos(parseVcf(texto)); }
function parseVcf(texto) { const res=[]; const bloques=texto.split(/BEGIN:VCARD/i).filter(b=>b.trim()); for(const b of bloques){const nm=b.match(/FN[^:]*:(.+)/i)||b.match(/N[^:]*:(.+)/i); const tm=b.match(/TEL[^:]*:([\d\s+\-().]+)/i); const nombre=nm?nm[1].trim().replace(/;/g,' ').replace(/\s+/g,' '):''; const tel=tm?tm[1].trim().replace(/[\s\-().]/g,''):''; if(nombre||tel)res.push({nombre,telefono:tel});} return res; }

function importarTelegram() { document.getElementById('inp-telegram').click(); }
async function procesarTelegram(input) { const file=input.files[0];if(!file)return; const texto=await file.text(); input.value=''; await _subirContactos(file.name.endsWith('.json')?parseTelegramJson(texto):parseTelegramHtml(texto)); }
function parseTelegramJson(texto) { try{const data=JSON.parse(texto); const lista=data.contacts?.list||data.list||[]; return lista.map(c=>({nombre:(c.first_name||'')+' '+(c.last_name||''),telefono:c.phone_number||''})).filter(c=>c.nombre.trim()||c.telefono);}catch{return[];} }
function parseTelegramHtml(texto) { const contactos=[]; const doc=new DOMParser().parseFromString(texto,'text/html'); doc.querySelectorAll('.contact').forEach(el=>{const nombre=el.querySelector('.contact-name')?.textContent?.trim()||''; const tel=el.querySelector('.contact-phone')?.textContent?.trim()||''; if(nombre||tel)contactos.push({nombre,telefono:tel});}); return contactos; }

async function importarContactPicker() {
  if(!('contacts' in navigator&&'ContactsManager' in window)){alert('Solo disponible en Chrome para Android.');return;}
  try{const sel=await navigator.contacts.select(['name','tel'],{multiple:true}); await _subirContactos(sel.map(c=>({nombre:(c.name||[])[0]||'',telefono:(c.tel||[])[0]||''})).filter(c=>c.nombre||c.telefono));}catch(e){if(e.name!=='AbortError')alert('Error: '+e.message);}
}
</script>
</body></html>"""
