import json
import random
import re
import unicodedata
import uuid
from datetime import date, timezone

from flask import (Blueprint, jsonify, make_response, redirect, render_template,
                   request, session, url_for)

from ..db import get_db_connection
from ..visitas_publicas import (
    listar_visitas_publicas,
    registrar_visita_publica,
    respuesta_con_visitante,
)
from .auth import admin_required
from .inventarios import _aplicar_tarjeta
try:
    from .contabilidad import _ejecutar_asiento_automatico as _asiento_auto
except ImportError:
    _asiento_auto = None

bp = Blueprint('restaurantes', __name__)

_tablas_listas = True  # tablas ya existen en producción



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
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS plato_id INTEGER",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS cantidad INTEGER DEFAULT 1",
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
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS solo_carta BOOLEAN DEFAULT FALSE",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS ref_vendedor VARCHAR(50)",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS descripcion TEXT",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20)",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS comprobante_pago TEXT",
    ]
    conn.execute("SET statement_timeout = '3000'")
    for sql in alters:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    conn.execute("SET statement_timeout = '0'")
    _tablas_listas = True


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


def _asegurar_domicilio_restaurante(conn):
    alters = [
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS subtotal_productos NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS valor_domicilio NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS domicilio_estado VARCHAR(30) DEFAULT 'no_aplica'",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS cliente_lat NUMERIC(10,7)",
        "ALTER TABLE pedidos_restaurante ADD COLUMN IF NOT EXISTS cliente_lon NUMERIC(10,7)",
    ]
    for sql in alters:
        conn.execute(sql)


def _punto_en_poligono(lat, lon, poligono):
    if lat is None or lon is None or not poligono or len(poligono) < 3:
        return False
    dentro = False
    j = len(poligono) - 1
    for i, punto in enumerate(poligono):
        lat_i = float(punto.get('lat') or 0)
        lon_i = float(punto.get('lon') or 0)
        lat_j = float(poligono[j].get('lat') or 0)
        lon_j = float(poligono[j].get('lon') or 0)
        cruza = ((lon_i > lon) != (lon_j > lon)) and (
            lat < (lat_j - lat_i) * (lon - lon_i) / ((lon_j - lon_i) or 1e-12) + lat_i
        )
        if cruza:
            dentro = not dentro
        j = i
    return dentro


def _config_domicilio(conn, tercero_id):
    if not tercero_id:
        return {'tarifa': 0, 'modo_fuera': 'por_confirmar', 'zona': []}
    try:
        row = conn.execute("""
            SELECT domicilio_tarifa, domicilio_modo_fuera, domicilio_zona
            FROM config_negocio WHERE tercero_id=%s
        """, (tercero_id,)).fetchone()
        if row:
            return {
                'tarifa': float(row['domicilio_tarifa'] or 0),
                'modo_fuera': row['domicilio_modo_fuera'] or 'por_confirmar',
                'zona': row['domicilio_zona'] or [],
            }
    except Exception:
        pass
    return {'tarifa': 0, 'modo_fuera': 'por_confirmar', 'zona': []}


def _calcular_domicilio(conn, tercero_id, tipo_entrega, lat, lon):
    if tipo_entrega != 'domicilio':
        return 0.0, 'no_aplica'
    cfg = _config_domicilio(conn, tercero_id)
    tarifa = float(cfg.get('tarifa') or 0)
    zona = cfg.get('zona') or []
    if not tarifa:
        return 0.0, 'por_confirmar'
    if lat is None or lon is None:
        return 0.0, 'por_confirmar'
    if zona and _punto_en_poligono(float(lat), float(lon), zona):
        return tarifa, 'confirmado'
    if not zona:
        return tarifa, 'confirmado'
    if cfg.get('modo_fuera') == 'rechazar':
        return None, 'fuera_cobertura'
    return 0.0, 'por_confirmar'


def _asegurar_experiencia_restaurante(conn):
    conn.execute("ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS pantalla_experiencial BOOLEAN DEFAULT FALSE")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS restaurante_experiencia_bloques (
            id SERIAL PRIMARY KEY,
            restaurante_id INTEGER NOT NULL REFERENCES restaurantes(id) ON DELETE CASCADE,
            tipo VARCHAR(20) NOT NULL,
            titulo VARCHAR(180),
            texto TEXT,
            media JSONB DEFAULT '[]'::jsonb,
            activo BOOLEAN DEFAULT TRUE,
            orden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_restaurante_experiencia_bloques
        ON restaurante_experiencia_bloques(restaurante_id, orden, id)
    """)
    conn.commit()


def _bloques_experiencia_restaurante(conn, restaurante_id, activo=True):
    _asegurar_experiencia_restaurante(conn)
    filtro = "AND activo = TRUE" if activo else ""
    rows = conn.execute(f"""
        SELECT id, tipo, titulo, texto, media, activo, orden
        FROM restaurante_experiencia_bloques
        WHERE restaurante_id = %s {filtro}
        ORDER BY orden, id
    """, (restaurante_id,)).fetchall()
    bloques = []
    for r in rows:
        item = dict(r)
        item['media'] = item.get('media') or []
        bloques.append(item)
    return bloques


def _generar_slug(nombre):
    slug = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    slug = slug.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')


def _enviar_telegram(*args):
    conn = None
    if len(args) == 3:
        conn, chat_id, texto = args
    elif len(args) == 2:
        chat_id, texto = args
    else:
        return
    if not chat_id:
        return
    try:
        import os, requests as req
        token = ''
        if conn:
            try:
                config = conn.execute(
                    'SELECT telegram_token FROM "CONFIGURACION_SISTEMA" WHERE id = 1'
                ).fetchone()
                if config:
                    try:
                        token = config['telegram_token'] or ''
                    except Exception:
                        token = config[0] or ''
            except Exception as _e:
                print(f'[telegram rest] token CONFIGURACION_SISTEMA no disponible: {_e}')
        token = token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if not token:
            print('[telegram rest] sin token configurado')
            return
        resp = req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'},
            timeout=10
        )
        if resp.status_code >= 400:
            print(f'[telegram rest] error {resp.status_code}: {resp.text[:200]}')
    except Exception as _e:
        print(f'[telegram rest] envio fallido: {_e}')


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
    }
    key = (codigo or '').strip().lower()
    return labels.get(key, codigo or 'Pendiente por escoger')


def _telegram_detalle_entrega_restaurante(tipo_entrega, direccion, mesa):
    if tipo_entrega == 'domicilio':
        return f"Domicilio. Llevar a: {direccion or 'direccion pendiente'}"
    if tipo_entrega == 'recoger':
        return "Cliente recoge en el local."
    if tipo_entrega == 'mesa':
        return f"Consumo / entrega en mesa: {mesa or 'mesa sin nombre'}"
    return f"{tipo_entrega or 'Pedido'}: {direccion or mesa or 'N/A'}"


def _notificar_pedido_restaurante(conn, rest, pedido_id, cliente, telefono, tipo_entrega,
                                  direccion, mesa, items, total, metodo_pago=None):
    try:
        admin_id = rest['admin_id']
        nombre_rest = rest['nombre']
    except Exception:
        admin_id = dict(rest).get('admin_id') if rest else None
        nombre_rest = dict(rest).get('nombre', 'restaurante') if rest else 'restaurante'
    chat_id = None
    if admin_id:
        admin = conn.execute(
            "SELECT telegram_chat_id FROM terceros WHERE id = %s", (admin_id,)
        ).fetchone()
        chat_id = admin['telegram_chat_id'] if admin else None
    if not chat_id:
        try:
            config = conn.execute(
                'SELECT telegram_chat_id FROM "CONFIGURACION_SISTEMA" WHERE id = 1'
            ).fetchone()
            if config:
                chat_id = config['telegram_chat_id'] or None
        except Exception as _e:
            print(f'[telegram rest] chat global no disponible: {_e}')
    if not chat_id:
        print(f'[telegram rest] sin chat_id para restaurante {nombre_rest}')
        return
    items_txt = '\n'.join(f"  {item}" for item in items) or '  Pedido registrado'
    entrega = _telegram_detalle_entrega_restaurante(tipo_entrega, direccion, mesa)
    pago_txt = _telegram_label_pago(metodo_pago)
    if (metodo_pago or '').lower() == 'contraentrega':
        pago_txt += "\n⚠️ Contraentrega: cobrar efectivo al entregar."
    msg = (
        f"🍽️ <b>Nuevo pedido en {nombre_rest}</b>\n"
        f"🧾 Pedido #{pedido_id}\n"
        f"👤 {cliente or 'Cliente'} - {telefono or 'Sin telefono'}\n"
        f"📦 Entrega: {entrega}\n"
        f"💳 Pago elegido: {pago_txt}\n\n"
        f"{items_txt}\n\n"
        f"💰 Total: ${total:,.0f}"
    )
    _enviar_telegram(conn, chat_id, msg)


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
        cliente_url = f"https://{restaurante['slug']}.tuc-tuc.co"
        return render_template('restaurante_admin.html', restaurante=restaurante, restaurantes=None, cliente_url=cliente_url)
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
            cliente_url = f"https://{restaurante['slug']}.tuc-tuc.co"
            return render_template('restaurante_admin.html', restaurante=restaurante, restaurantes=None, es_dueno=True, cliente_url=cliente_url)
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
        # Tercero del dueño (persona)
        tercero = conn.execute(
            "SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (admin_telefono,)
        ).fetchone()
        if tercero:
            admin_id = tercero['id']
            conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (admin_nombre, admin_id))
        else:
            admin_id = conn.execute(
                "INSERT INTO terceros (nombre, telefono, tipo_tercero) VALUES (%s, %s, 'persona') RETURNING id",
                (admin_nombre, admin_telefono)
            ).fetchone()[0]
        # Tercero del negocio (entidad propia)
        negocio_tercero_id = conn.execute(
            "INSERT INTO terceros (nombre, tipo_tercero) VALUES (%s, 'negocio') RETURNING id",
            (nombre,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO restaurantes (nombre, slug, tipo_restaurante, admin_id, admin_nombre, admin_telefono, token_acceso, tercero_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (nombre, slug, tipo, admin_id, admin_nombre, admin_telefono, token, negocio_tercero_id)
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
        rest = conn.execute("SELECT id, tercero_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        opciones = conn.execute(
            "SELECT id, categoria AS tipo, nombre, recargo, precio, imagen, disponible AS activo, descripcion, orden "
            "FROM productos WHERE negocio_id = %s ORDER BY orden, id",
            (rest['tercero_id'],)
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
            conn.execute("UPDATE productos SET orden = %s WHERE id = %s AND negocio_id = %s",
                         (item['orden'], item['id'], rest['tercero_id']))
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
        rest = conn.execute("SELECT id, tercero_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        productos = conn.execute("""
            SELECT DISTINCT ON (LOWER(p.nombre), LOWER(p.categoria))
                p.nombre, p.categoria AS tipo, p.precio, p.recargo
            FROM productos p
            WHERE p.negocio_id != %s AND p.disponible = TRUE AND LOWER(p.nombre) LIKE %s
            ORDER BY LOWER(p.nombre), LOWER(p.categoria), p.id DESC LIMIT 15
        """, (rest['tercero_id'], f'%{q.lower()}%')).fetchall()
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
        rest = conn.execute("SELECT id, tercero_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        existente = conn.execute(
            "SELECT id FROM productos WHERE negocio_id = %s AND LOWER(nombre) = %s AND LOWER(categoria) = %s AND disponible = TRUE",
            (rest['tercero_id'], nombre.lower(), tipo.lower())
        ).fetchone()
        if existente:
            conn.close()
            return jsonify({'ok': False, 'error': f'{nombre} ya existe en tu catálogo'}), 400
        original = conn.execute(
            "SELECT nombre, categoria AS tipo, precio, recargo, imagen FROM productos "
            "WHERE LOWER(nombre) = %s AND LOWER(categoria) = %s AND disponible = TRUE ORDER BY id DESC LIMIT 1",
            (nombre.lower(), tipo.lower())
        ).fetchone()
        if not original:
            conn.close()
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        conn.execute(
            "INSERT INTO productos (negocio_id, categoria, nombre, precio, recargo, imagen) VALUES (%s,%s,%s,%s,%s,%s)",
            (rest['tercero_id'], original['tipo'], original['nombre'], original['precio'], original['recargo'], original['imagen'])
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
        rest = conn.execute("SELECT id, tipo_restaurante, tercero_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        if rest['tipo_restaurante'] == 'menu_dia' and tipo not in ('sopa', 'proteina', 'principio'):
            conn.close()
            return jsonify({'ok': False, 'error': 'Tipo debe ser sopa, proteina o principio'}), 400
        if opcion_id:
            conn.execute(
                "UPDATE productos SET categoria=%s, nombre=%s, recargo=%s, precio=%s, descripcion=%s "
                "WHERE id=%s AND negocio_id=%s",
                (tipo, nombre, recargo, precio, descripcion or None, opcion_id, rest['tercero_id'])
            )
        else:
            conn.execute(
                "INSERT INTO productos (negocio_id, categoria, nombre, recargo, precio, descripcion) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (rest['tercero_id'], tipo, nombre, recargo, precio, descripcion or None)
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
        rest = conn.execute("SELECT id, tercero_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        conn.execute("UPDATE productos SET disponible = FALSE WHERE id = %s AND negocio_id = %s",
                     (opcion_id, rest['tercero_id']))
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
        conn.execute("UPDATE productos SET imagen = %s WHERE id = %s AND negocio_id = %s",
                     (imagen, opcion_id, rest['tercero_id']))
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


@bp.route('/api/restaurante/<slug>/experiencia', methods=['POST'])
def api_restaurante_experiencia(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    pantalla = bool((request.get_json() or {}).get('pantalla_experiencial', False))
    conn = get_db_connection()
    try:
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT id, admin_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        if session.get('rol') != 'Administrador' and session.get('usuario_id') != rest['admin_id']:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        conn.execute("UPDATE restaurantes SET pantalla_experiencial = %s WHERE id = %s", (pantalla, rest['id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/restaurante/<slug>/experiencia-bloques', methods=['GET', 'PUT'])
def api_restaurante_experiencia_bloques(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT id, admin_id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        if session.get('rol') != 'Administrador' and session.get('usuario_id') != rest['admin_id']:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        if request.method == 'GET':
            return jsonify({'ok': True, 'bloques': _bloques_experiencia_restaurante(conn, rest['id'], activo=False)})

        data = request.get_json() or {}
        bloques = data.get('bloques') or []
        if not isinstance(bloques, list):
            return jsonify({'ok': False, 'error': 'Formato invalido'}), 400
        tipos_validos = {'video', 'collage', 'galeria', 'texto'}
        conn.execute("DELETE FROM restaurante_experiencia_bloques WHERE restaurante_id = %s", (rest['id'],))
        for idx, bloque in enumerate(bloques[:12]):
            if not isinstance(bloque, dict):
                continue
            tipo = (bloque.get('tipo') or 'texto').strip().lower()
            if tipo not in tipos_validos:
                tipo = 'texto'
            titulo = (bloque.get('titulo') or '').strip()[:180] or None
            texto = (bloque.get('texto') or '').strip()[:1200] or None
            activo = bool(bloque.get('activo', True))
            media = bloque.get('media') or []
            if not isinstance(media, list):
                media = []
            media = [str(m).strip() for m in media if str(m).strip()]
            if tipo == 'texto':
                media = []
            elif tipo == 'video':
                media = media[:3]
            else:
                media = media[:12]
            conn.execute("""
                INSERT INTO restaurante_experiencia_bloques
                    (restaurante_id, tipo, titulo, texto, media, activo, orden)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)
            """, (rest['id'], tipo, titulo, texto, json.dumps(media), activo, idx))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


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
        rest = conn.execute("""
            SELECT id, admin_id, tercero_id, token_acceso
            FROM restaurantes
            WHERE slug=%s AND activo=TRUE
        """, (slug,)).fetchone()
        token_ok = session.get('restaurante_token') and rest and session.get('restaurante_token') == rest['token_acceso']
        autorizado = (
            rest and (
                session.get('rol') == 'Administrador'
                or uid == rest['admin_id']
                or uid == rest['tercero_id']
                or token_ok
            )
        )
        if not autorizado:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin acceso'}), 403
        if not rest['tercero_id'] and rest['admin_id']:
            conn.execute("UPDATE restaurantes SET tercero_id=%s WHERE id=%s", (rest['admin_id'], rest['id']))
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
                   om.categoria AS tipo, om.nombre, om.recargo
            FROM menu_dia_opciones mdo
            JOIN productos om ON om.id = mdo.opcion_id
            WHERE mdo.menu_dia_id = %s ORDER BY om.categoria, om.nombre
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
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
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
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
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
    import sys
    if sys.stdout:
        print(f'[REST] /r/{slug} recibido', flush=True)
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return "Restaurante no encontrado", 404
        cliente_data = None
        tercero_id = session.get('chat_tercero_id')
        if tercero_id and session.get('rol') not in ('Administrador', 'ClienteVFP'):
            conn2 = get_db_connection()
            tercero = conn2.execute(
                "SELECT nombre, telefono, direccion FROM terceros WHERE id = %s", (tercero_id,)
            ).fetchone()
            conn2.close()
            if tercero:
                cliente_data = {'nombre': tercero['nombre'], 'telefono': tercero['telefono'] or '',
                                'direccion': tercero['direccion'] or '', 'cliente_id': tercero_id}
        solo_carta = bool(rest['solo_carta']) if rest['solo_carta'] is not None else False
        bloques_experiencia = _bloques_experiencia_restaurante(conn, rest['id']) if rest['pantalla_experiencial'] else []
        visita = registrar_visita_publica(
            conn,
            'restaurante',
            rest['id'],
            recurso_tipo='carta',
            titulo='Carta restaurante',
        )
        conn.close()
        response = make_response(render_template('restaurante_cliente.html', restaurante=rest, mesa_nombre='',
                                                 cliente_data=cliente_data, solo_carta=solo_carta,
                                                 bloques_experiencia=bloques_experiencia))
        return respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/r/<slug>/mesa/<mesa_nombre>')
def restaurante_cliente(slug, mesa_nombre):
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            conn.close()
            return "Restaurante no encontrado", 404
        mesa = conn.execute(
            "SELECT id, COALESCE(NULLIF(nombre, ''), numero::text) AS etiqueta FROM mesas_restaurante WHERE restaurante_id = %s AND (nombre = %s OR numero::text = %s) AND activo = TRUE",
            (rest['id'], mesa_nombre, mesa_nombre)
        ).fetchone()
        if not mesa:
            conn.close()
            return "Mesa no encontrada", 404
        solo_carta = bool(rest['solo_carta']) if rest['solo_carta'] is not None else False
        bloques_experiencia = _bloques_experiencia_restaurante(conn, rest['id']) if rest['pantalla_experiencial'] else []
        visita = registrar_visita_publica(
            conn,
            'restaurante',
            rest['id'],
            recurso_tipo='mesa',
            recurso_id=mesa['id'],
            titulo=f"Mesa {mesa['etiqueta']} - carta",
            detalle='Acceso desde QR o enlace de mesa',
        )
        conn.close()
        response = make_response(render_template('restaurante_cliente.html', restaurante=rest, mesa_nombre=mesa_nombre,
                                                 cliente_data=None, solo_carta=solo_carta,
                                                 bloques_experiencia=bloques_experiencia))
        return respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500


@bp.route('/promo/restaurante/<slug>/menu')
def promo_restaurante_menu(slug):
    conn = get_db_connection()
    try:
        _asegurar_experiencia_restaurante(conn)
        rest = conn.execute("SELECT * FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not rest:
            return "Restaurante no encontrado", 404
        solo_carta = bool(rest['solo_carta']) if rest['solo_carta'] is not None else False
        txt = request.args.get('txt', '')
        _asegurar_experiencia_restaurante(conn)
        bloques_experiencia = _bloques_experiencia_restaurante(conn, rest['id']) if rest['pantalla_experiencial'] else []
        visita = registrar_visita_publica(
            conn,
            'restaurante',
            rest['id'],
            recurso_tipo='menu_compartido',
            titulo=f"Menu compartido: {rest['nombre']}",
            detalle=txt or None,
        )
        response = make_response(render_template('restaurante_cliente.html', restaurante=rest, mesa_nombre='',
                                                 cliente_data=None, solo_carta=solo_carta,
                                                 bloques_experiencia=bloques_experiencia))
        return respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/promo/restaurante/<slug>/<int:opcion_id>/imagen')
def promo_restaurante_imagen(slug, opcion_id):
    conn = get_db_connection()
    try:
        rest = conn.execute(
            "SELECT tercero_id FROM restaurantes WHERE slug = %s AND activo = TRUE",
            (slug,)
        ).fetchone()
        if not rest:
            return '', 404
        opcion = conn.execute(
            "SELECT imagen FROM productos WHERE id = %s AND negocio_id = %s AND disponible = TRUE",
            (opcion_id, rest['tercero_id'])
        ).fetchone()
        if not opcion or not opcion['imagen']:
            return '', 404
        return redirect(opcion['imagen'])
    except Exception:
        return '', 500
    finally:
        conn.close()


@bp.route('/promo/restaurante/<slug>/<int:opcion_id>')
def promo_restaurante_opcion(slug, opcion_id):
    conn = get_db_connection()
    try:
        rest = conn.execute(
            "SELECT id, nombre, slug, tercero_id, imagen_header FROM restaurantes WHERE slug = %s AND activo = TRUE",
            (slug,)
        ).fetchone()
        if not rest:
            return "Restaurante no encontrado", 404
        opcion = conn.execute(
            "SELECT id, nombre, descripcion, precio, imagen FROM productos WHERE id = %s AND negocio_id = %s AND disponible = TRUE",
            (opcion_id, rest['tercero_id'])
        ).fetchone()
        if not opcion:
            return "Producto no disponible", 404
        tiene_imagen = bool(opcion['imagen'])
        mostrar_foto = request.args.get('foto', '1') != '0'
        mostrar_precio = request.args.get('precio', '1') != '0'
        mostrar_desc = request.args.get('desc', '1') != '0'
        txt = request.args.get('txt', '')
        leyenda = request.args.get('leyenda', '¿A quién le llevamos?')
        visita = registrar_visita_publica(
            conn,
            'restaurante',
            rest['id'],
            recurso_tipo='producto_compartido',
            recurso_id=opcion['id'],
            titulo=f"Producto restaurante compartido: {opcion['nombre']}",
            detalle=txt or None,
        )
        response = make_response(render_template(
            'promo_restaurante.html',
            restaurante=rest,
            opcion=opcion,
            tiene_imagen=tiene_imagen,
            mostrar_foto=mostrar_foto,
            mostrar_precio=mostrar_precio,
            mostrar_desc=mostrar_desc,
            txt=txt,
            leyenda=leyenda,
        ))
        return respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


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
        metodo_pago = (data.get('metodo_pago') or '').strip() or None
        cliente_lat = data.get('cliente_lat')
        cliente_lon = data.get('cliente_lon')
        conn = get_db_connection()
        _crear_tablas(conn)
        _asegurar_domicilio_restaurante(conn)
        rest = conn.execute(
            "SELECT id, nombre, tipo_restaurante, dias_pagados, tercero_id, admin_id FROM restaurantes WHERE slug = %s",
            (slug,)
        ).fetchone()
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
        items_notificacion = []
        es_carta = rest['tipo_restaurante'] == 'carta' or (rest['tipo_restaurante'] == 'ambos' and data.get('platos'))
        valor_domicilio = 0.0
        domicilio_estado = 'no_aplica'

        if es_carta:
            platos = data.get('platos', [])
            if not platos:
                conn.close()
                return jsonify({'ok': False, 'error': 'Selecciona al menos un plato'}), 400
            insertados = 0
            pedidos_insertados = []
            for p in platos:
                opcion = conn.execute(
                    "SELECT id, nombre, precio FROM productos WHERE id=%s AND negocio_id=%s AND disponible=TRUE",
                    (p['plato_id'], rest['tercero_id'])
                ).fetchone()
                if not opcion:
                    continue
                cant = p.get('cantidad', 1)
                precio_item = float(opcion['precio']) * cant
                precio_total += precio_item
                items_notificacion.append(f"{cant}x {opcion['nombre']} - ${precio_item:,.0f}")
                nota_item = p.get('nota', '').strip() or None
                conn.execute("""
                    INSERT INTO pedidos_restaurante
                    (restaurante_id, mesa_num, mesa_nombre, tipo, plato_id, cantidad, precio, notas, nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id, metodo_pago, subtotal_productos, cliente_lat, cliente_lon)
                    VALUES (%s, 0, %s, 'carta', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (rest['id'], mesa_nombre, opcion['id'], cant, precio_item, nota_item,
                      nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id, metodo_pago,
                      precio_item, cliente_lat, cliente_lon))
                pedidos_insertados.append(conn.execute(
                    "SELECT currval(pg_get_serial_sequence('pedidos_restaurante','id'))"
                ).fetchone()[0])
                if rest['tercero_id']:
                    try:
                        conn.execute("SAVEPOINT sp_inv")
                        _aplicar_tarjeta(
                            conn, rest['tercero_id'],
                            producto_id=opcion['id'],
                            cantidad=cant,
                            tipo='salida',
                            motivo='venta',
                            registrado_por=session.get('usuario_id'),
                            referencia_tipo='pedido_restaurante',
                        )
                        conn.execute("RELEASE SAVEPOINT sp_inv")
                    except Exception as _e:
                        print(f'[inv] salida carta {opcion["id"]}: {_e}')
                        try: conn.execute("ROLLBACK TO SAVEPOINT sp_inv")
                        except: pass
                insertados += 1
            if insertados == 0:
                conn.close()
                return jsonify({'ok': False, 'error': 'Platos no encontrados en el menú'}), 400
            pedido_id = conn.execute(
                "SELECT currval(pg_get_serial_sequence('pedidos_restaurante','id'))"
            ).fetchone()[0]
            tercero_config_id = rest['tercero_id'] or rest['admin_id']
            valor_domicilio, domicilio_estado = _calcular_domicilio(
                conn, tercero_config_id, tipo_entrega, cliente_lat, cliente_lon
            )
            if domicilio_estado == 'fuera_cobertura':
                conn.close()
                return jsonify({'ok': False, 'error': 'La direccion esta fuera de cobertura de domicilio'}), 400
            if pedidos_insertados:
                conn.execute("""
                    UPDATE pedidos_restaurante
                    SET valor_domicilio=%s, domicilio_estado=%s
                    WHERE id=%s
                """, (float(valor_domicilio or 0), domicilio_estado, pedidos_insertados[-1]))
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
                recargo = conn.execute("SELECT recargo FROM productos WHERE id = %s", (proteina_id,)).fetchone()
                if recargo and recargo['recargo']:
                    precio_total += float(recargo['recargo'])
            items_notificacion.append(f"Menu {tipo} - ${precio_total:,.0f}")
            tercero_config_id = rest['tercero_id'] or rest['admin_id']
            valor_domicilio, domicilio_estado = _calcular_domicilio(
                conn, tercero_config_id, tipo_entrega, cliente_lat, cliente_lon
            )
            if domicilio_estado == 'fuera_cobertura':
                conn.close()
                return jsonify({'ok': False, 'error': 'La direccion esta fuera de cobertura de domicilio'}), 400
            for etiqueta, prod_id in (('Sopa', sopa_id), ('Proteina', proteina_id), ('Principio', principio_id)):
                if prod_id:
                    prod = conn.execute("SELECT nombre FROM productos WHERE id = %s", (prod_id,)).fetchone()
                    if prod:
                        items_notificacion.append(f"{etiqueta}: {prod['nombre']}")
            conn.execute("""
                INSERT INTO pedidos_restaurante
                (restaurante_id, mesa_num, mesa_nombre, tipo, sopa_id, proteina_id, principio_id, precio, notas, nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id, metodo_pago, subtotal_productos, valor_domicilio, domicilio_estado, cliente_lat, cliente_lon)
                VALUES (%s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (rest['id'], mesa_nombre, tipo, sopa_id, proteina_id, principio_id, precio_total,
                  notas or None, nombre_cliente, tipo_entrega, telefono_cliente, direccion_cliente, cliente_id, metodo_pago,
                  precio_total, float(valor_domicilio or 0), domicilio_estado, cliente_lat, cliente_lon))
            pedido_id = conn.execute(
                "SELECT currval(pg_get_serial_sequence('pedidos_restaurante','id'))"
            ).fetchone()[0]
            if rest['tercero_id']:
                for prod_id in filter(None, [sopa_id, proteina_id, principio_id]):
                    try:
                        conn.execute("SAVEPOINT sp_inv")
                        _aplicar_tarjeta(
                            conn, rest['tercero_id'],
                            producto_id=prod_id,
                            cantidad=1,
                            tipo='salida',
                            motivo='venta',
                            registrado_por=session.get('usuario_id'),
                            referencia_tipo='pedido_restaurante',
                        )
                        conn.execute("RELEASE SAVEPOINT sp_inv")
                    except Exception as _e:
                        print(f'[inv] salida menu {prod_id}: {_e}')
                        try: conn.execute("ROLLBACK TO SAVEPOINT sp_inv")
                        except: pass

        if rest['tercero_id'] and _asiento_auto:
            try:
                _asiento_auto(conn, rest['tercero_id'], 'VENTA',
                              {'subtotal_venta': precio_total,
                               'iva_venta': 0,
                               'total_venta': precio_total},
                              registrado_por=session.get('usuario_id'))
            except Exception as _e:
                print(f'[cont] venta rest {slug}: {_e}')
        conn.commit()
        try:
            _notificar_pedido_restaurante(
                conn, rest, pedido_id, nombre_cliente, telefono_cliente, tipo_entrega,
                direccion_cliente, mesa_nombre, items_notificacion, precio_total + float(valor_domicilio or 0), metodo_pago
            )
        except Exception as _e:
            print(f'[telegram] pedido rest {slug}: {_e}')
        conn.close()
        return jsonify({'ok': True, 'precio': precio_total, 'pedido_id': pedido_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/restaurante/<slug>/pedido/<int:pedido_id>/comprobante', methods=['POST'])
def api_restaurante_pedido_comprobante(slug, pedido_id):
    data = request.get_json() or {}
    imagen = (data.get('imagen') or '').strip()
    if not imagen:
        return jsonify({'ok': False, 'error': 'Sin imagen'}), 400
    conn = get_db_connection()
    try:
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug=%s", (slug,)).fetchone()
        if not rest:
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        cur = conn.execute(
            "UPDATE pedidos_restaurante SET comprobante_pago=%s WHERE id=%s AND restaurante_id=%s",
            (imagen, pedido_id, rest['id'])
        )
        if cur.rowcount == 0:
            return jsonify({'ok': False, 'error': 'Pedido no encontrado'}), 404
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/restaurante/<slug>/pedidos')
def api_pedidos(slug):
    estado = request.args.get('estado', 'pendiente,listo')
    estados = [e.strip() for e in estado.split(',')]
    try:
        conn = get_db_connection()
        _crear_tablas(conn)
        _asegurar_pagos_restaurante(conn)
        _asegurar_domicilio_restaurante(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        placeholders = ','.join(['%s'] * len(estados))
        pedidos = conn.execute(f"""
            SELECT p.id, p.mesa_num, p.mesa_nombre, p.tipo, p.precio, p.estado, p.notas, p.nombre_cliente, p.created_at,
                   p.cantidad, p.tipo_entrega, p.telefono_cliente, p.direccion_cliente, p.cliente_id,
                   p.metodo_pago, p.comprobante_pago, p.valor_domicilio, p.domicilio_estado,
                   s.nombre as sopa_nombre, pr.nombre as proteina_nombre, pr.recargo as proteina_recargo,
                   pi.nombre as principio_nombre, pl.nombre as plato_nombre
            FROM pedidos_restaurante p
            LEFT JOIN productos s ON s.id = p.sopa_id
            LEFT JOIN productos pr ON pr.id = p.proteina_id
            LEFT JOIN productos pi ON pi.id = p.principio_id
            LEFT JOIN productos pl ON pl.id = p.plato_id
            WHERE p.restaurante_id = %s AND p.estado IN ({placeholders})
            AND p.created_at::date = CURRENT_DATE
            ORDER BY p.created_at DESC
        """, (rest['id'], *estados)).fetchall()
        resultado = []
        for p in pedidos:
            pagos = conn.execute("""
                SELECT metodo_codigo, metodo_nombre, monto
                FROM pedido_pagos_restaurante
                WHERE pedido_id = %s
                ORDER BY id
            """, (p['id'],)).fetchall()
            pagos_json = [{
                'codigo': pago['metodo_codigo'] or '',
                'nombre': pago['metodo_nombre'] or pago['metodo_codigo'] or '',
                'monto': float(pago['monto'] or 0),
            } for pago in pagos]
            if not pagos_json:
                pagos_json = [{
                    'codigo': p['metodo_pago'] or 'efectivo',
                    'nombre': p['metodo_pago'] or 'efectivo',
                    'monto': float(p['precio'] or 0) * float(p['cantidad'] or 1),
                }]
            resultado.append({
                'id': p['id'], 'mesa_num': p['mesa_num'], 'mesa_nombre': p['mesa_nombre'] or '',
                'tipo': p['tipo'], 'precio': float(p['precio']), 'estado': p['estado'],
                'notas': p['notas'], 'sopa': p['sopa_nombre'], 'proteina': p['proteina_nombre'],
                'proteina_recargo': float(p['proteina_recargo']) if p['proteina_recargo'] else 0,
                'principio': p['principio_nombre'], 'plato': p['plato_nombre'],
                'cantidad': p['cantidad'] or 1, 'nombre_cliente': p['nombre_cliente'],
                'tipo_entrega': p['tipo_entrega'] or 'mesa', 'telefono_cliente': p['telefono_cliente'],
                'direccion_cliente': p['direccion_cliente'], 'cliente_id': p['cliente_id'],
                'metodo_pago': p['metodo_pago'] or 'efectivo',
                'comprobante_pago': p['comprobante_pago'] or '',
                'valor_domicilio': float(p['valor_domicilio'] or 0),
                'domicilio_estado': p['domicilio_estado'] or 'no_aplica',
                'pagos': pagos_json,
                'created_at': p['created_at'].strftime('%H:%M') if p['created_at'] else ''
            })
        conn.close()
        return jsonify({'ok': True, 'pedidos': resultado})
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


def cobrar_mesa_page(slug, mesa_id):
    conn = get_db_connection()
    try:
        rest = conn.execute(
            "SELECT id, nombre, slug, tercero_id FROM restaurantes WHERE slug=%s AND activo=TRUE", (slug,)
        ).fetchone()
        if not rest:
            return "Restaurante no encontrado", 404
        row = conn.execute("""
            SELECT COALESCE(SUM(precio), 0) AS total
            FROM pedidos_restaurante
            WHERE restaurante_id=%s
            AND (mesa_nombre=%s OR (COALESCE(mesa_nombre,'')='' AND mesa_num::text=%s))
            AND estado != 'cobrado' AND created_at::date = CURRENT_DATE
        """, (rest['id'], mesa_id, mesa_id)).fetchone()
        total = float(row['total'] or 0)
        mesa_label = 'En línea' if str(mesa_id) == '0' else f'Mesa {mesa_id}'
        return render_template('pagar.html',
                               tipo='mesa',
                               tercero_id=rest['tercero_id'],
                               negocio_nombre=rest['nombre'],
                               negocio_slug=slug,
                               total=total,
                               mesa_label=mesa_label,
                               api_url=f'/api/restaurante/{slug}/cobrar/{mesa_id}',
                               volver_url=f'https://{slug}.tuc-tuc.co/mesero',
                               volver_texto='Volver al mesero')
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/api/restaurante/<slug>/cobrar/<mesa_id>', methods=['POST'])
def api_cobrar(slug, mesa_id):
    data = request.get_json() or {}
    pagos = data.get('pagos') or []
    metodo_pago = (pagos[0].get('codigo') if pagos and isinstance(pagos[0], dict) else None) or (data.get('metodo_pago') or '').strip() or None
    try:
        conn = get_db_connection()
        _asegurar_pagos_restaurante(conn)
        rest = conn.execute("SELECT id FROM restaurantes WHERE slug = %s", (slug,)).fetchone()
        if not rest:
            conn.close()
            return jsonify({'ok': False, 'error': 'No encontrado'}), 404
        pedidos = conn.execute("""
            SELECT id, precio, COALESCE(cantidad, 1) AS cantidad
            FROM pedidos_restaurante
            WHERE restaurante_id = %s
            AND (mesa_nombre = %s OR (COALESCE(mesa_nombre,'') = '' AND mesa_num::text = %s))
            AND estado != 'cobrado' AND created_at::date = CURRENT_DATE
        """, (rest['id'], mesa_id, mesa_id)).fetchall()
        conn.execute("""
            UPDATE pedidos_restaurante
            SET estado = 'cobrado', metodo_pago = COALESCE(%s, metodo_pago)
            WHERE restaurante_id = %s
            AND (mesa_nombre = %s OR (COALESCE(mesa_nombre,'') = '' AND mesa_num::text = %s))
            AND estado != 'cobrado' AND created_at::date = CURRENT_DATE
        """, (metodo_pago, rest['id'], mesa_id, mesa_id))
        pagos_validos = [p for p in pagos if isinstance(p, dict) and float(p.get('monto') or 0) > 0]
        total_mesa = sum(float(p['precio'] or 0) * float(p['cantidad'] or 1) for p in pedidos)
        for pedido in pedidos:
            pedido_total = float(pedido['precio'] or 0) * float(pedido['cantidad'] or 1)
            proporcion = (pedido_total / total_mesa) if total_mesa else 1
            conn.execute("DELETE FROM pedido_pagos_restaurante WHERE pedido_id=%s", (pedido['id'],))
            if pagos_validos:
                for pago in pagos_validos:
                    conn.execute("""
                        INSERT INTO pedido_pagos_restaurante (pedido_id, metodo_codigo, metodo_nombre, monto)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        pedido['id'],
                        pago.get('codigo') or metodo_pago,
                        pago.get('nombre') or pago.get('codigo') or metodo_pago,
                        float(pago.get('monto') or 0) * proporcion,
                    ))
            elif metodo_pago:
                conn.execute("""
                    INSERT INTO pedido_pagos_restaurante (pedido_id, metodo_codigo, metodo_nombre, monto)
                    VALUES (%s, %s, %s, %s)
                """, (pedido['id'], metodo_pago, metodo_pago, pedido_total))
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
            LEFT JOIN productos s ON s.id = p.sopa_id
            LEFT JOIN productos pr ON pr.id = p.proteina_id
            LEFT JOIN productos pi ON pi.id = p.principio_id
            LEFT JOIN productos pl ON pl.id = p.plato_id
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

@bp.route('/api/restaurante/<slug>/visitas-publicas')
def api_restaurante_visitas_publicas(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        rest = conn.execute(
            "SELECT id, admin_id FROM restaurantes WHERE slug = %s AND activo = TRUE",
            (slug,)
        ).fetchone()
        if not rest:
            return jsonify({'ok': False, 'error': 'Restaurante no encontrado'}), 404
        if session.get('rol') != 'Administrador' and session.get('usuario_id') != rest['admin_id']:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        visitantes, visitas = listar_visitas_publicas(conn, 'restaurante', rest['id'])
        return jsonify({
            'ok': True,
            'zona_horaria': 'America/Bogota',
            'visitantes': visitantes,
            'visitas': visitas,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/docs/restaurante')
@bp.route('/admin/docs/restaurante')
def docs_restaurante():
    return render_template('docs_restaurante.html')
