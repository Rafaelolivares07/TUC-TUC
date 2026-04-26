import random
import re
import unicodedata
import uuid
from datetime import date, timezone

from flask import (Blueprint, jsonify, redirect, render_template,
                   request, session, url_for)

from ..db import get_db_connection
from .auth import admin_required

bp = Blueprint('restaurantes', __name__)

_tablas_listas = False


def init_tablas_restaurante():
    """Llamar desde create_app() para ejecutar migraciones antes de atender requests."""
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        conn.close()
    except Exception as e:
        print(f'[restaurantes] Error en init_tablas: {e}')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _crear_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return
    sqls = [
        """CREATE TABLE IF NOT EXISTS restaurantes (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS mesas_restaurante (
            id SERIAL PRIMARY KEY,
            restaurante_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            activo BOOLEAN DEFAULT TRUE
        )""",
        """CREATE TABLE IF NOT EXISTS opciones_menu (
            id SERIAL PRIMARY KEY,
            restaurante_id INTEGER NOT NULL,
            tipo VARCHAR(20) NOT NULL,
            nombre VARCHAR(255) NOT NULL,
            recargo DECIMAL(10,2) DEFAULT 0,
            activo BOOLEAN DEFAULT TRUE
        )""",
        """CREATE TABLE IF NOT EXISTS menu_dia (
            id SERIAL PRIMARY KEY,
            restaurante_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            precio_completo DECIMAL(10,2) NOT NULL,
            precio_bandeja DECIMAL(10,2) NOT NULL,
            precio_sopa DECIMAL(10,2) NOT NULL,
            activo BOOLEAN DEFAULT TRUE
        )""",
        """CREATE TABLE IF NOT EXISTS menu_dia_opciones (
            id SERIAL PRIMARY KEY,
            menu_dia_id INTEGER NOT NULL,
            opcion_id INTEGER NOT NULL,
            agotado BOOLEAN DEFAULT FALSE
        )""",
        """CREATE TABLE IF NOT EXISTS pedidos_restaurante (
            id SERIAL PRIMARY KEY,
            restaurante_id INTEGER NOT NULL,
            mesa_num INTEGER NOT NULL,
            tipo VARCHAR(20) NOT NULL,
            sopa_id INTEGER,
            proteina_id INTEGER,
            principio_id INTEGER,
            precio DECIMAL(10,2) NOT NULL,
            estado VARCHAR(20) DEFAULT 'pendiente',
            notas TEXT,
            nombre_cliente VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS pagos_restaurante (
            id SERIAL PRIMARY KEY,
            restaurante_id INTEGER NOT NULL,
            dias INTEGER NOT NULL,
            nota VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]
    for sql in sqls:
        conn.execute(sql)
    conn.commit()
    alters = [
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS nombre_cliente VARCHAR(100)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS tipo_restaurante VARCHAR(20) DEFAULT 'menu_dia'",
        "ALTER TABLE opciones_menu ADD COLUMN IF NOT EXISTS precio DECIMAL(10,2) DEFAULT 0",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS plato_id INTEGER",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS cantidad INTEGER DEFAULT 1",
        "ALTER TABLE opciones_menu ADD COLUMN IF NOT EXISTS imagen TEXT",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS admin_id INTEGER",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS admin_telefono VARCHAR(20)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS admin_nombre VARCHAR(255)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS token_acceso VARCHAR(100) UNIQUE",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS pin_mesero VARCHAR(10)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS pin_cocina VARCHAR(10)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS dias_pagados INTEGER DEFAULT 0",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS tipo_entrega VARCHAR(20) DEFAULT 'mesa'",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS telefono_cliente VARCHAR(20)",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS direccion_cliente TEXT",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS cliente_id INTEGER",
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS direccion TEXT",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS imagen_header TEXT",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS tema VARCHAR(10) DEFAULT 'claro'",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS mostrar_nombre BOOLEAN DEFAULT TRUE",
        "ALTER TABLE opciones_menu ADD COLUMN IF NOT EXISTS descripcion TEXT",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS lat NUMERIC(10,7)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS lon NUMERIC(10,7)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS requerir_pin_cocina BOOLEAN DEFAULT TRUE",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS requerir_pin_mesero BOOLEAN DEFAULT TRUE",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS es_ejemplo BOOLEAN DEFAULT FALSE",
        "ALTER TABLE mesas_restaurante ADD COLUMN IF NOT EXISTS nombre VARCHAR(20)",
        "ALTER TABLE mesas_restaurante ADD COLUMN IF NOT EXISTS sector VARCHAR(100)",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS mesa_nombre VARCHAR(20)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id)",
        "UPDATE restaurantes SET tercero_id = admin_id WHERE tercero_id IS NULL AND admin_id IS NOT NULL",
        "ALTER TABLE opciones_menu ADD COLUMN IF NOT EXISTS iva_pct NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS solo_carta BOOLEAN DEFAULT FALSE",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS ref_vendedor VARCHAR(50)",
        "ALTER TABLE opciones_menu ADD COLUMN IF NOT EXISTS orden INT DEFAULT 0",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS descripcion TEXT",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    _tablas_listas = True


def _generar_slug(nombre):
    slug = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')


def _enviar_telegram(chat_id, texto):
    import os, requests as req
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token or not chat_id:
        return
    try:
        req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'},
            timeout=5
        )
    except Exception:
        pass


def _auth_rest(slug, conn):
    """Devuelve (rest_row, ok) verificando sesión o token."""
    rest = conn.execute(
        "SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
    ).fetchone()
    if not rest:
        return None, False
    uid = session.get('usuario_id')
    tok = session.get('restaurante_token')
    es_admin = session.get('rol') == 'Administrador'
    autenticado = es_admin or (uid and uid == rest['admin_id']) or (tok and tok == rest['token_acceso'])
    return rest, autenticado


# ── Admin HTML ────────────────────────────────────────────────────────────────

@bp.route('/admin/restaurante')
def admin_restaurante_lista():
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        restaurantes_raw = conn.execute(
            "SELECT id, nombre, slug, admin_nombre, admin_telefono, token_acceso, dias_pagados "
            "FROM restaurantes WHERE activo = TRUE ORDER BY nombre"
        ).fetchall()
        restaurantes = []
        for r in restaurantes_raw:
            dias_usados = conn.execute(
                "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos_restaurante WHERE restaurante_id = %s",
                (r['id'],)
            ).fetchone()['dias']
            d = dict(r)
            d['dias_usados'] = dias_usados
            d['dias_restantes'] = max(0, (r['dias_pagados'] or 0) - dias_usados)
            restaurantes.append(d)
        conn.close()
        return render_template('restaurante_admin.html', restaurantes=restaurantes, restaurante=None)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/admin/restaurante/<slug>')
def admin_restaurante_detalle(slug):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        restaurante = conn.execute(
            "SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        conn.close()
        if not restaurante:
            return redirect(url_for('restaurantes.admin_restaurante_lista'))
        return render_template('restaurante_admin.html', restaurante=restaurante, restaurantes=None)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/mi-restaurante/<slug>')
def mi_restaurante(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        restaurante = conn.execute(
            "SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not restaurante:
            conn.close()
            return "Restaurante no encontrado", 404
        uid = session.get('usuario_id')
        es_admin = session.get('rol') == 'Administrador'
        tok = session.get('restaurante_token')
        autenticado = es_admin or (uid and uid == restaurante['admin_id']) or (tok and tok == restaurante['token_acceso'])
        conn.close()
        if autenticado:
            return render_template('restaurante_admin.html', restaurante=restaurante, restaurantes=None, es_dueno=True)
        return render_template('restaurante_recuperar.html', restaurante=restaurante)
    except Exception as e:
        return f"Error: {e}", 500


# ── Acceso por token mágico ───────────────────────────────────────────────────

@bp.route('/r/acceso/<token>')
def restaurante_acceso_token(token):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        restaurante = conn.execute(
            "SELECT * FROM restaurantes WHERE token_acceso = %s AND activo = TRUE", (token,)
        ).fetchone()
        if not restaurante:
            conn.close()
            return "Enlace inválido o expirado", 404
        admin_id = restaurante['admin_id']
        if admin_id:
            tercero = conn.execute(
                "SELECT id, nombre, telefono FROM terceros WHERE id = %s", (admin_id,)
            ).fetchone()
            conn.close()
            if not tercero:
                return "Usuario no encontrado", 404
            session['usuario_id'] = tercero['id']
            session['nombre'] = tercero['nombre']
            session['telefono'] = tercero['telefono'] or ''
        else:
            conn.close()
            session['nombre'] = restaurante['nombre']
            session['telefono'] = ''
        session['rol'] = 'Restaurante'
        session['restaurante_token'] = token
        session.permanent = True
        session.modified = True
        return redirect(f"/mi-restaurante/{restaurante['slug']}")
    except Exception as e:
        return f"Error: {e}", 500


# ── Recuperación de acceso ────────────────────────────────────────────────────

@bp.route('/api/restaurante/recuperar', methods=['POST'])
def api_recuperar():
    data = request.get_json()
    telefono = ''.join(filter(str.isdigit, data.get('telefono', '')))
    slug = data.get('slug', '')
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular inválido'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute(
            "SELECT id, admin_id, admin_telefono FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not rest or rest['admin_telefono'] != telefono:
            conn.close()
            return jsonify({'ok': False, 'error': 'Este celular no corresponde al administrador'}), 400
        tercero = conn.execute(
            "SELECT id, telegram_chat_id FROM terceros WHERE id = %s", (rest['admin_id'],)
        ).fetchone()
        conn.close()
        if not tercero or not tercero['telegram_chat_id']:
            return jsonify({'ok': False, 'necesita_telegram': True, 'error': 'No tenés Telegram vinculado'}), 400
        codigo = str(random.randint(100000, 999999))
        session['codigo_recuperacion'] = codigo
        session['recuperar_admin_id'] = tercero['id']
        session['recuperar_slug'] = slug
        session.modified = True
        _enviar_telegram(tercero['telegram_chat_id'],
                         f"🔐 Tu código de acceso es:\n\n<b>{codigo}</b>\n\nIngresalo en la pantalla de recuperación.")
        return jsonify({'ok': True, 'mensaje': 'Código enviado a tu Telegram'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/verificar-codigo', methods=['POST'])
def api_verificar_codigo():
    data = request.get_json()
    codigo = data.get('codigo', '').strip()
    codigo_guardado = session.get('codigo_recuperacion')
    admin_id = session.get('recuperar_admin_id')
    slug = session.get('recuperar_slug')
    if not codigo_guardado or not admin_id:
        return jsonify({'ok': False, 'error': 'No hay código pendiente'}), 400
    if codigo != codigo_guardado:
        return jsonify({'ok': False, 'error': 'Código incorrecto'}), 400
    try:
        conn = get_db_connection()
        tercero = conn.execute(
            "SELECT id, nombre, telefono FROM terceros WHERE id = %s", (admin_id,)
        ).fetchone()
        conn.close()
        if not tercero:
            return jsonify({'ok': False, 'error': 'Usuario no encontrado'}), 400
        for k in ('codigo_recuperacion', 'recuperar_admin_id', 'recuperar_slug'):
            session.pop(k, None)
        session['usuario_id'] = tercero['id']
        session['nombre'] = tercero['nombre']
        session['telefono'] = tercero['telefono'] or ''
        session['rol'] = 'Restaurante'
        session.permanent = True
        session.modified = True
        return jsonify({'ok': True, 'slug': slug})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── CRUD restaurante ──────────────────────────────────────────────────────────

@bp.route('/api/restaurante/crear', methods=['POST'])
def api_crear():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    nombre = data.get('nombre', '').strip()
    tipo = data.get('tipo_restaurante', 'menu_dia')
    admin_nombre = data.get('admin_nombre', '').strip()
    admin_telefono = ''.join(filter(str.isdigit, data.get('admin_telefono', '')))
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    if not admin_nombre or not admin_telefono:
        return jsonify({'ok': False, 'error': 'Nombre y celular del admin requeridos'}), 400
    if len(admin_telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 dígitos'}), 400
    if tipo not in ('menu_dia', 'carta', 'ambos'):
        tipo = 'menu_dia'
    slug = _generar_slug(nombre)
    token = str(uuid.uuid4())
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        if conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone():
            conn.close()
            return jsonify({'ok': False, 'error': 'Ya existe un restaurante con ese nombre'}), 400
        tercero = conn.execute(
            "SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (admin_telefono,)
        ).fetchone()
        if tercero:
            admin_id = tercero['id']
            conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (admin_nombre, admin_id))
        else:
            conn.execute("INSERT INTO terceros (nombre, telefono) VALUES (%s, %s)", (admin_nombre, admin_telefono))
            admin_id = conn.execute(
                "SELECT id FROM terceros WHERE telefono = %s", (admin_telefono,)
            ).fetchone()['id']
        conn.execute(
            "INSERT INTO restaurantes (nombre, slug, tipo_restaurante, admin_id, admin_nombre, admin_telefono, token_acceso) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (nombre, slug, tipo, admin_id, admin_nombre, admin_telefono, token)
        )
        conn.commit()
        conn.close()
        link = f"{request.host_url}r/acceso/{token}"
        return jsonify({'ok': True, 'slug': slug, 'nombre': nombre, 'token_acceso': token, 'link_acceso': link})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Catálogo / opciones ───────────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/opciones')
def api_opciones(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        opciones = conn.execute(
            "SELECT id, tipo, nombre, recargo, precio, imagen, activo, descripcion, orden "
            "FROM opciones_menu WHERE restaurante_id = %s ORDER BY orden, id",
            (rest['id'],)
        ).fetchall()
        conn.close()
        return jsonify({'ok': True, 'opciones': [dict(o) for o in opciones]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/reordenar', methods=['POST'])
def api_reordenar(slug):
    if 'usuario_id' not in session and not session.get('restaurante_token'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        items = (request.get_json() or {}).get('items', [])
        conn = get_db_connection()
        rest, auth = _auth_rest(slug, conn)
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if not auth:
            conn.close()
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        for item in items:
            conn.execute("UPDATE opciones_menu SET orden = %s WHERE id = %s AND restaurante_id = %s",
                         (item['orden'], item['id'], rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/buscar-productos')
def api_buscar_productos(slug):
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'ok': True, 'productos': []})
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        productos = conn.execute("""
            SELECT DISTINCT ON (LOWER(om.nombre), LOWER(om.tipo))
                om.nombre, om.tipo, om.precio, om.recargo
            FROM opciones_menu om
            WHERE om.restaurante_id != %s AND om.activo = TRUE AND LOWER(om.nombre) LIKE %s
            ORDER BY LOWER(om.nombre), LOWER(om.tipo), om.id DESC LIMIT 15
        """, (rest['id'], f'%{q.lower()}%')).fetchall()
        conn.close()
        return jsonify({'ok': True, 'productos': [
            {'nombre': p['nombre'], 'tipo': p['tipo'],
             'precio': float(p['precio']) if p['precio'] else 0,
             'recargo': float(p['recargo']) if p['recargo'] else 0}
            for p in productos
        ]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/adoptar-producto', methods=['POST'])
def api_adoptar_producto(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    nombre = data.get('nombre', '').strip()
    tipo = data.get('tipo', '').strip()
    if not nombre or not tipo:
        return jsonify({'ok': False, 'error': 'Nombre y tipo requeridos'}), 400
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        existente = conn.execute(
            "SELECT id FROM opciones_menu WHERE restaurante_id = %s AND LOWER(nombre) = %s AND LOWER(tipo) = %s AND activo = TRUE",
            (rest['id'], nombre.lower(), tipo.lower())
        ).fetchone()
        if existente:
            conn.close()
            return jsonify({'ok': False, 'error': f'{nombre} ya existe en tu catálogo'}), 400
        original = conn.execute(
            "SELECT nombre, tipo, precio, recargo, imagen FROM opciones_menu "
            "WHERE LOWER(nombre) = %s AND LOWER(tipo) = %s AND activo = TRUE ORDER BY id DESC LIMIT 1",
            (nombre.lower(), tipo.lower())
        ).fetchone()
        if not original:
            conn.close()
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        conn.execute(
            "INSERT INTO opciones_menu (restaurante_id, tipo, nombre, precio, recargo, imagen) VALUES (%s,%s,%s,%s,%s,%s)",
            (rest['id'], original['tipo'], original['nombre'], original['precio'], original['recargo'], original['imagen'])
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/opcion', methods=['POST'])
def api_opcion_crear(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    opcion_id = data.get('id')
    tipo = data.get('tipo', '').strip()
    nombre = data.get('nombre', '').strip()
    recargo = data.get('recargo', 0)
    precio = data.get('precio', 0)
    descripcion = data.get('descripcion', '').strip()
    if not tipo:
        return jsonify({'ok': False, 'error': 'Categoría requerida'}), 400
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id, tipo_restaurante FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        if rest['tipo_restaurante'] == 'menu_dia' and tipo not in ('sopa', 'proteina', 'principio'):
            conn.close()
            return jsonify({'ok': False, 'error': 'Tipo debe ser sopa, proteina o principio'}), 400
        if opcion_id:
            conn.execute(
                "UPDATE opciones_menu SET tipo=%s, nombre=%s, recargo=%s, precio=%s, descripcion=%s "
                "WHERE id=%s AND restaurante_id=%s",
                (tipo, nombre, recargo, precio, descripcion or None, opcion_id, rest['id'])
            )
        else:
            conn.execute(
                "INSERT INTO opciones_menu (restaurante_id, tipo, nombre, recargo, precio, descripcion) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (rest['id'], tipo, nombre, recargo, precio, descripcion or None)
            )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/opcion/<int:opcion_id>', methods=['DELETE'])
def api_opcion_eliminar(slug, opcion_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        conn.execute("UPDATE opciones_menu SET activo = FALSE WHERE id = %s AND restaurante_id = %s",
                     (opcion_id, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/opcion/<int:opcion_id>/imagen', methods=['POST', 'DELETE'])
def api_opcion_imagen(slug, opcion_id):
    if 'usuario_id' not in session and not session.get('restaurante_token'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        rest, auth = _auth_rest(slug, conn)
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if not auth:
            conn.close()
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        imagen = None if request.method == 'DELETE' else (request.get_json() or {}).get('imagen')
        conn.execute("UPDATE opciones_menu SET imagen = %s WHERE id = %s AND restaurante_id = %s",
                     (imagen, opcion_id, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/imagen-header', methods=['POST'])
def api_imagen_header(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    imagen = (request.get_json() or {}).get('imagen', '')
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute("UPDATE restaurantes SET imagen_header = %s WHERE id = %s",
                     (imagen or None, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/tema', methods=['POST'])
def api_tema(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    tema = (request.get_json() or {}).get('tema', 'claro')
    if tema not in ('claro', 'oscuro'):
        return jsonify({'ok': False, 'error': 'Tema inválido'}), 400
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute("UPDATE restaurantes SET tema = %s WHERE id = %s", (tema, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/mostrar-nombre', methods=['POST'])
def api_mostrar_nombre(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    mostrar = (request.get_json() or {}).get('mostrar', True)
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute("UPDATE restaurantes SET mostrar_nombre = %s WHERE id = %s", (mostrar, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/tipo-restaurante', methods=['POST'])
def api_tipo(slug):
    if 'usuario_id' not in session and not session.get('restaurante_token'):
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    tipo = (request.get_json() or {}).get('tipo', 'menu_dia')
    if tipo not in ('menu_dia', 'carta', 'ambos'):
        return jsonify({'ok': False, 'error': 'Tipo inválido'}), 400
    try:
        conn = get_db_connection()
        rest, auth = _auth_rest(slug, conn)
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if not auth:
            conn.close()
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        conn.execute("UPDATE restaurantes SET tipo_restaurante = %s WHERE id = %s", (tipo, rest['id']))
        conn.commit()
        verificado = conn.execute("SELECT tipo_restaurante FROM restaurantes WHERE id = %s", (rest['id'],)).fetchone()
        conn.close()
        if verificado['tipo_restaurante'] != tipo:
            return jsonify({'ok': False, 'error': 'No se guardó'}), 500
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/admin/ubicacion', methods=['POST'])
def api_ubicacion(slug):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'sin_sesion'}), 401
    try:
        data = request.get_json(force=True)
        lat = data.get('lat')
        lon = data.get('lon')
        if lat is None or lon is None:
            return jsonify({'ok': False, 'error': 'Coordenadas requeridas'}), 400
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute(
            "SELECT id FROM restaurantes WHERE slug=%s AND (admin_id=%s OR %s)",
            (slug, uid, session.get('rol') == 'Administrador')
        ).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin acceso'}), 403
        conn.execute("UPDATE restaurantes SET lat=%s, lon=%s WHERE id=%s", (lat, lon, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Menú del día ──────────────────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/menu-dia')
def api_menu_dia(slug):
    fecha = request.args.get('fecha') or date.today().isoformat()
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        menu = conn.execute(
            "SELECT id, fecha, precio_completo, precio_bandeja, precio_sopa "
            "FROM menu_dia WHERE restaurante_id = %s AND fecha = %s AND activo = TRUE",
            (rest['id'], fecha)
        ).fetchone()
        if not menu:
            ultimo = conn.execute(
                "SELECT precio_completo, precio_bandeja, precio_sopa FROM menu_dia "
                "WHERE restaurante_id = %s AND activo = TRUE ORDER BY fecha DESC LIMIT 1",
                (rest['id'],)
            ).fetchone()
            conn.close()
            return jsonify({'ok': True, 'menu': None, 'opciones_activas': [],
                            'precios_sugeridos': {'precio_completo': float(ultimo['precio_completo']),
                                                   'precio_bandeja': float(ultimo['precio_bandeja']),
                                                   'precio_sopa': float(ultimo['precio_sopa'])} if ultimo else None})
        opciones = conn.execute("""
            SELECT mdo.id as mdo_id, mdo.opcion_id, mdo.agotado,
                   om.tipo, om.nombre, om.recargo
            FROM menu_dia_opciones mdo
            JOIN opciones_menu om ON om.id = mdo.opcion_id
            WHERE mdo.menu_dia_id = %s ORDER BY om.tipo, om.nombre
        """, (menu['id'],)).fetchall()
        conn.close()
        return jsonify({'ok': True,
                        'menu': {'id': menu['id'],
                                 'fecha': menu['fecha'].isoformat() if hasattr(menu['fecha'], 'isoformat') else str(menu['fecha']),
                                 'precio_completo': float(menu['precio_completo']),
                                 'precio_bandeja': float(menu['precio_bandeja']),
                                 'precio_sopa': float(menu['precio_sopa'])},
                        'opciones_activas': [dict(o) for o in opciones]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/menu-dia', methods=['POST'])
def api_menu_dia_guardar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    fecha = data.get('fecha')
    precio_completo = data.get('precio_completo')
    precio_bandeja = data.get('precio_bandeja')
    precio_sopa = data.get('precio_sopa')
    opciones_ids = data.get('opciones_ids', [])
    if not fecha or not precio_completo:
        return jsonify({'ok': False, 'error': 'Fecha y precio completo requeridos'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        menu = conn.execute(
            "SELECT id FROM menu_dia WHERE restaurante_id = %s AND fecha = %s", (rest['id'], fecha)
        ).fetchone()
        if menu:
            menu_id = menu['id']
            conn.execute("UPDATE menu_dia SET precio_completo=%s, precio_bandeja=%s, precio_sopa=%s, activo=TRUE WHERE id=%s",
                         (precio_completo, precio_bandeja, precio_sopa, menu_id))
            conn.execute("DELETE FROM menu_dia_opciones WHERE menu_dia_id = %s", (menu_id,))
        else:
            row = conn.execute(
                "INSERT INTO menu_dia (restaurante_id, fecha, precio_completo, precio_bandeja, precio_sopa) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (rest['id'], fecha, precio_completo, precio_bandeja, precio_sopa)
            ).fetchone()
            menu_id = row[0]
        for op_id in opciones_ids:
            conn.execute("INSERT INTO menu_dia_opciones (menu_dia_id, opcion_id) VALUES (%s,%s)", (menu_id, op_id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'menu_id': menu_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Mesas ─────────────────────────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/mesas')
def api_mesas(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        mesas = conn.execute("""
            SELECT id, numero, COALESCE(nombre, numero::text) as nombre, sector
            FROM mesas_restaurante
            WHERE restaurante_id = %s AND activo = TRUE
            ORDER BY sector NULLS FIRST,
                     CASE WHEN nombre ~ '^[0-9]+$' THEN nombre::int ELSE NULL END NULLS LAST,
                     nombre
        """, (rest['id'],)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'mesas': [dict(m) for m in mesas]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/mesa', methods=['POST'])
def api_mesa_crear(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json(force=True)
    nombre = (data.get('nombre') or str(data.get('numero') or '')).strip()
    sector = (data.get('sector') or '').strip() or None
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre de mesa requerido'}), 400
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        if conn.execute("SELECT id FROM mesas_restaurante WHERE restaurante_id=%s AND nombre=%s AND activo=TRUE",
                        (rest['id'], nombre)).fetchone():
            conn.close()
            return jsonify({'ok': False, 'error': f'Mesa {nombre} ya existe'}), 400
        max_num = conn.execute("SELECT COALESCE(MAX(numero),0) as m FROM mesas_restaurante WHERE restaurante_id=%s",
                               (rest['id'],)).fetchone()['m']
        conn.execute("INSERT INTO mesas_restaurante (restaurante_id, numero, nombre, sector) VALUES (%s,%s,%s,%s)",
                     (rest['id'], max_num + 1, nombre, sector))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/mesas/bulk', methods=['POST'])
def api_mesas_bulk(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = None
    try:
        data = request.get_json(force=True)
        sector = (data.get('sector') or '').strip() or None
        prefijo = (data.get('prefijo') or '').strip()
        cantidad = int(data.get('cantidad', 0))
        desde = int(data.get('desde', 1))
        if cantidad < 1 or cantidad > 100:
            return jsonify({'ok': False, 'error': 'Cantidad inválida (1-100)'}), 400
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        max_num = conn.execute("SELECT COALESCE(MAX(numero),0) as m FROM mesas_restaurante WHERE restaurante_id=%s",
                               (rest['id'],)).fetchone()['m']
        creadas = 0
        for i in range(desde, desde + cantidad):
            nombre = f"{prefijo}{i}"
            if not conn.execute("SELECT id FROM mesas_restaurante WHERE restaurante_id=%s AND nombre=%s AND activo=TRUE",
                                (rest['id'], nombre)).fetchone():
                max_num += 1
                conn.execute("INSERT INTO mesas_restaurante (restaurante_id, numero, nombre, sector) VALUES (%s,%s,%s,%s)",
                             (rest['id'], max_num, nombre, sector))
                creadas += 1
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'creadas': creadas})
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/mesa/<int:mesa_id>', methods=['DELETE'])
def api_mesa_eliminar(slug, mesa_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        conn.execute("UPDATE mesas_restaurante SET activo = FALSE WHERE id = %s AND restaurante_id = %s",
                     (mesa_id, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── PINs ──────────────────────────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/pines', methods=['GET'])
def api_pines_get(slug):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute(
            "SELECT id, admin_id, pin_mesero, pin_cocina, requerir_pin_mesero, requerir_pin_cocina "
            "FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        conn.close()
        if not rest:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if session.get('rol') != 'Administrador' and uid != rest['admin_id']:
            return jsonify({'ok': False, 'error': 'Sin permisos'}), 403
        return jsonify({'ok': True,
                        'pin_mesero': rest['pin_mesero'] or '',
                        'pin_cocina': rest['pin_cocina'] or '',
                        'requerir_pin_mesero': rest['requerir_pin_mesero'] if rest['requerir_pin_mesero'] is not None else True,
                        'requerir_pin_cocina': rest['requerir_pin_cocina'] if rest['requerir_pin_cocina'] is not None else True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pines', methods=['POST'])
def api_pines_set(slug):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id, admin_id FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if session.get('rol') != 'Administrador' and uid != rest['admin_id']:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin permisos'}), 403
        data = request.get_json()
        pin_mesero = data.get('pin_mesero', '').strip()
        pin_cocina = data.get('pin_cocina', '').strip()
        conn.execute("UPDATE restaurantes SET pin_mesero=%s, pin_cocina=%s WHERE id=%s",
                     (pin_mesero or None, pin_cocina or None, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/verificar-pin', methods=['POST'])
def api_verificar_pin(slug):
    data = request.get_json()
    pin = data.get('pin', '').strip()
    rol = data.get('rol', '')
    if rol not in ('mesero', 'cocina'):
        return jsonify({'ok': False, 'error': 'Rol inválido'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute(
            "SELECT id, pin_mesero, pin_cocina FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        conn.close()
        if not rest:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        pin_correcto = rest[f'pin_{rol}']
        if not pin_correcto:
            return jsonify({'ok': False, 'error': 'El administrador no ha configurado el PIN aún'}), 400
        if pin == pin_correcto:
            return jsonify({'ok': True})
        return jsonify({'ok': False, 'error': 'PIN incorrecto'}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/toggle-pin', methods=['POST'])
def api_toggle_pin(slug):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json()
    rol = data.get('rol', '')
    valor = data.get('valor')
    if rol not in ('mesero', 'cocina') or valor is None:
        return jsonify({'ok': False, 'error': 'Parámetros inválidos'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id, admin_id FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if session.get('rol') != 'Administrador' and uid != rest['admin_id']:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin permisos'}), 403
        campo = 'requerir_pin_mesero' if rol == 'mesero' else 'requerir_pin_cocina'
        conn.execute(f"UPDATE restaurantes SET {campo} = %s WHERE id = %s", (bool(valor), rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/toggle-solo-carta', methods=['POST'])
def api_toggle_solo_carta(slug):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    valor = (request.get_json() or {}).get('valor')
    if valor is None:
        return jsonify({'ok': False, 'error': 'Parámetros inválidos'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id, admin_id FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if session.get('rol') != 'Administrador' and uid != rest['admin_id']:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin permisos'}), 403
        conn.execute("UPDATE restaurantes SET solo_carta = %s WHERE id = %s", (bool(valor), rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Suscripción / días pagados ────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/suscripcion')
def api_suscripcion(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id, dias_pagados FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        dias_pagados = rest['dias_pagados'] or 0
        dias_usados = conn.execute(
            "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos_restaurante WHERE restaurante_id = %s",
            (rest['id'],)
        ).fetchone()['dias']
        conn.close()
        return jsonify({'ok': True, 'dias_pagados': dias_pagados, 'dias_usados': dias_usados,
                        'dias_restantes': max(0, dias_pagados - dias_usados)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/dias-pagados', methods=['POST'])
def api_dias_pagados(slug):
    if session.get('rol') != 'Administrador':
        return jsonify({'ok': False, 'error': 'Solo administradores'}), 403
    data = request.get_json()
    dias = data.get('dias')
    nota = data.get('nota', '').strip()
    if not dias or not isinstance(dias, int) or dias <= 0:
        return jsonify({'ok': False, 'error': 'Número de días inválido'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id, dias_pagados FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        nuevo_total = (rest['dias_pagados'] or 0) + dias
        conn.execute("UPDATE restaurantes SET dias_pagados = %s WHERE id = %s", (nuevo_total, rest['id']))
        conn.execute("INSERT INTO pagos_restaurante (restaurante_id, dias, nota) VALUES (%s,%s,%s)",
                     (rest['id'], dias, nota or None))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'nuevo_total': nuevo_total})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pagos')
def api_pagos(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        pagos = conn.execute(
            "SELECT dias, nota, created_at FROM pagos_restaurante WHERE restaurante_id = %s ORDER BY created_at DESC",
            (rest['id'],)
        ).fetchall()
        conn.close()
        return jsonify({'ok': True, 'pagos': [
            {'dias': p['dias'], 'nota': p['nota'] or '', 'fecha': p['created_at'].strftime('%Y-%m-%d %H:%M')}
            for p in pagos
        ]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Vistas públicas ───────────────────────────────────────────────────────────

@bp.route('/r/<slug>/mesero')
def restaurante_mesero(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        conn.close()
        if not rest:
            return "Restaurante no encontrado", 404
        uid = session.get('usuario_id')
        skip_pin = uid and (session.get('rol') == 'Administrador' or uid == rest['admin_id'])
        requerir = rest['requerir_pin_mesero'] if rest['requerir_pin_mesero'] is not None else True
        tiene_pin = requerir and not skip_pin
        return render_template('restaurante_mesero.html', restaurante=rest, tiene_pin=tiene_pin)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/r/<slug>/cocina')
def restaurante_cocina(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        conn.close()
        if not rest:
            return "Restaurante no encontrado", 404
        uid = session.get('usuario_id')
        skip_pin = uid and (session.get('rol') == 'Administrador' or uid == rest['admin_id'])
        requerir = rest['requerir_pin_cocina'] if rest['requerir_pin_cocina'] is not None else True
        tiene_pin = requerir and not skip_pin
        return render_template('restaurante_cocina.html', restaurante=rest, tiene_pin=tiene_pin)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/r/<slug>')
def restaurante_publico(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        conn.close()
        if not rest:
            return "Restaurante no encontrado", 404
        cliente_data = None
        if session.get('usuario_id'):
            conn2 = get_db_connection()
            tercero = conn2.execute(
                "SELECT nombre, telefono, direccion FROM terceros WHERE id = %s", (session['usuario_id'],)
            ).fetchone()
            conn2.close()
            if tercero:
                cliente_data = {'nombre': tercero['nombre'], 'telefono': tercero['telefono'] or '',
                                'direccion': tercero['direccion'] or '', 'cliente_id': session['usuario_id']}
        solo_carta = bool(rest['solo_carta']) if rest['solo_carta'] is not None else False
        return render_template('restaurante_cliente.html', restaurante=rest, mesa_nombre='',
                               cliente_data=cliente_data, solo_carta=solo_carta)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/r/<slug>/mesa/<mesa_nombre>')
def restaurante_cliente(slug, mesa_nombre):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return "Restaurante no encontrado", 404
        mesa = conn.execute(
            "SELECT id FROM mesas_restaurante WHERE restaurante_id = %s AND (nombre = %s OR numero::text = %s) AND activo = TRUE",
            (rest['id'], mesa_nombre, mesa_nombre)
        ).fetchone()
        conn.close()
        if not mesa:
            return "Mesa no encontrada", 404
        solo_carta = bool(rest['solo_carta']) if rest['solo_carta'] is not None else False
        return render_template('restaurante_cliente.html', restaurante=rest, mesa_nombre=mesa_nombre,
                               cliente_data=None, solo_carta=solo_carta)
    except Exception as e:
        return f"Error: {e}", 500


# ── Pedidos ───────────────────────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/registrar-cliente', methods=['POST'])
def api_registrar_cliente(slug):
    data = request.get_json()
    nombre = data.get('nombre', '').strip()
    telefono = ''.join(filter(str.isdigit, data.get('telefono', '')))
    direccion = data.get('direccion', '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 dígitos'}), 400
    try:
        conn = get_db_connection()
        tercero = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)).fetchone()
        if tercero:
            cliente_id = tercero['id']
            conn.execute("UPDATE terceros SET nombre=%s, direccion=%s WHERE id=%s",
                         (nombre, direccion or None, cliente_id))
        else:
            conn.execute("INSERT INTO terceros (nombre, telefono, direccion) VALUES (%s,%s,%s)",
                         (nombre, telefono, direccion or None))
            cliente_id = conn.execute("SELECT id FROM terceros WHERE telefono = %s", (telefono,)).fetchone()['id']
        conn.commit()
        conn.close()
        session['usuario_id'] = cliente_id
        session['nombre'] = nombre
        session['telefono'] = telefono
        session['rol'] = 'Cliente'
        session.permanent = True
        session.modified = True
        return jsonify({'ok': True, 'cliente_id': cliente_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pedido', methods=['POST'])
def api_pedido_crear(slug):
    try:
        data = request.get_json(force=True) or {}
        mesa_nombre = str(data.get('mesa_nombre') or '').strip() or None
        nombre_cliente = data.get('nombre_cliente', '').strip() or None
        notas = data.get('notas', '').strip()
        tipo_entrega = data.get('tipo_entrega', 'mesa')
        telefono_cliente = data.get('telefono_cliente') or None
        direccion_cliente = data.get('direccion_cliente') or None
        cliente_id = data.get('cliente_id')
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id, tipo_restaurante, dias_pagados FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404

        # Verificar suscripción
        dias_pagados = rest['dias_pagados'] or 0
        if dias_pagados > 0:
            dias_usados = conn.execute(
                "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos_restaurante WHERE restaurante_id = %s",
                (rest['id'],)
            ).fetchone()['dias']
            tiene_pedidos_hoy = conn.execute(
                "SELECT 1 FROM pedidos_restaurante WHERE restaurante_id = %s AND DATE(created_at) = CURRENT_DATE LIMIT 1",
                (rest['id'],)
            ).fetchone()
            if not tiene_pedidos_hoy and dias_usados >= dias_pagados:
                conn.close()
                return jsonify({'ok': False, 'error': 'suscripcion_agotada',
                                'dias_pagados': dias_pagados, 'dias_usados': dias_usados}), 402

        precio_total = 0
        es_carta = rest['tipo_restaurante'] == 'carta' or (rest['tipo_restaurante'] == 'ambos' and data.get('platos'))

        if es_carta:
            platos = data.get('platos', [])
            if not platos:
                conn.close()
                return jsonify({'ok': False, 'error': 'Selecciona al menos un plato'}), 400
            for p in platos:
                opcion = conn.execute(
                    "SELECT id, nombre, precio FROM opciones_menu WHERE id=%s AND restaurante_id=%s AND activo=TRUE",
                    (p['plato_id'], rest['id'])
                ).fetchone()
                if not opcion:
                    continue
                cant = p.get('cantidad', 1)
                precio_item = float(opcion['precio']) * cant
                precio_total += precio_item
                nota_item = p.get('nota', '').strip() or None
                conn.execute("""
                    INSERT INTO pedidos_restaurante
                    (restaurante_id, mesa_num, mesa_nombre, tipo, plato_id, cantidad, precio, notas, nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id)
                    VALUES (%s, 0, %s, 'carta', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (rest['id'], mesa_nombre, opcion['id'], cant, precio_item, nota_item,
                      nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id))
        else:
            tipo = data.get('tipo')
            sopa_id = data.get('sopa_id')
            proteina_id = data.get('proteina_id')
            principio_id = data.get('principio_id')
            if tipo not in ('completo', 'bandeja', 'sopa'):
                conn.close()
                return jsonify({'ok': False, 'error': 'Tipo requerido'}), 400
            menu = conn.execute(
                "SELECT id, precio_completo, precio_bandeja, precio_sopa FROM menu_dia "
                "WHERE restaurante_id = %s AND fecha = %s AND activo = TRUE",
                (rest['id'], date.today().isoformat())
            ).fetchone()
            if not menu:
                conn.close()
                return jsonify({'ok': False, 'error': 'No hay menú configurado para hoy'}), 400
            precio_total = float(menu[f'precio_{tipo}'])
            if proteina_id and tipo in ('completo', 'bandeja'):
                recargo = conn.execute("SELECT recargo FROM opciones_menu WHERE id = %s", (proteina_id,)).fetchone()
                if recargo and recargo['recargo']:
                    precio_total += float(recargo['recargo'])
            conn.execute("""
                INSERT INTO pedidos_restaurante
                (restaurante_id, mesa_num, mesa_nombre, tipo, sopa_id, proteina_id, principio_id, precio, notas, nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id)
                VALUES (%s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (rest['id'], mesa_nombre, tipo, sopa_id, proteina_id, principio_id, precio_total,
                  notas or None, nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id))

        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'precio': precio_total})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pedidos')
def api_pedidos(slug):
    estado = request.args.get('estado', 'pendiente,listo')
    estados = [e.strip() for e in estado.split(',')]
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        placeholders = ','.join(['%s'] * len(estados))
        pedidos = conn.execute(f"""
            SELECT p.id, p.mesa_num, p.mesa_nombre, p.tipo, p.precio, p.estado, p.notas, p.nombre_cliente, p.created_at,
                   p.cantidad, p.tipo_entrega, p.telefono_cliente, p.direccion_cliente, p.cliente_id,
                   s.nombre as sopa_nombre, pr.nombre as proteina_nombre, pr.recargo as proteina_recargo,
                   pi.nombre as principio_nombre, pl.nombre as plato_nombre
            FROM pedidos_restaurante p
            LEFT JOIN opciones_menu s ON s.id = p.sopa_id
            LEFT JOIN opciones_menu pr ON pr.id = p.proteina_id
            LEFT JOIN opciones_menu pi ON pi.id = p.principio_id
            LEFT JOIN opciones_menu pl ON pl.id = p.plato_id
            WHERE p.restaurante_id = %s AND p.estado IN ({placeholders})
            AND p.created_at::date = CURRENT_DATE
            ORDER BY p.created_at DESC
        """, (rest['id'], *estados)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'pedidos': [{
            'id': p['id'], 'mesa_num': p['mesa_num'], 'mesa_nombre': p['mesa_nombre'] or '',
            'tipo': p['tipo'], 'precio': float(p['precio']), 'estado': p['estado'],
            'notas': p['notas'], 'sopa': p['sopa_nombre'], 'proteina': p['proteina_nombre'],
            'proteina_recargo': float(p['proteina_recargo']) if p['proteina_recargo'] else 0,
            'principio': p['principio_nombre'], 'plato': p['plato_nombre'],
            'cantidad': p['cantidad'] or 1, 'nombre_cliente': p['nombre_cliente'],
            'tipo_entrega': p['tipo_entrega'] or 'mesa', 'telefono_cliente': p['telefono_cliente'],
            'direccion_cliente': p['direccion_cliente'], 'cliente_id': p['cliente_id'],
            'created_at': p['created_at'].strftime('%H:%M') if p['created_at'] else ''
        } for p in pedidos]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pedido/<int:pedido_id>/listo', methods=['POST'])
def api_pedido_listo(slug, pedido_id):
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute("UPDATE pedidos_restaurante SET estado='listo' WHERE id=%s AND restaurante_id=%s AND estado='pendiente'",
                     (pedido_id, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pedido/<int:pedido_id>/entregado', methods=['POST'])
def api_pedido_entregado(slug, pedido_id):
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute("UPDATE pedidos_restaurante SET estado='entregado' WHERE id=%s AND restaurante_id=%s AND estado='listo'",
                     (pedido_id, rest['id']))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/agotar/<int:opcion_id>', methods=['POST'])
def api_agotar(slug, opcion_id):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        menu = conn.execute(
            "SELECT id FROM menu_dia WHERE restaurante_id = %s AND fecha = %s AND activo = TRUE",
            (rest['id'], date.today().isoformat())
        ).fetchone()
        if not menu:
            conn.close()
            return jsonify({'ok': False, 'error': 'No hay menú hoy'}), 400
        mdo = conn.execute(
            "SELECT id, agotado FROM menu_dia_opciones WHERE menu_dia_id=%s AND opcion_id=%s",
            (menu['id'], opcion_id)
        ).fetchone()
        if mdo:
            conn.execute("UPDATE menu_dia_opciones SET agotado = NOT agotado WHERE id = %s", (mdo['id'],))
        conn.commit()
        nuevo_estado = not mdo['agotado'] if mdo else False
        conn.close()
        return jsonify({'ok': True, 'agotado': nuevo_estado})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Cuentas / cobro ───────────────────────────────────────────────────────────

@bp.route('/api/restaurante/<slug>/cuentas')
def api_cuentas(slug):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        cuentas = conn.execute("""
            SELECT COALESCE(NULLIF(mesa_nombre,''), mesa_num::text) as mesa_id,
                   COUNT(*) as cantidad, SUM(precio) as total
            FROM pedidos_restaurante
            WHERE restaurante_id = %s AND estado != 'cobrado' AND created_at::date = CURRENT_DATE
            GROUP BY COALESCE(NULLIF(mesa_nombre,''), mesa_num::text)
            ORDER BY COALESCE(NULLIF(mesa_nombre,''), mesa_num::text)
        """, (rest['id'],)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'cuentas': [
            {'mesa_id': c['mesa_id'], 'cantidad': c['cantidad'], 'total': float(c['total'])}
            for c in cuentas
        ]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/cobrar/<mesa_id>', methods=['POST'])
def api_cobrar(slug, mesa_id):
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        conn.execute("""
            UPDATE pedidos_restaurante SET estado = 'cobrado'
            WHERE restaurante_id = %s
            AND (mesa_nombre = %s OR (COALESCE(mesa_nombre,'') = '' AND mesa_num::text = %s))
            AND estado != 'cobrado' AND created_at::date = CURRENT_DATE
        """, (rest['id'], mesa_id, mesa_id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/venta-dia')
def api_venta_dia(slug):
    try:
        conn = get_db_connection()
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        venta = conn.execute("""
            SELECT COUNT(*) as cantidad, COALESCE(SUM(precio),0) as total
            FROM pedidos_restaurante
            WHERE restaurante_id = %s AND estado = 'cobrado' AND created_at::date = CURRENT_DATE
        """, (rest['id'],)).fetchone()
        conn.close()
        return jsonify({'ok': True, 'cantidad': venta['cantidad'], 'total': float(venta['total'])})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/ventas')
def api_ventas(slug):
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    if not desde or not hasta:
        return jsonify({'ok': False, 'error': 'Fechas requeridas'}), 400
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        pedidos = conn.execute("""
            SELECT p.id, p.mesa_num, p.tipo, p.precio, p.estado, p.notas, p.nombre_cliente,
                   p.cantidad, p.tipo_entrega, p.telefono_cliente, p.direccion_cliente, p.created_at,
                   s.nombre as sopa_nombre, pr.nombre as proteina_nombre,
                   pi.nombre as principio_nombre, pl.nombre as plato_nombre
            FROM pedidos_restaurante p
            LEFT JOIN opciones_menu s ON s.id = p.sopa_id
            LEFT JOIN opciones_menu pr ON pr.id = p.proteina_id
            LEFT JOIN opciones_menu pi ON pi.id = p.principio_id
            LEFT JOIN opciones_menu pl ON pl.id = p.plato_id
            WHERE p.restaurante_id = %s AND p.created_at::date >= %s AND p.created_at::date <= %s
            ORDER BY p.created_at DESC
        """, (rest['id'], desde, hasta)).fetchall()
        conn.close()
        resultado = []
        for p in pedidos:
            items = ([p['plato_nombre']] if p['plato_nombre']
                     else [p[c] for c in ('sopa_nombre', 'proteina_nombre', 'principio_nombre') if p[c]])
            resultado.append({
                'id': p['id'], 'mesa_num': p['mesa_num'], 'tipo': p['tipo'],
                'precio': float(p['precio']), 'estado': p['estado'],
                'nombre_cliente': p['nombre_cliente'], 'cantidad': p['cantidad'] or 1,
                'tipo_entrega': p['tipo_entrega'] or 'mesa', 'items': items,
                'plato': p['plato_nombre'], 'notas': p['notas'],
                'fecha': p['created_at'].strftime('%Y-%m-%d') if p['created_at'] else '',
                'hora': p['created_at'].strftime('%H:%M') if p['created_at'] else ''
            })
        return jsonify({'ok': True, 'pedidos': resultado})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Docs ──────────────────────────────────────────────────────────────────────

@bp.route('/docs/restaurante')
@bp.route('/admin/docs/restaurante')
def docs_restaurante():
    return render_template('docs_restaurante.html')
