import base64
import itertools
import json
import random
import secrets
import time
import uuid
from datetime import date, timedelta

from flask import (Blueprint, Response, jsonify, redirect, render_template,
                   request, session)

from ..db import get_db_connection
from .auth import solo_admin
from .inventarios import _aplicar_tarjeta, _es_ensamble
try:
    from .contabilidad import _ejecutar_asiento_automatico as _asiento_auto
except ImportError:
    _asiento_auto = None

bp = Blueprint('tiendas', __name__)

_tablas_listas = False
_sesiones_caja_cliente = {}
_SESION_CAJA_TTL = 60 * 60 * 4


def _limpiar_sesiones_caja():
    ahora = time.time()
    expiradas = [
        token for token, sesion in _sesiones_caja_cliente.items()
        if ahora - sesion.get('updated_at', sesion.get('created_at', ahora)) > _SESION_CAJA_TTL
    ]
    for token in expiradas:
        _sesiones_caja_cliente.pop(token, None)


def _crear_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return
    sqls = [
        """CREATE TABLE IF NOT EXISTS tiendas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            admin_id INTEGER,
            admin_nombre VARCHAR(255),
            admin_telefono VARCHAR(20),
            token_acceso VARCHAR(100) UNIQUE,
            dias_pagados INTEGER DEFAULT 0,
            imagen_header TEXT,
            imagen_header_movil TEXT,
            tema VARCHAR(10) DEFAULT 'claro',
            mostrar_nombre BOOLEAN DEFAULT TRUE,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS pedidos_tienda (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            cliente_id INTEGER,
            nombre_cliente VARCHAR(100),
            telefono_cliente VARCHAR(20),
            direccion_cliente TEXT,
            tipo_entrega VARCHAR(20) DEFAULT 'domicilio',
            estado VARCHAR(20) DEFAULT 'nuevo',
            total DECIMAL(10,2) DEFAULT 0,
            notas TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS items_pedido_tienda (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            nombre_producto VARCHAR(255),
            cantidad INTEGER DEFAULT 1,
            precio_unitario DECIMAL(10,2) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS producto_atributos (
            id SERIAL PRIMARY KEY,
            producto_id INTEGER NOT NULL,
            nombre VARCHAR(50) NOT NULL,
            orden INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS atributo_valores (
            id SERIAL PRIMARY KEY,
            atributo_id INTEGER NOT NULL,
            valor VARCHAR(100) NOT NULL,
            orden INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS producto_variantes (
            id SERIAL PRIMARY KEY,
            producto_id INTEGER NOT NULL,
            atributos JSONB NOT NULL,
            precio DECIMAL(10,2) NOT NULL,
            disponible BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS producto_imagenes (
            id SERIAL PRIMARY KEY,
            producto_id INTEGER NOT NULL,
            imagen TEXT NOT NULL,
            orden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS producto_documentos (
            id SERIAL PRIMARY KEY,
            producto_id INTEGER NOT NULL,
            tipo VARCHAR(40) DEFAULT 'ficha_tecnica',
            nombre VARCHAR(255) NOT NULL,
            mime VARCHAR(120) DEFAULT 'application/pdf',
            archivo TEXT NOT NULL,
            visible_cliente BOOLEAN DEFAULT TRUE,
            orden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS catalogo_productos (
            id SERIAL PRIMARY KEY,
            codigo_barra VARCHAR(50) UNIQUE,
            nombre VARCHAR(255) NOT NULL,
            descripcion TEXT,
            imagen TEXT,
            categoria VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS tienda_cajeros (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            nombre VARCHAR(100) NOT NULL,
            pin VARCHAR(10) NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS tienda_vendedores (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            vendedor_id INTEGER NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(tienda_id, vendedor_id)
        )""",
        """CREATE TABLE IF NOT EXISTS metodos_pago_catalogo (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            codigo VARCHAR(50) NOT NULL UNIQUE,
            icono VARCHAR(10) DEFAULT '💳',
            activo BOOLEAN DEFAULT TRUE,
            orden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS metodos_pago_tienda (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            catalogo_id INTEGER,
            nombre VARCHAR(100),
            codigo VARCHAR(50),
            activo BOOLEAN DEFAULT TRUE,
            orden INTEGER DEFAULT 0,
            UNIQUE(tienda_id, catalogo_id)
        )""",
        """CREATE TABLE IF NOT EXISTS pedido_pagos_tienda (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL,
            metodo_codigo VARCHAR(50),
            metodo_nombre VARCHAR(100),
            monto NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS tienda_categorias (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            categoria VARCHAR(100) NOT NULL,
            imagen TEXT,
            orden INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(tienda_id, categoria)
        )""",
        """CREATE TABLE IF NOT EXISTS cotizaciones_tienda (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            cliente_id INTEGER REFERENCES terceros(id),
            cliente_nombre VARCHAR(255),
            cliente_telefono VARCHAR(30),
            cliente_email VARCHAR(120),
            ubicacion VARCHAR(255),
            factor_generacion NUMERIC(6,2),
            consumo_mensual NUMERIC(12,2),
            objetivo VARCHAR(80),
            consumos_json JSONB DEFAULT '[]'::jsonb,
            datos_tecnicos JSONB DEFAULT '{}'::jsonb,
            notas TEXT,
            estado VARCHAR(30) DEFAULT 'borrador',
            subtotal NUMERIC(14,2) DEFAULT 0,
            total NUMERIC(14,2) DEFAULT 0,
            token_publico VARCHAR(80) UNIQUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS cotizacion_items_tienda (
            id SERIAL PRIMARY KEY,
            cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones_tienda(id) ON DELETE CASCADE,
            producto_id INTEGER REFERENCES productos(id),
            nombre VARCHAR(255) NOT NULL,
            categoria VARCHAR(100),
            cantidad NUMERIC(12,3) NOT NULL DEFAULT 1,
            precio_unitario NUMERIC(14,2) NOT NULL DEFAULT 0,
            total NUMERIC(14,2) NOT NULL DEFAULT 0,
            notas TEXT,
            orden INTEGER DEFAULT 0
        )""",
    ]
    for sql in sqls:
        conn.execute(sql)
    conn.commit()

    alters = [
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS fecha_vence DATE",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS pin_caja VARCHAR(10)",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS color_primario VARCHAR(20) DEFAULT '#f59e0b'",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS descripcion TEXT",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS lat NUMERIC(10,7)",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS lon NUMERIC(10,7)",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id)",
        "ALTER TABLE pedidos_tienda ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20) DEFAULT 'efectivo'",
        "ALTER TABLE pedidos_tienda ADD COLUMN IF NOT EXISTS id_cajero INTEGER",
        "ALTER TABLE pedidos_tienda ADD COLUMN IF NOT EXISTS nombre_cajero VARCHAR(100)",
        "ALTER TABLE pedidos_tienda ADD COLUMN IF NOT EXISTS id_tercero_cajero INTEGER REFERENCES terceros(id)",
        "ALTER TABLE tienda_cajeros ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id)",
        "CREATE INDEX IF NOT EXISTS idx_catalogo_productos_codigo ON catalogo_productos(codigo_barra)",
        "CREATE INDEX IF NOT EXISTS idx_tienda_cajeros_tienda ON tienda_cajeros(tienda_id)",
        "ALTER TABLE metodos_pago_tienda ALTER COLUMN nombre DROP NOT NULL",
        "ALTER TABLE metodos_pago_tienda ALTER COLUMN codigo DROP NOT NULL",
        "UPDATE tiendas SET tercero_id = admin_id WHERE tercero_id IS NULL AND admin_id IS NOT NULL",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS desktop_layout VARCHAR(20) DEFAULT 'movil'",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS movil_cols SMALLINT DEFAULT 2",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS pantalla_experiencial BOOLEAN DEFAULT FALSE",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS color_accion VARCHAR(20) DEFAULT '#e11d48'",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS imagen_header_movil TEXT",
        "CREATE INDEX IF NOT EXISTS idx_cotizaciones_tienda ON cotizaciones_tienda(tienda_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_cot_items_cotizacion ON cotizacion_items_tienda(cotizacion_id)",
        "CREATE INDEX IF NOT EXISTS idx_producto_documentos_producto ON producto_documentos(producto_id)",
        "ALTER TABLE metodos_pago_catalogo ADD COLUMN IF NOT EXISTS grupo VARCHAR(30)",
        "ALTER TABLE pedidos_tienda ADD COLUMN IF NOT EXISTS comprobante_pago TEXT",
        "INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo) VALUES ('Nequi QR', 'nequi_qr', '📲', 21, 'nequi') ON CONFLICT (codigo) DO NOTHING",
        "INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo) VALUES ('Nequi Celular', 'nequi_movil', '📱', 22, 'nequi') ON CONFLICT (codigo) DO NOTHING",
        "UPDATE metodos_pago_catalogo SET grupo = 'nequi' WHERE codigo = 'nequi' AND grupo IS NULL",
        "UPDATE metodos_pago_catalogo SET activo = FALSE WHERE codigo = 'nequi'",
        """UPDATE config_negocio SET metodos_pago = array_replace(metodos_pago, 'nequi', 'nequi_movil') WHERE 'nequi' = ANY(metodos_pago)""",
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

    _seed_metodos_pago_catalogo(conn)
    _tablas_listas = True


def _seed_metodos_pago_catalogo(conn):
    existe = conn.execute("SELECT COUNT(*) as n FROM metodos_pago_catalogo").fetchone()['n']
    if existe:
        return
    metodos = [
        ('Efectivo',        'efectivo',       '💵', 1),
        ('Nequi',           'nequi',          '📱', 2),
        ('Bancolombia',     'bancolombia',     '🏦', 3),
        ('Daviplata',       'daviplata',       '📲', 4),
        ('Tarjeta débito',  'tarjeta_debito',  '💳', 5),
        ('Tarjeta crédito', 'tarjeta_credito', '💳', 6),
        ('Transferencia',   'transferencia',   '🔄', 7),
        ('Contraentrega',   'contraentrega',   '📦', 8),
    ]
    for nombre, codigo, icono, orden in metodos:
        conn.execute("""
            INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden)
            VALUES (%s, %s, %s, %s) ON CONFLICT (codigo) DO NOTHING
        """, (nombre, codigo, icono, orden))
    conn.commit()


def _generar_slug(nombre):
    import unicodedata
    import re
    s = unicodedata.normalize('NFD', nombre.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def _enviar_telegram_tienda(conn, chat_id, texto):
    try:
        import requests as req
        config = conn.execute(
            "SELECT telegram_token FROM configuracion_sistema WHERE id = 1"
        ).fetchone()
        if config and config[0]:
            req.post(
                f"https://api.telegram.org/bot{config[0]}/sendMessage",
                json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'},
                timeout=10
            )
    except Exception:
        pass


def _registrar_negocio_en_pois(conn, nombre, lat, lon, uid):
    try:
        existente = conn.execute(
            "SELECT id FROM pois_cali WHERE origen='tuctuc' AND sugerido_por=%s AND ABS(lat-%s)<0.0003 AND ABS(lon-%s)<0.0003",
            (uid, lat, lon)
        ).fetchone()
        if existente:
            conn.execute(
                "UPDATE pois_cali SET nombre=%s, lat=%s, lon=%s WHERE id=%s",
                (nombre, lat, lon, existente['id'])
            )
        else:
            conn.execute(
                "INSERT INTO pois_cali (nombre, lat, lon, categoria, origen, sugerido_por) VALUES (%s,%s,%s,'tienda','tuctuc',%s)",
                (nombre, lat, lon, uid)
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        lu = conn.execute(
            "SELECT id FROM lugares_usuario WHERE usuario_id=%s AND ABS(lat-%s)<0.0003 AND ABS(lon-%s)<0.0003",
            (uid, lat, lon)
        ).fetchone()
        if lu:
            conn.execute("UPDATE lugares_usuario SET nombre=%s, lat=%s, lon=%s WHERE id=%s", (nombre, lat, lon, lu['id']))
        else:
            conn.execute(
                "INSERT INTO lugares_usuario (usuario_id, nombre, lat, lon, icono, es_sugerido_publico) VALUES (%s,%s,%s,%s,'🏪',TRUE)",
                (uid, nombre, lat, lon)
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


# ── Páginas admin HTML ─────────────────────────────────────────────────────────

@bp.route('/admin/tienda')
def admin_tienda_lista():
    if 'usuario_id' not in session:
        return redirect('/login')
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tiendas_raw = conn.execute(
            "SELECT id, nombre, slug, admin_nombre, admin_telefono, token_acceso, dias_pagados FROM tiendas WHERE activo = TRUE ORDER BY nombre"
        ).fetchall()
        tiendas = []
        for t in tiendas_raw:
            dias_usados = conn.execute(
                "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos_tienda WHERE tienda_id = %s",
                (t['id'],)
            ).fetchone()['dias']
            t_dict = dict(t)
            t_dict['dias_usados'] = dias_usados
            t_dict['dias_restantes'] = max(0, (t['dias_pagados'] or 0) - dias_usados)
            tiendas.append(t_dict)
        return render_template('tienda_admin.html', tiendas=tiendas, tienda=None)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/admin/tienda/<slug>')
def admin_tienda_detalle(slug):
    if 'usuario_id' not in session:
        return redirect('/login')
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT * FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return redirect('/admin/tienda')
        return render_template('tienda_admin.html', tienda=tienda, tiendas=None)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/admin/tienda/<slug>/metodos-pago')
def admin_tienda_metodos_pago(slug):
    if 'usuario_id' not in session:
        return redirect('/login')
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id, nombre, slug FROM tiendas WHERE slug=%s AND activo=TRUE", (slug,)).fetchone()
        if not tienda:
            return redirect('/admin/tienda')
        metodos = conn.execute(
            "SELECT * FROM metodos_pago_tienda WHERE tienda_id=%s ORDER BY orden, id", (tienda['id'],)
        ).fetchall()
        return render_template('tienda_metodos_pago.html', tienda=tienda, metodos=metodos)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


# ── Token magic link ───────────────────────────────────────────────────────────

@bp.route('/t/acceso/<token>')
def tienda_acceso_token(token):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT * FROM tiendas WHERE token_acceso = %s AND activo = TRUE", (token,)
        ).fetchone()
        if not tienda:
            return "Enlace invalido o expirado", 404
        tercero = conn.execute(
            "SELECT id, nombre, telefono FROM terceros WHERE id = %s", (tienda['admin_id'],)
        ).fetchone()
        if not tercero:
            return "Usuario no encontrado", 404
        session['usuario_id'] = tercero['id']
        session['nombre']     = tercero['nombre']
        session['telefono']   = tercero['telefono'] or ''
        session['rol']        = 'Tienda'
        session.permanent     = True
        session.modified      = True
        return redirect(f"/mi-tienda/{tienda['slug']}")
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/mi-tienda/<slug>')
def mi_tienda(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT * FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return "Tienda no encontrada", 404
        usuario_id      = session.get('usuario_id')
        es_admin_sistema = session.get('rol') == 'Administrador'
        if usuario_id and (es_admin_sistema or usuario_id == tienda['admin_id']):
            return render_template('tienda_admin.html', tienda=tienda, tiendas=None, es_dueno=True)
        return render_template('tienda_recuperar.html', tienda=tienda)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


# ── Vista pública ──────────────────────────────────────────────────────────────

@bp.route('/t/<slug>')
def tienda_publica(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT * FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return "Tienda no encontrada", 404
        cliente_data = None
        if session.get('usuario_id'):
            conn2 = get_db_connection()
            try:
                tercero = conn2.execute(
                    "SELECT nombre, telefono, direccion FROM terceros WHERE id = %s", (session['usuario_id'],)
                ).fetchone()
                if tercero:
                    cliente_data = {
                        'nombre': tercero['nombre'],
                        'telefono': tercero['telefono'] or '',
                        'direccion': tercero['direccion'] or '',
                        'cliente_id': session['usuario_id']
                    }
            finally:
                conn2.close()
        return render_template('tienda_cliente.html', tienda=tienda, cliente_data=cliente_data)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


# ── Caja POS ───────────────────────────────────────────────────────────────────

@bp.route('/tienda/<slug>/caja')
def tienda_caja(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT id, nombre, imagen_header, color_primario, tercero_id FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return "Tienda no encontrada", 404
        return render_template('tienda_caja.html', tienda=tienda, slug=slug)
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()


# ── Promo páginas ──────────────────────────────────────────────────────────────

@bp.route('/admin/tienda/<slug>/caja')
@solo_admin
def admin_tienda_caja(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT id, nombre, imagen_header, color_primario, tercero_id FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return "Tienda no encontrada", 404
        return render_template('tienda_caja.html', tienda=tienda, slug=slug, modo_admin=True)
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()


@bp.route('/tienda/<slug>/caja/cliente/<token>')
def tienda_caja_cliente(slug, token):
    conn = get_db_connection()
    try:
        tienda = conn.execute(
            "SELECT id, nombre, imagen_header FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return "Tienda no encontrada", 404
        return render_template('tienda_caja_cliente.html', tienda=tienda, slug=slug, token=token)
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/caja/sesion', methods=['POST'])
def api_tienda_caja_sesion_crear(slug):
    _limpiar_sesiones_caja()
    conn = get_db_connection()
    try:
        tienda = conn.execute(
            "SELECT id, nombre FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404

        token = secrets.token_urlsafe(18)
        update_key = secrets.token_urlsafe(24)
        ahora = time.time()
        _sesiones_caja_cliente[token] = {
            'slug': slug,
            'tienda_id': tienda['id'],
            'tienda_nombre': tienda['nombre'],
            'update_key': update_key,
            'estado': 'activa',
            'items': [],
            'recibo': None,
            'total': 0,
            'iva': 0,
            'updated_at': ahora,
            'created_at': ahora,
        }
        return jsonify({'ok': True, 'token': token, 'update_key': update_key, 'url': f'/tienda/{slug}/caja/cliente/{token}'})
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/caja/sesion/<token>', methods=['GET', 'POST'])
def api_tienda_caja_sesion(slug, token):
    _limpiar_sesiones_caja()
    sesion = _sesiones_caja_cliente.get(token)
    if not sesion or sesion.get('slug') != slug:
        return jsonify({'ok': False, 'error': 'Sesion no encontrada'}), 404

    if request.method == 'GET':
        public_sesion = {k: v for k, v in sesion.items() if k != 'update_key'}
        return jsonify({'ok': True, **public_sesion})

    data = request.get_json(silent=True) or {}
    update_key = request.headers.get('X-Caja-Session-Key', '')
    if update_key != sesion.get('update_key'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    items = data.get('items') or []
    sesion.update({
        'estado': data.get('estado') or 'activa',
        'items': items[:80] if isinstance(items, list) else [],
        'recibo': data.get('recibo') if isinstance(data.get('recibo'), dict) else sesion.get('recibo'),
        'total': float(data.get('total') or 0),
        'iva': float(data.get('iva') or 0),
        'updated_at': time.time(),
    })
    return jsonify({'ok': True})


@bp.route('/promo/tienda/<slug>/<int:producto_id>/imagen')
def promo_tienda_imagen(slug, producto_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            """SELECT p.imagen FROM productos p
               JOIN tiendas t ON t.tercero_id = p.negocio_id
               WHERE t.slug = %s AND p.id = %s""",
            (slug, producto_id)
        ).fetchone()
        if not row or not row['imagen']:
            return '', 404
        imagen = row['imagen']
    finally:
        conn.close()
    try:
        import base64, io
        from flask import Response
        from PIL import Image, ImageFilter
        if imagen.startswith('data:'):
            _, b64data = imagen.split(',', 1)
            img_bytes = base64.b64decode(b64data)
        else:
            import urllib.request
            with urllib.request.urlopen(imagen, timeout=5) as resp:
                img_bytes = resp.read()
        original = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
        W, H = 1200, 630
        canvas = Image.new('RGBA', (W, H), (0, 0, 0, 255))
        bg = original.copy()
        bg_ratio = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * bg_ratio * 1.1), int(bg.height * bg_ratio * 1.1)), Image.LANCZOS)
        bx, by = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((bx, by, bx + W, by + H))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
        dark = Image.new('RGBA', (W, H), (0, 0, 0, 140))
        canvas.paste(bg.convert('RGB'), (0, 0))
        canvas.paste(dark, (0, 0), dark)
        max_w, max_h = int(W * 0.80), int(H * 0.88)
        img_ratio = min(max_w / original.width, max_h / original.height)
        new_w, new_h = int(original.width * img_ratio), int(original.height * img_ratio)
        fg = original.resize((new_w, new_h), Image.LANCZOS)
        canvas.paste(fg, ((W - new_w) // 2, (H - new_h) // 2), fg if fg.mode == 'RGBA' else None)
        out = io.BytesIO()
        canvas.convert('RGB').save(out, format='JPEG', quality=88, optimize=True)
        out.seek(0)
        from flask import Response
        return Response(out.read(), mimetype='image/jpeg',
                        headers={'Cache-Control': 'public, max-age=86400'})
    except Exception:
        return '', 500


@bp.route('/promo/tienda/<slug>/<int:producto_id>')
def promo_tienda_producto(slug, producto_id):
    conn = get_db_connection()
    try:
        tienda = conn.execute(
            "SELECT id, nombre, slug, imagen_header FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda:
            return "Tienda no encontrada", 404
        producto = conn.execute(
            "SELECT id, nombre, descripcion, precio, imagen FROM productos WHERE id = %s AND negocio_id = (SELECT tercero_id FROM tiendas WHERE id = %s) AND disponible = TRUE",
            (producto_id, tienda['id'])
        ).fetchone()
        if not producto:
            return "Producto no disponible", 404
        tiene_imagen    = bool(producto['imagen'])
        mostrar_foto    = request.args.get('foto',   '1') != '0'
        mostrar_precio  = request.args.get('precio', '1') != '0'
        mostrar_desc    = request.args.get('desc',   '1') != '0'
        txt             = request.args.get('txt',    '')
        leyenda         = request.args.get('leyenda', '¿A quién le llevamos?')
        return render_template('promo_tienda.html',
            tienda=tienda, producto=producto, tiene_imagen=tiene_imagen,
            mostrar_foto=mostrar_foto, mostrar_precio=mostrar_precio, mostrar_desc=mostrar_desc,
            txt=txt, leyenda=leyenda)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


# ── API Admin métodos de pago ──────────────────────────────────────────────────

@bp.route('/api/admin/tienda/<slug>/metodos-pago', methods=['GET'])
def api_admin_metodos_pago(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug=%s AND activo=TRUE", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        metodos = conn.execute("""
            SELECT c.id, c.nombre, c.codigo, c.icono, c.orden,
                   COALESCE(t.activo, FALSE) AS activo
            FROM metodos_pago_catalogo c
            LEFT JOIN metodos_pago_tienda t ON t.catalogo_id = c.id AND t.tienda_id = %s
            WHERE c.activo = TRUE
            ORDER BY c.orden, c.id
        """, (tienda['id'],)).fetchall()
        return jsonify({'ok': True, 'metodos': [dict(m) for m in metodos]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/admin/tienda/<slug>/metodos-pago/<int:catalogo_id>/toggle', methods=['POST'])
def api_admin_metodo_pago_toggle(slug, catalogo_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug=%s AND activo=TRUE", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        activo = bool((request.get_json() or {}).get('activo', True))
        conn.execute("""
            INSERT INTO metodos_pago_tienda (tienda_id, catalogo_id, activo)
            VALUES (%s, %s, %s)
            ON CONFLICT (tienda_id, catalogo_id) DO UPDATE SET activo = EXCLUDED.activo
        """, (tienda['id'], catalogo_id, activo))
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


@bp.route('/api/tienda/<slug>/metodos-pago')
def api_tienda_metodos_pago_publico(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug=%s AND activo=TRUE", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        metodos = conn.execute("""
            SELECT c.id, c.nombre, c.codigo
            FROM metodos_pago_tienda t
            JOIN metodos_pago_catalogo c ON c.id = t.catalogo_id
            WHERE t.tienda_id=%s AND t.activo=TRUE AND c.activo=TRUE
            ORDER BY c.orden, c.id
        """, (tienda['id'],)).fetchall()
        return jsonify({'ok': True, 'metodos': [dict(m) for m in metodos]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Recuperación de acceso ────────────────────────────────────────────────────

def _enviar_telegram_tienda(chat_id, texto):
    import os
    import requests as req
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token or not chat_id:
        return
    try:
        req.post(f'https://api.telegram.org/bot{token}/sendMessage',
                 json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'}, timeout=5)
    except Exception:
        pass


@bp.route('/api/tienda/recuperar', methods=['POST'])
def api_tienda_recuperar():
    data = request.get_json()
    telefono = ''.join(filter(str.isdigit, data.get('telefono', '')))
    slug = data.get('slug', '')
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular inválido'}), 400
    try:
        conn = get_db_connection()
        tienda = conn.execute(
            "SELECT id, admin_id, admin_telefono FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
        ).fetchone()
        if not tienda or tienda['admin_telefono'] != telefono:
            conn.close()
            return jsonify({'ok': False, 'error': 'Este celular no corresponde al administrador'}), 400
        tercero = conn.execute(
            "SELECT id, telegram_chat_id FROM terceros WHERE id = %s", (tienda['admin_id'],)
        ).fetchone()
        conn.close()
        if not tercero or not tercero['telegram_chat_id']:
            return jsonify({'ok': False, 'necesita_telegram': True, 'error': 'No tenés Telegram vinculado'}), 400
        codigo = str(random.randint(100000, 999999))
        session['codigo_recuperacion_tienda'] = codigo
        session['recuperar_tienda_admin_id'] = tercero['id']
        session['recuperar_tienda_slug'] = slug
        session.modified = True
        _enviar_telegram_tienda(tercero['telegram_chat_id'],
                                f"🔐 Tu código de acceso es:\n\n<b>{codigo}</b>\n\nIngresalo en la pantalla de recuperación.")
        return jsonify({'ok': True, 'mensaje': 'Código enviado a tu Telegram'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/tienda/verificar-codigo', methods=['POST'])
def api_tienda_verificar_codigo():
    data = request.get_json()
    codigo = data.get('codigo', '').strip()
    codigo_guardado = session.get('codigo_recuperacion_tienda')
    admin_id = session.get('recuperar_tienda_admin_id')
    slug = session.get('recuperar_tienda_slug')
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
        for k in ('codigo_recuperacion_tienda', 'recuperar_tienda_admin_id', 'recuperar_tienda_slug'):
            session.pop(k, None)
        session['usuario_id'] = tercero['id']
        session['nombre'] = tercero['nombre']
        session['telefono'] = tercero['telefono'] or ''
        session['rol'] = 'Tienda'
        session.permanent = True
        session.modified = True
        return jsonify({'ok': True, 'slug': slug})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API crear tienda ───────────────────────────────────────────────────────────

@bp.route('/api/tienda/crear', methods=['POST'])
def api_tienda_crear():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data          = request.get_json() or {}
    nombre        = data.get('nombre', '').strip()
    admin_nombre  = data.get('admin_nombre', '').strip()
    admin_telefono = ''.join(filter(str.isdigit, data.get('admin_telefono', '')))
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre de la tienda requerido'}), 400
    if not admin_nombre or not admin_telefono:
        return jsonify({'ok': False, 'error': 'Nombre y celular del administrador son requeridos'}), 400
    if len(admin_telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 digitos'}), 400
    slug         = _generar_slug(nombre)
    token_acceso = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        if conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone():
            return jsonify({'ok': False, 'error': 'Ya existe una tienda con ese nombre'}), 400
        # Tercero del dueño (persona)
        tercero = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (admin_telefono,)).fetchone()
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
            "INSERT INTO tiendas (nombre, slug, admin_id, admin_nombre, admin_telefono, token_acceso, tercero_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (nombre, slug, admin_id, admin_nombre, admin_telefono, token_acceso, negocio_tercero_id)
        )
        conn.commit()
        link = f"{request.host_url}t/acceso/{token_acceso}"
        return jsonify({'ok': True, 'slug': slug, 'nombre': nombre, 'token_acceso': token_acceso, 'link_acceso': link})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/dias-pagados', methods=['POST'])
def api_tienda_dias_pagados(slug):
    if session.get('rol') != 'Administrador':
        return jsonify({'ok': False, 'error': 'Sin permisos'}), 403
    dias = int((request.get_json() or {}).get('dias', 0))
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT dias_pagados, fecha_vence FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        nuevo_total = (tienda['dias_pagados'] or 0) + dias
        base        = tienda['fecha_vence'] if tienda['fecha_vence'] and tienda['fecha_vence'] > date.today() else date.today()
        nueva_fecha = base + timedelta(days=dias)
        conn.execute(
            "UPDATE tiendas SET dias_pagados = %s, fecha_vence = %s WHERE slug = %s",
            (nuevo_total, nueva_fecha, slug)
        )
        conn.commit()
        return jsonify({'ok': True, 'dias_pagados': nuevo_total, 'fecha_vence': str(nueva_fecha)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── API productos ──────────────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/productos')
def api_tienda_productos(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        productos = conn.execute(
            "SELECT id, nombre, categoria, precio, imagen, disponible, orden, descripcion, codigo_barra, catalogo_id, iva_pct FROM productos WHERE negocio_id = %s ORDER BY categoria, orden, nombre",
            (tienda['tercero_id'],)
        ).fetchall()
        categorias_media = conn.execute(
            """
            SELECT categoria, imagen
            FROM tienda_categorias
            WHERE tienda_id = %s
            """,
            (tienda['id'],)
        ).fetchall()
        media_por_categoria = {c['categoria']: c['imagen'] for c in categorias_media}
        resultado = []
        for p in productos:
            nv = conn.execute("SELECT COUNT(*) FROM producto_variantes WHERE producto_id = %s", (p['id'],)).fetchone()[0]
            nf = conn.execute("SELECT COUNT(*) FROM producto_imagenes WHERE producto_id = %s", (p['id'],)).fetchone()[0]
            doc = conn.execute("""
                SELECT id, nombre
                FROM producto_documentos
                WHERE producto_id = %s AND visible_cliente = TRUE
                ORDER BY tipo = 'ficha_tecnica' DESC, orden, id
                LIMIT 1
            """, (p['id'],)).fetchone()
            nd = conn.execute("SELECT COUNT(*) FROM producto_documentos WHERE producto_id = %s", (p['id'],)).fetchone()[0]
            resultado.append({
                'id': p['id'], 'nombre': p['nombre'], 'categoria': p['categoria'] or '',
                'precio': float(p['precio']), 'imagen': p['imagen'] or '',
                'disponible': p['disponible'], 'orden': p['orden'],
                'descripcion': p['descripcion'] or '',
                'codigo_barra': p['codigo_barra'] or '',
                'catalogo_id': p['catalogo_id'],
                'iva_pct': float(p['iva_pct'] or 0),
                'tiene_variantes': nv > 0,
                'n_fotos': nf,
                'n_documentos': nd,
                'ficha_tecnica_id': doc['id'] if doc else None,
                'ficha_tecnica_nombre': doc['nombre'] if doc else '',
            })
        categorias = []
        vistas = set()
        for p in productos:
            categoria = p['categoria'] or 'Sin categoria'
            if categoria in vistas:
                continue
            vistas.add(categoria)
            categorias.append({
                'nombre': categoria,
                'imagen': media_por_categoria.get(categoria) or '',
            })
        return jsonify({'ok': True, 'productos': resultado, 'categorias': categorias})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto', methods=['POST'])
def api_tienda_producto_crear(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = None
    try:
        data        = request.get_json(force=True) or {}
        nombre      = (data.get('nombre') or '').strip()
        categoria   = (data.get('categoria') or '').strip()
        precio      = float(data.get('precio', 0))
        producto_id = data.get('id')
        descripcion = (data.get('descripcion') or '').strip()
        codigo_barra = (data.get('codigo_barra') or '').strip() or None
        catalogo_id  = data.get('catalogo_id') or None
        iva_pct      = float(data.get('iva_pct', 0) or 0)
        if not nombre:
            return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
        conn = get_db_connection()
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        if codigo_barra and not catalogo_id:
            existing = conn.execute("SELECT id FROM catalogo_productos WHERE codigo_barra = %s", (codigo_barra,)).fetchone()
            if existing:
                catalogo_id = existing['id']
            else:
                cat_row = conn.execute(
                    "INSERT INTO catalogo_productos (codigo_barra, nombre, descripcion, categoria) VALUES (%s,%s,%s,%s) RETURNING id",
                    (codigo_barra, nombre, descripcion or None, categoria or None)
                ).fetchone()
                catalogo_id = cat_row['id']
                conn.commit()
        if producto_id:
            conn.execute(
                "UPDATE productos SET nombre=%s, categoria=%s, precio=%s, descripcion=%s, catalogo_id=%s, codigo_barra=%s, iva_pct=%s WHERE id=%s AND negocio_id=%s",
                (nombre, categoria, precio, descripcion or None, catalogo_id, codigo_barra, iva_pct, producto_id, tienda['tercero_id'])
            )
            nuevo_id = producto_id
        else:
            row = conn.execute(
                "INSERT INTO productos (negocio_id, nombre, categoria, precio, descripcion, catalogo_id, codigo_barra, iva_pct) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (tienda['tercero_id'], nombre, categoria, precio, descripcion or None, catalogo_id, codigo_barra, iva_pct)
            ).fetchone()
            nuevo_id = row['id']
        conn.commit()
        return jsonify({'ok': True, 'id': nuevo_id})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@bp.route('/api/catalogo/buscar')
def api_catalogo_buscar():
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({'ok': False, 'error': 'Código requerido'}), 400
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, nombre, descripcion, imagen, categoria FROM catalogo_productos WHERE codigo_barra = %s", (codigo,)
        ).fetchone()
        if row:
            return jsonify({'ok': True, 'encontrado': True, 'producto': dict(row)})
        return jsonify({'ok': True, 'encontrado': False})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>', methods=['DELETE'])
def api_tienda_producto_eliminar(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("DELETE FROM productos WHERE id = %s AND negocio_id = %s", (producto_id, tienda['tercero_id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/imagen', methods=['POST'])
def api_tienda_producto_imagen(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    imagen = (request.get_json() or {}).get('imagen', '')
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("UPDATE productos SET imagen = %s WHERE id = %s AND negocio_id = %s", (imagen, producto_id, tienda['tercero_id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/disponible', methods=['POST'])
def api_tienda_producto_disponible(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    disponible = (request.get_json() or {}).get('disponible', True)
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("UPDATE productos SET disponible = %s WHERE id = %s AND negocio_id = %s", (disponible, producto_id, tienda['tercero_id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/buscar-productos')
def api_tienda_buscar_productos(slug):
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'ok': True, 'productos': []})
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        productos = conn.execute("""
            SELECT DISTINCT nombre, categoria FROM productos
            WHERE negocio_id != %s AND LOWER(nombre) LIKE %s LIMIT 20
        """, (tienda['tercero_id'], f'%{q.lower()}%')).fetchall()
        return jsonify({'ok': True, 'productos': [{'nombre': p['nombre'], 'categoria': p['categoria'] or ''} for p in productos]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/adoptar-producto', methods=['POST'])
def api_tienda_adoptar_producto(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data     = request.get_json() or {}
    nombre   = data.get('nombre', '').strip()
    categoria = data.get('categoria', '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        if conn.execute("SELECT id FROM productos WHERE negocio_id = %s AND LOWER(nombre) = %s", (tienda['tercero_id'], nombre.lower())).fetchone():
            return jsonify({'ok': False, 'error': 'Ya tienes este producto'}), 400
        conn.execute("INSERT INTO productos (negocio_id, nombre, categoria, precio) VALUES (%s,%s,%s,0)", (tienda['tercero_id'], nombre, categoria))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── API personalización ────────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/imagen-header', methods=['POST'])
def api_tienda_imagen_header(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    imagen = data.get('imagen', '')
    tipo = data.get('tipo', 'desktop')
    campo = 'imagen_header_movil' if tipo == 'movil' else 'imagen_header'
    conn = get_db_connection()
    try:
        conn.execute(f"UPDATE tiendas SET {campo} = %s WHERE slug = %s", (imagen, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/tema', methods=['POST'])
def api_tienda_tema(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    tema = (request.get_json() or {}).get('tema', 'claro')
    if tema not in ('claro', 'oscuro'):
        tema = 'claro'
    conn = get_db_connection()
    try:
        conn.execute("UPDATE tiendas SET tema = %s WHERE slug = %s", (tema, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/descripcion', methods=['POST'])
def api_tienda_descripcion(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    descripcion = ((request.get_json() or {}).get('descripcion', '') or '').strip() or None
    conn = get_db_connection()
    try:
        conn.execute("UPDATE tiendas SET descripcion = %s WHERE slug = %s", (descripcion, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/movil-cols', methods=['POST'])
def api_tienda_movil_cols(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    cols = (request.get_json() or {}).get('cols', 2)
    if cols not in (1, 2):
        cols = 2
    conn = get_db_connection()
    try:
        conn.execute("UPDATE tiendas SET movil_cols = %s WHERE slug = %s", (cols, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/desktop-layout', methods=['POST'])
def api_tienda_desktop_layout(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    layout = (request.get_json() or {}).get('layout', 'movil')
    if layout not in ('movil', 'ampliado', 'galeria'):
        layout = 'movil'
    conn = get_db_connection()
    try:
        conn.execute("UPDATE tiendas SET desktop_layout = %s WHERE slug = %s", (layout, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/mostrar-nombre', methods=['POST'])
def api_tienda_mostrar_nombre(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    mostrar = (request.get_json() or {}).get('mostrar', True)
    conn = get_db_connection()
    try:
        conn.execute("UPDATE tiendas SET mostrar_nombre = %s WHERE slug = %s", (mostrar, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/experiencia', methods=['POST'])
def api_tienda_experiencia(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    pantalla = bool(data.get('pantalla_experiencial', False))
    color = (data.get('color_accion') or '#e11d48').strip()
    if not color.startswith('#') or len(color) not in (4, 7):
        color = '#e11d48'
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE tiendas SET pantalla_experiencial = %s, color_accion = %s WHERE slug = %s",
            (pantalla, color, slug)
        )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/categoria-imagen', methods=['POST'])
def api_tienda_categoria_imagen(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    categoria = (data.get('categoria') or '').strip()
    imagen = (data.get('imagen') or '').strip() or None
    if not categoria:
        return jsonify({'ok': False, 'error': 'Categoria requerida'}), 400
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("""
            INSERT INTO tienda_categorias (tienda_id, categoria, imagen, updated_at)
            VALUES (%s,%s,%s,NOW())
            ON CONFLICT (tienda_id, categoria)
            DO UPDATE SET imagen = EXCLUDED.imagen, updated_at = NOW()
        """, (tienda['id'], categoria, imagen))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cotizaciones')
def api_tienda_cotizaciones(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        rows = conn.execute("""
            SELECT id, cliente_nombre, cliente_telefono, ubicacion, objetivo,
                   consumo_mensual, factor_generacion, estado, total, created_at
            FROM cotizaciones_tienda
            WHERE tienda_id = %s
            ORDER BY created_at DESC
            LIMIT 80
        """, (tienda['id'],)).fetchall()
        cotizaciones = []
        for r in rows:
            cotizaciones.append({
                'id': r['id'],
                'cliente_nombre': r['cliente_nombre'] or '',
                'cliente_telefono': r['cliente_telefono'] or '',
                'ubicacion': r['ubicacion'] or '',
                'objetivo': r['objetivo'] or '',
                'consumo_mensual': float(r['consumo_mensual'] or 0),
                'factor_generacion': float(r['factor_generacion'] or 0),
                'estado': r['estado'] or 'borrador',
                'total': float(r['total'] or 0),
                'created_at': r['created_at'].isoformat() if r['created_at'] else None,
            })
        return jsonify({'ok': True, 'cotizaciones': cotizaciones})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cotizacion/<int:cotizacion_id>')
def api_tienda_cotizacion_detalle(slug, cotizacion_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        cot = conn.execute("""
            SELECT c.*
            FROM cotizaciones_tienda c
            JOIN tiendas t ON t.id = c.tienda_id
            WHERE t.slug = %s AND c.id = %s
        """, (slug, cotizacion_id)).fetchone()
        if not cot:
            return jsonify({'ok': False, 'error': 'Cotizacion no encontrada'}), 404
        consumos = cot['consumos_json'] or []
        datos_tecnicos = cot['datos_tecnicos'] or {}
        if isinstance(consumos, str):
            consumos = json.loads(consumos or '[]')
        if isinstance(datos_tecnicos, str):
            datos_tecnicos = json.loads(datos_tecnicos or '{}')
        items = conn.execute("""
            SELECT id, producto_id, nombre, categoria, cantidad, precio_unitario, total, notas, orden
            FROM cotizacion_items_tienda
            WHERE cotizacion_id = %s
            ORDER BY orden, id
        """, (cotizacion_id,)).fetchall()
        return jsonify({
            'ok': True,
            'cotizacion': {
                'id': cot['id'],
                'cliente_nombre': cot['cliente_nombre'] or '',
                'cliente_telefono': cot['cliente_telefono'] or '',
                'cliente_email': cot['cliente_email'] or '',
                'ubicacion': cot['ubicacion'] or '',
                'factor_generacion': float(cot['factor_generacion'] or 0),
                'consumo_mensual': float(cot['consumo_mensual'] or 0),
                'objetivo': cot['objetivo'] or '',
                'consumos': consumos,
                'datos_tecnicos': datos_tecnicos,
                'notas': cot['notas'] or '',
                'estado': cot['estado'] or 'borrador',
                'subtotal': float(cot['subtotal'] or 0),
                'total': float(cot['total'] or 0),
                'items': [{
                    'id': it['id'],
                    'producto_id': it['producto_id'],
                    'nombre': it['nombre'],
                    'categoria': it['categoria'] or '',
                    'cantidad': float(it['cantidad'] or 0),
                    'precio_unitario': float(it['precio_unitario'] or 0),
                    'total': float(it['total'] or 0),
                    'notas': it['notas'] or '',
                } for it in items]
            }
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cotizacion', methods=['POST'])
def api_tienda_cotizacion_guardar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    items = data.get('items') or []
    if not data.get('cliente_nombre'):
        return jsonify({'ok': False, 'error': 'Cliente requerido'}), 400
    if not items:
        return jsonify({'ok': False, 'error': 'Agrega al menos una linea'}), 400

    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404

        subtotal = 0.0
        lineas = []
        for idx, item in enumerate(items):
            cantidad = float(item.get('cantidad') or 0)
            precio = float(item.get('precio_unitario') or 0)
            if cantidad <= 0:
                continue
            total = round(cantidad * precio, 2)
            subtotal += total
            lineas.append({
                'producto_id': item.get('producto_id') or None,
                'nombre': (item.get('nombre') or 'Item').strip(),
                'categoria': (item.get('categoria') or '').strip() or None,
                'cantidad': cantidad,
                'precio_unitario': precio,
                'total': total,
                'notas': (item.get('notas') or '').strip() or None,
                'orden': idx,
            })
        if not lineas:
            return jsonify({'ok': False, 'error': 'Agrega cantidades validas'}), 400

        cotizacion_id = data.get('id')
        total = round(subtotal, 2)
        payload = (
            data.get('cliente_nombre', '').strip(),
            (data.get('cliente_telefono') or '').strip() or None,
            (data.get('cliente_email') or '').strip() or None,
            (data.get('ubicacion') or '').strip() or None,
            float(data.get('factor_generacion') or 0) or None,
            float(data.get('consumo_mensual') or 0) or None,
            (data.get('objetivo') or '').strip() or None,
            json.dumps(data.get('consumos') or []),
            json.dumps(data.get('datos_tecnicos') or {}),
            (data.get('notas') or '').strip() or None,
            data.get('estado') or 'borrador',
            subtotal,
            total,
        )

        if cotizacion_id:
            row = conn.execute("""
                UPDATE cotizaciones_tienda
                   SET cliente_nombre=%s, cliente_telefono=%s, cliente_email=%s,
                       ubicacion=%s, factor_generacion=%s, consumo_mensual=%s,
                       objetivo=%s, consumos_json=%s::jsonb, datos_tecnicos=%s::jsonb,
                       notas=%s, estado=%s, subtotal=%s, total=%s, updated_at=NOW()
                 WHERE id=%s AND tienda_id=%s
                 RETURNING id
            """, (*payload, cotizacion_id, tienda['id'])).fetchone()
            if not row:
                return jsonify({'ok': False, 'error': 'Cotizacion no encontrada'}), 404
            conn.execute("DELETE FROM cotizacion_items_tienda WHERE cotizacion_id=%s", (cotizacion_id,))
        else:
            token = secrets.token_urlsafe(18)
            row = conn.execute("""
                INSERT INTO cotizaciones_tienda
                    (tienda_id, cliente_nombre, cliente_telefono, cliente_email,
                     ubicacion, factor_generacion, consumo_mensual, objetivo,
                     consumos_json, datos_tecnicos, notas, estado, subtotal, total, token_publico)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                RETURNING id
            """, (tienda['id'], *payload, token)).fetchone()
            cotizacion_id = row['id']

        for item in lineas:
            conn.execute("""
                INSERT INTO cotizacion_items_tienda
                    (cotizacion_id, producto_id, nombre, categoria, cantidad,
                     precio_unitario, total, notas, orden)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                cotizacion_id, item['producto_id'], item['nombre'], item['categoria'],
                item['cantidad'], item['precio_unitario'], item['total'],
                item['notas'], item['orden']
            ))
        conn.commit()
        return jsonify({'ok': True, 'cotizacion_id': cotizacion_id, 'total': total})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pedido/<int:pedido_id>/comprobante', methods=['POST'])
def api_tienda_pedido_comprobante(slug, pedido_id):
    data = request.get_json() or {}
    imagen = (data.get('imagen') or '').strip()
    if not imagen:
        return jsonify({'ok': False, 'error': 'Sin imagen'}), 400
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug=%s AND activo=TRUE", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        cur = conn.execute(
            "UPDATE pedidos_tienda SET comprobante_pago=%s WHERE id=%s AND tienda_id=%s",
            (imagen, pedido_id, tienda['id'])
        )
        if cur.rowcount == 0:
            return jsonify({'ok': False, 'error': 'Pedido no encontrado'}), 404
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/admin/ubicacion', methods=['POST'])
def api_tienda_ubicacion(slug):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'sin_sesion'}), 401
    data = request.get_json(silent=True) or {}
    lat  = data.get('lat')
    lon  = data.get('lon')
    if lat is None or lon is None:
        return jsonify({'ok': False, 'error': 'Coordenadas requeridas'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        es_admin = session.get('rol') == 'Administrador'
        if es_admin:
            tienda = conn.execute("SELECT id, nombre FROM tiendas WHERE slug=%s", (slug,)).fetchone()
        else:
            tienda = conn.execute("SELECT id, nombre FROM tiendas WHERE slug=%s AND admin_id=%s", (slug, uid)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Sin acceso'}), 403
        conn.execute("UPDATE tiendas SET lat=%s, lon=%s WHERE id=%s", (lat, lon, tienda['id']))
        conn.commit()
        _registrar_negocio_en_pois(conn, tienda['nombre'], lat, lon, uid)
        return jsonify({'ok': True})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/telegram', methods=['POST'])
def api_tienda_telegram(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    chat_id = (request.get_json() or {}).get('telegram_chat_id', '').strip()
    conn = get_db_connection()
    try:
        conn.execute("UPDATE tiendas SET telegram_chat_id = %s WHERE slug = %s", (chat_id or None, slug))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── API pedidos ────────────────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/cliente-info')
def api_tienda_cliente_info(slug):
    tercero_id = request.args.get('id', '').strip()
    tel        = request.args.get('tel', '').strip()
    if not tercero_id and not tel:
        return jsonify({'ok': False}), 400
    conn = get_db_connection()
    try:
        if tercero_id:
            row = conn.execute("SELECT id, nombre, telefono, direccion FROM terceros WHERE id = %s LIMIT 1", (tercero_id,)).fetchone()
        else:
            row = conn.execute("SELECT id, nombre, telefono, direccion FROM terceros WHERE telefono = %s LIMIT 1", (tel,)).fetchone()
        if row:
            return jsonify({'ok': True, 'id': row['id'], 'nombre': row['nombre'], 'telefono': row['telefono'], 'direccion': row['direccion'] or ''})
        return jsonify({'ok': False})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/promo-invitar', methods=['POST'])
def api_tienda_promo_invitar(slug):
    data     = request.get_json() or {}
    nombre   = (data.get('nombre') or '').strip()
    telefono = (data.get('telefono') or '').replace(' ', '').replace('-', '')
    if not telefono:
        return jsonify({'ok': False, 'error': 'Teléfono requerido'}), 400
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)).fetchone()
        if existing:
            if nombre:
                conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (nombre, existing['id']))
                conn.commit()
            return jsonify({'ok': True, 'id': existing['id']})
        row = conn.execute(
            "INSERT INTO terceros (nombre, telefono, fecha_creacion) VALUES (%s, %s, NOW()) RETURNING id",
            (nombre or telefono, telefono)
        ).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/registrar-cliente', methods=['POST'])
def api_tienda_registrar_cliente(slug):
    data      = request.get_json() or {}
    nombre    = data.get('nombre', '').strip()
    telefono  = ''.join(filter(str.isdigit, data.get('telefono', '')))
    direccion = data.get('direccion', '').strip()
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    if len(telefono) < 10:
        return jsonify({'ok': False, 'error': 'Celular debe tener al menos 10 digitos'}), 400
    conn = get_db_connection()
    try:
        tercero = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)).fetchone()
        if tercero:
            cliente_id = tercero['id']
            conn.execute("UPDATE terceros SET nombre = %s, direccion = %s WHERE id = %s", (nombre, direccion, cliente_id))
        else:
            conn.execute("INSERT INTO terceros (nombre, telefono, direccion) VALUES (%s, %s, %s)", (nombre, telefono, direccion))
            cliente_id = conn.execute("SELECT id FROM terceros WHERE telefono = %s", (telefono,)).fetchone()['id']
        conn.commit()
        session['usuario_id'] = cliente_id
        session['nombre']     = nombre
        session['telefono']   = telefono
        session['rol']        = 'Cliente'
        session.permanent     = True
        session.modified      = True
        return jsonify({'ok': True, 'cliente_id': cliente_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pedido', methods=['POST'])
def api_tienda_pedido_crear(slug):
    data             = request.get_json() or {}
    nombre_cliente   = data.get('nombre_cliente', '').strip()
    telefono_cliente = data.get('telefono_cliente', '').strip()
    direccion_cliente = data.get('direccion_cliente', '').strip()
    tipo_entrega     = data.get('tipo_entrega', 'domicilio')
    notas            = data.get('notas', '').strip()
    cliente_id       = data.get('cliente_id')
    metodo_pago      = data.get('metodo_pago', 'efectivo')
    pagos            = data.get('pagos', [])
    items            = data.get('items', [])
    id_cajero        = data.get('id_cajero')
    nombre_cajero    = data.get('nombre_cajero', '').strip() or None
    id_tercero_cajero = data.get('id_tercero_cajero')
    if not items:
        return jsonify({'ok': False, 'error': 'El carrito esta vacio'}), 400
    if not nombre_cliente and tipo_entrega != 'caja':
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT id, nombre, dias_pagados, telegram_chat_id, fecha_vence, tercero_id FROM tiendas WHERE slug = %s AND activo = TRUE",
            (slug,)
        ).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        fecha_vence = tienda['fecha_vence']
        if fecha_vence and date.today() > fecha_vence:
            return jsonify({'ok': False, 'error': 'suscripcion_agotada', 'fecha_vence': str(fecha_vence)}), 402
        total = 0
        items_validos = []
        for item in items:
            producto = conn.execute(
                "SELECT id, nombre, precio, disponible, iva_pct FROM productos WHERE id = %s AND negocio_id = %s",
                (item.get('producto_id'), tienda['tercero_id'])
            ).fetchone()
            if not producto or not producto['disponible']:
                continue
            cantidad  = max(1, int(item.get('cantidad', 1)))
            precio_u  = float(producto['precio'])
            total    += precio_u * cantidad
            items_validos.append({
                'producto_id': producto['id'], 'nombre_producto': producto['nombre'],
                'cantidad': cantidad, 'precio_unitario': precio_u,
                'iva_pct': float(producto['iva_pct'] or 0)
            })
        if not items_validos:
            return jsonify({'ok': False, 'error': 'Ningun producto valido en el carrito'}), 400
        conn.execute("""
            INSERT INTO pedidos_tienda
                (tienda_id, cliente_id, nombre_cliente, telefono_cliente, direccion_cliente,
                 tipo_entrega, total, notas, metodo_pago, id_cajero, nombre_cajero, id_tercero_cajero)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (tienda['id'], cliente_id, nombre_cliente or None, telefono_cliente or None,
              direccion_cliente or None, tipo_entrega, total, notas or None, metodo_pago,
              id_cajero, nombre_cajero, id_tercero_cajero))
        pedido_id = conn.execute(
            "SELECT currval(pg_get_serial_sequence('pedidos_tienda', 'id'))"
        ).fetchone()[0]
        for it in items_validos:
            conn.execute("""
                INSERT INTO items_pedido_tienda (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario)
                VALUES (%s,%s,%s,%s,%s)
            """, (pedido_id, it['producto_id'], it['nombre_producto'], it['cantidad'], it['precio_unitario']))
            if tienda['tercero_id']:
                try:
                    _aplicar_tarjeta(
                        conn, tienda['tercero_id'],
                        producto_id    = it['producto_id'],
                        cantidad       = it['cantidad'],
                        tipo           = 'salida',
                        motivo         = 'venta',
                        registrado_por = session.get('usuario_id'),
                        referencia_id  = pedido_id,
                        referencia_tipo= 'pedido_tienda',
                    )
                except Exception as _e:
                    print(f'[inv] salida tienda {it["producto_id"]}: {_e}')
                    try: conn.rollback()
                    except: pass
        pagos_validos = [p for p in pagos if float(p.get('monto') or 0) > 0]
        if pagos_validos:
            for p in pagos_validos:
                conn.execute("""
                    INSERT INTO pedido_pagos_tienda (pedido_id, metodo_codigo, metodo_nombre, monto)
                    VALUES (%s,%s,%s,%s)
                """, (pedido_id, p['codigo'], p.get('nombre', p['codigo']), float(p['monto'])))
        else:
            conn.execute("""
                INSERT INTO pedido_pagos_tienda (pedido_id, metodo_codigo, metodo_nombre, monto)
                VALUES (%s,%s,%s,%s)
            """, (pedido_id, metodo_pago, metodo_pago, total))
        if tienda['tercero_id'] and _asiento_auto:
            try:
                iva_total = sum(
                    it['precio_unitario'] * it['cantidad'] * it['iva_pct'] / 100
                    for it in items_validos
                )
                tipo_doc = 'VENTA_POS' if tipo_entrega == 'caja' else 'VENTA_DOM'
                _asiento_auto(conn, tienda['tercero_id'], tipo_doc,
                              {'subtotal_venta': total - iva_total,
                               'iva_venta': iva_total,
                               'total_venta': total},
                              registrado_por=session.get('usuario_id'))
            except Exception as _e:
                print(f'[cont] venta tienda {slug}: {_e}')
        conn.commit()
        # Notificación Telegram
        chat_id = tienda['telegram_chat_id']
        if chat_id:
            items_txt = '\n'.join([f"  {it['cantidad']}x {it['nombre_producto']} - ${it['precio_unitario'] * it['cantidad']:,.0f}" for it in items_validos])
            entrega   = 'Domicilio' if tipo_entrega == 'domicilio' else 'Recoger'
            msg = f"🛒 <b>Nuevo pedido en {tienda['nombre']}</b>\n👤 {nombre_cliente} - {telefono_cliente}\n📦 {entrega}: {direccion_cliente or 'N/A'}\n\n{items_txt}\n\n💰 Total: ${total:,.0f}"
            _enviar_telegram_tienda(conn, chat_id, msg)
        return jsonify({'ok': True, 'pedido_id': pedido_id, 'total': total})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pedidos')
def api_tienda_pedidos(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        pedidos = conn.execute("""
            SELECT id, nombre_cliente, telefono_cliente, direccion_cliente, tipo_entrega,
                   estado, total, notas, created_at, nombre_cajero, metodo_pago, comprobante_pago
            FROM pedidos_tienda WHERE tienda_id = %s AND DATE(created_at) = CURRENT_DATE
            ORDER BY created_at DESC
        """, (tienda['id'],)).fetchall()
        resultado = []
        for p in pedidos:
            items = conn.execute(
                "SELECT nombre_producto, cantidad, precio_unitario FROM items_pedido_tienda WHERE pedido_id = %s",
                (p['id'],)
            ).fetchall()
            resultado.append({
                'id': p['id'],
                'nombre_cliente': p['nombre_cliente'] or '',
                'telefono_cliente': p['telefono_cliente'] or '',
                'direccion_cliente': p['direccion_cliente'] or '',
                'tipo_entrega': p['tipo_entrega'],
                'estado': p['estado'],
                'total': float(p['total']),
                'notas': p['notas'] or '',
                'created_at': p['created_at'].strftime('%H:%M') if p['created_at'] else '',
                'nombre_cajero': p['nombre_cajero'] or '',
                'metodo_pago': p['metodo_pago'] or 'efectivo',
                'comprobante_pago': p['comprobante_pago'] or '',
                'items': [{'nombre': i['nombre_producto'], 'cantidad': i['cantidad'], 'precio': float(i['precio_unitario'])} for i in items]
            })
        return jsonify({'ok': True, 'pedidos': resultado})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pedido/<int:pedido_id>/estado', methods=['POST'])
def api_tienda_pedido_estado(slug, pedido_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    estado = (request.get_json() or {}).get('estado', '')
    if estado not in ('nuevo', 'preparando', 'listo', 'entregado'):
        return jsonify({'ok': False, 'error': 'Estado invalido'}), 400
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute(
            "UPDATE pedidos_tienda SET estado = %s WHERE id = %s AND tienda_id = %s",
            (estado, pedido_id, tienda['id'])
        )
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


@bp.route('/api/tienda/<slug>/suscripcion')
def api_tienda_suscripcion(slug):
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, dias_pagados FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        dias_usados  = conn.execute(
            "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos_tienda WHERE tienda_id = %s",
            (tienda['id'],)
        ).fetchone()['dias']
        dias_pagados = tienda['dias_pagados'] or 0
        return jsonify({
            'ok': True, 'dias_pagados': dias_pagados,
            'dias_usados': dias_usados,
            'dias_restantes': max(0, dias_pagados - dias_usados)
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Caja PIN y cajeros ─────────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/verificar-pin-caja', methods=['POST'])
def api_tienda_verificar_pin_caja(slug):
    pin = ((request.get_json() or {}).get('pin') or '').strip()
    if not pin:
        return jsonify({'ok': False, 'error': 'PIN requerido'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        cajero = conn.execute(
            "SELECT id, nombre, tercero_id FROM tienda_cajeros WHERE tienda_id = %s AND pin = %s AND activo = TRUE",
            (tienda['id'], pin)
        ).fetchone()
        if not cajero:
            return jsonify({'ok': False, 'error': 'PIN incorrecto o cajero inactivo'}), 403
        return jsonify({'ok': True, 'id_cajero': cajero['id'], 'nombre_cajero': cajero['nombre'], 'tercero_id': cajero['tercero_id']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pin-caja', methods=['GET', 'POST'])
def api_tienda_pin_caja(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, pin_caja FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        if request.method == 'GET':
            return jsonify({'ok': True, 'pin_caja': tienda['pin_caja'] or ''})
        nuevo_pin = ((request.get_json() or {}).get('pin_caja') or '').strip()
        conn.execute("UPDATE tiendas SET pin_caja = %s WHERE id = %s", (nuevo_pin or None, tienda['id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cajeros', methods=['GET'])
def api_tienda_cajeros_listar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        cajeros = conn.execute(
            "SELECT id, nombre, pin, activo FROM tienda_cajeros WHERE tienda_id = %s ORDER BY id",
            (tienda['id'],)
        ).fetchall()
        return jsonify({'ok': True, 'cajeros': [dict(c) for c in cajeros]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cajero', methods=['POST'])
def api_tienda_cajero_crear(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data         = request.get_json() or {}
    telefono     = (data.get('telefono') or '').strip()
    nombre_custom = (data.get('nombre') or '').strip()
    pin          = (data.get('pin') or '').strip()
    if not telefono or not pin:
        return jsonify({'ok': False, 'error': 'Teléfono y PIN requeridos'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        if conn.execute("SELECT id FROM tienda_cajeros WHERE tienda_id = %s AND pin = %s", (tienda['id'], pin)).fetchone():
            return jsonify({'ok': False, 'error': 'Ya existe un cajero con ese PIN'}), 409
        tercero = conn.execute("SELECT id, nombre FROM terceros WHERE telefono = %s", (telefono,)).fetchone()
        if not tercero:
            nombre = nombre_custom or telefono
            conn.execute("INSERT INTO terceros (nombre, telefono) VALUES (%s, %s)", (nombre, telefono))
            conn.commit()
            tercero = conn.execute("SELECT id, nombre FROM terceros WHERE telefono = %s", (telefono,)).fetchone()
        tercero_id = tercero['id']
        nombre     = nombre_custom or tercero['nombre']
        cajero = conn.execute(
            "INSERT INTO tienda_cajeros (tienda_id, tercero_id, nombre, pin) VALUES (%s,%s,%s,%s) RETURNING id",
            (tienda['id'], tercero_id, nombre, pin)
        ).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': cajero['id'], 'nombre': nombre, 'tercero_id': tercero_id})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cajero/<int:cajero_id>/toggle', methods=['POST'])
def api_tienda_cajero_toggle(slug, cajero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute(
            "UPDATE tienda_cajeros SET activo = NOT activo WHERE id = %s AND tienda_id = %s",
            (cajero_id, tienda['id'])
        )
        conn.commit()
        nuevo = conn.execute("SELECT activo FROM tienda_cajeros WHERE id = %s", (cajero_id,)).fetchone()
        return jsonify({'ok': True, 'activo': nuevo['activo']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/cajero/<int:cajero_id>', methods=['DELETE'])
def api_tienda_cajero_eliminar(slug, cajero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("DELETE FROM tienda_cajeros WHERE id = %s AND tienda_id = %s", (cajero_id, tienda['id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Vendedores ─────────────────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/vendedores', methods=['GET'])
def api_tienda_vendedores_listar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        rows = conn.execute("""
            SELECT tv.id, tv.vendedor_id, t.nombre, t.telefono
            FROM tienda_vendedores tv
            JOIN terceros t ON t.id = tv.vendedor_id
            WHERE tv.tienda_id = %s AND tv.activo = TRUE ORDER BY tv.created_at ASC
        """, (tienda['id'],)).fetchall()
        return jsonify({'ok': True, 'vendedores': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/vendedores', methods=['POST'])
def api_tienda_vendedores_agregar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data     = request.get_json() or {}
    telefono = (data.get('telefono') or '').strip().replace(' ', '')
    nombre   = (data.get('nombre') or '').strip()[:100]
    if not telefono:
        return jsonify({'ok': False, 'error': 'Teléfono requerido'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        tercero = conn.execute("SELECT id, nombre FROM terceros WHERE telefono = %s", (telefono,)).fetchone()
        if tercero:
            vendedor_id = tercero['id']
            nombre_real = tercero['nombre']
        else:
            if not nombre:
                return jsonify({'ok': False, 'error': 'Vendedor no registrado — envía también su nombre'}), 400
            new = conn.execute(
                "INSERT INTO terceros (nombre, telefono, fecha_creacion) VALUES (%s, %s, NOW()) RETURNING id",
                (nombre, telefono)
            ).fetchone()
            conn.commit()
            vendedor_id = new['id']
            nombre_real = nombre
        conn.execute(
            "INSERT INTO tienda_vendedores (tienda_id, vendedor_id, activo) VALUES (%s,%s,TRUE) ON CONFLICT (tienda_id, vendedor_id) DO UPDATE SET activo = TRUE",
            (tienda['id'], vendedor_id)
        )
        conn.commit()
        return jsonify({'ok': True, 'vendedor_id': vendedor_id, 'nombre': nombre_real})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/vendedores/<int:vid>', methods=['DELETE'])
def api_tienda_vendedores_eliminar(slug, vid):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("UPDATE tienda_vendedores SET activo = FALSE WHERE tienda_id = %s AND id = %s", (tienda['id'], vid))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Variantes de productos ─────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/atributos')
def api_tienda_atributos(slug, producto_id):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        producto = conn.execute(
            "SELECT id, precio FROM productos WHERE id = %s AND negocio_id = %s",
            (producto_id, tienda['tercero_id'])
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        atributos = conn.execute(
            "SELECT id, nombre, orden FROM producto_atributos WHERE producto_id = %s ORDER BY orden, id",
            (producto_id,)
        ).fetchall()
        resultado = []
        for a in atributos:
            valores = conn.execute(
                "SELECT id, valor, orden FROM atributo_valores WHERE atributo_id = %s ORDER BY orden, id",
                (a['id'],)
            ).fetchall()
            resultado.append({'id': a['id'], 'nombre': a['nombre'], 'valores': [dict(v) for v in valores]})
        variantes = conn.execute(
            "SELECT id, atributos, precio, disponible FROM producto_variantes WHERE producto_id = %s ORDER BY id",
            (producto_id,)
        ).fetchall()
        return jsonify({
            'ok': True,
            'atributos': resultado,
            'variantes': [{'id': v['id'], 'atributos': v['atributos'], 'precio': float(v['precio']), 'disponible': v['disponible']} for v in variantes]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/atributo', methods=['POST'])
def api_tienda_atributo_crear(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data    = request.get_json() or {}
    nombre  = data.get('nombre', '').strip()
    valores = [v.strip() for v in data.get('valores', []) if str(v).strip()]
    if not nombre or not valores:
        return jsonify({'ok': False, 'error': 'Nombre y al menos un valor requeridos'}), 400
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        row = conn.execute(
            "INSERT INTO producto_atributos (producto_id, nombre) VALUES (%s, %s) RETURNING id",
            (producto_id, nombre)
        ).fetchone()
        atributo_id = row['id']
        for i, v in enumerate(valores):
            conn.execute("INSERT INTO atributo_valores (atributo_id, valor, orden) VALUES (%s,%s,%s)", (atributo_id, v, i))
        conn.commit()
        return jsonify({'ok': True, 'id': atributo_id})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/atributo/<int:atributo_id>', methods=['DELETE'])
def api_tienda_atributo_eliminar(slug, producto_id, atributo_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("DELETE FROM atributo_valores WHERE atributo_id = %s", (atributo_id,))
        conn.execute("DELETE FROM producto_atributos WHERE id = %s AND producto_id = %s", (atributo_id, producto_id))
        conn.execute("DELETE FROM producto_variantes WHERE producto_id = %s", (producto_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/generar-variantes', methods=['POST'])
def api_tienda_generar_variantes(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id, tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        producto = conn.execute(
            "SELECT id, precio FROM productos WHERE id = %s AND negocio_id = %s",
            (producto_id, tienda['tercero_id'])
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        atributos = conn.execute(
            "SELECT id, nombre FROM producto_atributos WHERE producto_id = %s ORDER BY orden, id",
            (producto_id,)
        ).fetchall()
        if not atributos:
            return jsonify({'ok': False, 'error': 'Define al menos un atributo primero'}), 400
        listas = []
        for a in atributos:
            valores = conn.execute(
                "SELECT valor FROM atributo_valores WHERE atributo_id = %s ORDER BY orden, id", (a['id'],)
            ).fetchall()
            listas.append((a['nombre'], [v['valor'] for v in valores]))
        existentes = conn.execute(
            "SELECT atributos, precio, disponible FROM producto_variantes WHERE producto_id = %s", (producto_id,)
        ).fetchall()
        existentes_map = {
            json.dumps(dict(e['atributos']), sort_keys=True): {'precio': float(e['precio']), 'disponible': e['disponible']}
            for e in existentes
        }
        conn.execute("DELETE FROM producto_variantes WHERE producto_id = %s", (producto_id,))
        nombres = [l[0] for l in listas]
        precio_base = float(producto['precio'])
        for combo in itertools.product(*[l[1] for l in listas]):
            atrs = dict(zip(nombres, combo))
            key  = json.dumps(atrs, sort_keys=True)
            prev = existentes_map.get(key, {})
            conn.execute(
                "INSERT INTO producto_variantes (producto_id, atributos, precio, disponible) VALUES (%s,%s,%s,%s)",
                (producto_id, json.dumps(atrs), prev.get('precio', precio_base), prev.get('disponible', True))
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/variante/<int:variante_id>', methods=['POST'])
def api_tienda_variante_editar(slug, producto_id, variante_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        campos, vals = [], []
        if 'precio' in data:
            campos.append('precio = %s')
            vals.append(float(data['precio']))
        if 'disponible' in data:
            campos.append('disponible = %s')
            vals.append(bool(data['disponible']))
        if not campos:
            return jsonify({'ok': False, 'error': 'Nada que actualizar'}), 400
        vals += [variante_id, producto_id]
        conn.execute(f"UPDATE producto_variantes SET {', '.join(campos)} WHERE id = %s AND producto_id = %s", vals)
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/imagenes')
def api_tienda_producto_imagenes(slug, producto_id):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        imgs = conn.execute(
            "SELECT id, imagen, orden FROM producto_imagenes WHERE producto_id = %s ORDER BY orden, id",
            (producto_id,)
        ).fetchall()
        return jsonify({'ok': True, 'imagenes': [dict(i) for i in imgs]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/imagen-extra', methods=['POST'])
def api_tienda_producto_imagen_extra(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    imagen = (request.get_json() or {}).get('imagen', '')
    if not imagen:
        return jsonify({'ok': False, 'error': 'Imagen requerida'}), 400
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        max_orden = conn.execute(
            "SELECT COALESCE(MAX(orden), -1) FROM producto_imagenes WHERE producto_id = %s", (producto_id,)
        ).fetchone()[0]
        row = conn.execute(
            "INSERT INTO producto_imagenes (producto_id, imagen, orden) VALUES (%s,%s,%s) RETURNING id",
            (producto_id, imagen, max_orden + 1)
        ).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/imagen-extra/<int:imagen_id>', methods=['DELETE'])
def api_tienda_producto_imagen_extra_eliminar(slug, producto_id, imagen_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("DELETE FROM producto_imagenes WHERE id = %s AND producto_id = %s", (imagen_id, producto_id))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Docs ───────────────────────────────────────────────────────────────────────


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/documentos')
def api_tienda_producto_documentos(slug, producto_id):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        producto = conn.execute(
            "SELECT id FROM productos WHERE id = %s AND negocio_id = %s",
            (producto_id, tienda['tercero_id'])
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        docs = conn.execute("""
            SELECT id, tipo, nombre, mime, visible_cliente, orden, created_at
            FROM producto_documentos
            WHERE producto_id = %s
            ORDER BY tipo = 'ficha_tecnica' DESC, orden, id
        """, (producto_id,)).fetchall()
        return jsonify({'ok': True, 'documentos': [{
            'id': d['id'],
            'tipo': d['tipo'],
            'nombre': d['nombre'],
            'mime': d['mime'],
            'visible_cliente': bool(d['visible_cliente']),
            'orden': d['orden'],
            'url': f'/api/tienda/{slug}/producto/{producto_id}/documento/{d["id"]}',
        } for d in docs]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/documento', methods=['POST'])
def api_tienda_producto_documento_subir(slug, producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    archivo = data.get('archivo') or ''
    nombre = (data.get('nombre') or 'Ficha tecnica.pdf').strip()
    mime = (data.get('mime') or 'application/pdf').strip()
    tipo = (data.get('tipo') or 'ficha_tecnica').strip()
    if not archivo:
        return jsonify({'ok': False, 'error': 'Archivo requerido'}), 400
    if mime != 'application/pdf':
        return jsonify({'ok': False, 'error': 'Por ahora solo PDF'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        producto = conn.execute(
            "SELECT id FROM productos WHERE id = %s AND negocio_id = %s",
            (producto_id, tienda['tercero_id'])
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        max_orden = conn.execute(
            "SELECT COALESCE(MAX(orden), -1) FROM producto_documentos WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        row = conn.execute("""
            INSERT INTO producto_documentos
                (producto_id, tipo, nombre, mime, archivo, visible_cliente, orden)
            VALUES (%s,%s,%s,%s,%s,TRUE,%s)
            RETURNING id
        """, (producto_id, tipo, nombre, mime, archivo, max_orden + 1)).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/documento/<int:documento_id>')
def api_tienda_producto_documento_ver(slug, producto_id, documento_id):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        doc = conn.execute("""
            SELECT d.nombre, d.mime, d.archivo
            FROM producto_documentos d
            JOIN productos p ON p.id = d.producto_id
            WHERE d.id = %s AND d.producto_id = %s AND p.negocio_id = %s
        """, (documento_id, producto_id, tienda['tercero_id'])).fetchone()
        if not doc:
            return jsonify({'ok': False, 'error': 'Documento no encontrado'}), 404
        archivo = doc['archivo'] or ''
        payload = archivo.split(',', 1)[1] if ',' in archivo else archivo
        contenido = base64.b64decode(payload)
        nombre = (doc['nombre'] or 'ficha-tecnica.pdf').replace('"', "'")
        return Response(
            contenido,
            mimetype=doc['mime'] or 'application/pdf',
            headers={'Content-Disposition': f'inline; filename="{nombre}"'}
        )
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/documento/<int:documento_id>', methods=['DELETE'])
def api_tienda_producto_documento_eliminar(slug, producto_id, documento_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        tienda = conn.execute("SELECT tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        conn.execute("""
            DELETE FROM producto_documentos d
            USING productos p
            WHERE d.id = %s AND d.producto_id = %s
              AND p.id = d.producto_id AND p.negocio_id = %s
        """, (documento_id, producto_id, tienda['tercero_id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/docs/tienda')
def docs_tienda():
    return render_template('docs_tienda.html')


@bp.route('/admin/docs/tienda')
def admin_docs_tienda():
    return render_template('docs_tienda_admin.html')
