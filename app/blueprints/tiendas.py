import base64
import itertools
import json
import random
import re
import secrets
import time
import unicodedata
import uuid
from datetime import date, timedelta

from flask import (Blueprint, Response, jsonify, make_response, redirect,
                   render_template, request, session, flash, url_for)

from ..db import get_db_connection
from ..dominios_negocio import resolver_slug_por_host
from ..visitas_publicas import (
    listar_visitas_publicas,
    registrar_visita_publica as _registrar_visita_generica,
    respuesta_con_visitante as _respuesta_con_visitante_generica,
)
from .auth import solo_admin
from .inventarios import _aplicar_tarjeta, _es_ensamble, _verificar_stock_pedido, _mov_directo, _recostear_producto, _sync_precio, _fecha_o_none
try:
    from .contabilidad import _ejecutar_asiento_automatico as _asiento_auto
    from .contabilidad import obtener_siguiente_consecutivo
except ImportError:
    _asiento_auto = None
    def obtener_siguiente_consecutivo(*args, **kwargs):
        return None, True

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
        """CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER,
            restaurante_id INTEGER,
            negocio_id INTEGER,
            tipo_documento_id INTEGER,
            numero_documento VARCHAR(50),
            id_cajero VARCHAR(50),
            nombre_cajero VARCHAR(100),
            id_tercero_cajero INTEGER,
            cliente_id INTEGER,
            nombre_cliente VARCHAR(100),
            telefono_cliente VARCHAR(20),
            direccion_cliente TEXT,
            tipo_entrega VARCHAR(20) DEFAULT 'domicilio',
            estado VARCHAR(20) DEFAULT 'nuevo',
            total DECIMAL(12,2) DEFAULT 0,
            subtotal_productos DECIMAL(12,2) DEFAULT 0,
            valor_domicilio DECIMAL(12,2) DEFAULT 0,
            domicilio_estado VARCHAR(30) DEFAULT 'no_aplica',
            cliente_lat DECIMAL(10,7),
            cliente_lon DECIMAL(10,7),
            notas TEXT,
            metodo_pago VARCHAR(20),
            comprobante_pago TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            
            -- Restaurantes
            mesa_num INTEGER,
            mesa_nombre VARCHAR(20),
            tipo VARCHAR(20),
            sopa_id INTEGER,
            proteina_id INTEGER,
            principio_id INTEGER,
            plato_id INTEGER,
            cantidad INTEGER DEFAULT 1,
            precio DECIMAL(12,2)
        )""",
        """CREATE TABLE IF NOT EXISTS pedido_items (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
            producto_id INTEGER NOT NULL,
            nombre_producto VARCHAR(255),
            cantidad INTEGER DEFAULT 1,
            precio_unitario DECIMAL(12,2) NOT NULL,
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
        """CREATE TABLE IF NOT EXISTS pedido_pagos (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
            metodo_codigo VARCHAR(50) NOT NULL,
            metodo_nombre VARCHAR(100) NOT NULL,
            monto DECIMAL(12,2) NOT NULL,
            recibido_con DECIMAL(12,2),
            devuelta DECIMAL(12,2),
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
        """CREATE TABLE IF NOT EXISTS tienda_experiencia_bloques (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL REFERENCES tiendas(id) ON DELETE CASCADE,
            tipo VARCHAR(20) NOT NULL,
            titulo VARCHAR(180),
            texto TEXT,
            media JSONB DEFAULT '[]'::jsonb,
            activo BOOLEAN DEFAULT TRUE,
            orden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
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
        """CREATE TABLE IF NOT EXISTS producto_fichas_solares (
            producto_id INTEGER PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
            tipo VARCHAR(40) NOT NULL DEFAULT '',
            datos JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS proyectos_solares (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL REFERENCES tiendas(id) ON DELETE CASCADE,
            cliente_id INTEGER REFERENCES terceros(id),
            cliente_nombre VARCHAR(255),
            cliente_telefono VARCHAR(30),
            ubicacion VARCHAR(255),
            escenario VARCHAR(255),
            tipo_sistema VARCHAR(40),
            datos_tecnicos JSONB DEFAULT '{}'::jsonb,
            presupuesto JSONB DEFAULT '{}'::jsonb,
            total NUMERIC(14,2) DEFAULT 0,
            estado VARCHAR(30) DEFAULT 'borrador',
            asesoria_pagada BOOLEAN DEFAULT FALSE,
            pdf_habilitado BOOLEAN DEFAULT FALSE,
            token_publico VARCHAR(80) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS tienda_visitantes_publicos (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL REFERENCES tiendas(id) ON DELETE CASCADE,
            visitante_token VARCHAR(80) NOT NULL,
            usuario_id INTEGER,
            primer_path TEXT,
            ultimo_path TEXT,
            user_agent TEXT,
            ip_primera VARCHAR(80),
            ip_ultima VARCHAR(80),
            visitas INTEGER DEFAULT 1,
            first_seen TIMESTAMP DEFAULT NOW(),
            last_seen TIMESTAMP DEFAULT NOW(),
            UNIQUE(tienda_id, visitante_token)
        )""",
        """CREATE TABLE IF NOT EXISTS tienda_visitas_publicas (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL REFERENCES tiendas(id) ON DELETE CASCADE,
            visitante_id INTEGER REFERENCES tienda_visitantes_publicos(id) ON DELETE SET NULL,
            usuario_id INTEGER,
            proyecto_id INTEGER,
            tipo VARCHAR(40),
            path TEXT,
            referrer TEXT,
            ip VARCHAR(80),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT NOW()
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
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20) DEFAULT 'efectivo'",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS subtotal_productos NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS valor_domicilio NUMERIC(12,2) DEFAULT 0",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS domicilio_estado VARCHAR(30) DEFAULT 'no_aplica'",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS cliente_lat NUMERIC(10,7)",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS cliente_lon NUMERIC(10,7)",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS id_cajero VARCHAR(50)",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS nombre_cajero VARCHAR(100)",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS id_tercero_cajero INTEGER REFERENCES terceros(id)",
        "ALTER TABLE tienda_cajeros ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id)",
        "CREATE INDEX IF NOT EXISTS idx_catalogo_productos_codigo ON catalogo_productos(codigo_barra)",
        "CREATE INDEX IF NOT EXISTS idx_tienda_cajeros_tienda ON tienda_cajeros(tienda_id)",
        "ALTER TABLE metodos_pago_tienda ALTER COLUMN nombre DROP NOT NULL",
        "ALTER TABLE metodos_pago_tienda ALTER COLUMN codigo DROP NOT NULL",
        "ALTER TABLE pedido_pagos ADD COLUMN IF NOT EXISTS recibido_con NUMERIC(12,2)",
        "ALTER TABLE pedido_pagos ADD COLUMN IF NOT EXISTS devuelta NUMERIC(12,2)",
        "UPDATE tiendas SET tercero_id = admin_id WHERE tercero_id IS NULL AND admin_id IS NOT NULL",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS desktop_layout VARCHAR(20) DEFAULT 'movil'",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS movil_cols SMALLINT DEFAULT 2",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS pantalla_experiencial BOOLEAN DEFAULT FALSE",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS color_accion VARCHAR(20) DEFAULT '#e11d48'",
        "ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS imagen_header_movil TEXT",
        "CREATE INDEX IF NOT EXISTS idx_cotizaciones_tienda ON cotizaciones_tienda(tienda_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_cot_items_cotizacion ON cotizacion_items_tienda(cotizacion_id)",
        "CREATE INDEX IF NOT EXISTS idx_producto_documentos_producto ON producto_documentos(producto_id)",
        "CREATE INDEX IF NOT EXISTS idx_producto_fichas_solares_tipo ON producto_fichas_solares(tipo)",
        "ALTER TABLE proyectos_solares ADD COLUMN IF NOT EXISTS cliente_id INTEGER REFERENCES terceros(id)",
        "ALTER TABLE proyectos_solares ADD COLUMN IF NOT EXISTS asesoria_pagada BOOLEAN DEFAULT FALSE",
        "ALTER TABLE proyectos_solares ADD COLUMN IF NOT EXISTS pdf_habilitado BOOLEAN DEFAULT FALSE",
        "CREATE INDEX IF NOT EXISTS idx_proyectos_solares_tienda ON proyectos_solares(tienda_id, updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_proyectos_solares_cliente ON proyectos_solares(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_tienda_visitantes_publicos_tienda ON tienda_visitantes_publicos(tienda_id, last_seen DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tienda_visitas_publicas_tienda ON tienda_visitas_publicas(tienda_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tienda_visitas_publicas_proyecto ON tienda_visitas_publicas(proyecto_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tienda_experiencia_bloques ON tienda_experiencia_bloques(tienda_id, orden, id)",
        "ALTER TABLE metodos_pago_catalogo ADD COLUMN IF NOT EXISTS grupo VARCHAR(30)",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS comprobante_pago TEXT",
        "INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo) VALUES ('Nequi QR', 'nequi_qr', '📲', 21, 'nequi') ON CONFLICT (codigo) DO NOTHING",
        "INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo) VALUES ('Nequi Celular', 'nequi_movil', '📱', 22, 'nequi') ON CONFLICT (codigo) DO NOTHING",
        "INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo) VALUES ('Bancolombia QR', 'bancolombia_qr', '🏦', 31, 'bancolombia') ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre, icono = EXCLUDED.icono, orden = EXCLUDED.orden, grupo = EXCLUDED.grupo, activo = TRUE",
        "INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, orden, grupo) VALUES ('Llave bancaria', 'llave', '🔑', 32, NULL) ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre, icono = EXCLUDED.icono, orden = EXCLUDED.orden, grupo = EXCLUDED.grupo, activo = TRUE",
        "UPDATE metodos_pago_catalogo SET nombre = 'Contraentrega en efectivo' WHERE codigo = 'contraentrega'",
        "UPDATE metodos_pago_catalogo SET grupo = 'nequi' WHERE codigo = 'nequi' AND grupo IS NULL",
        "UPDATE metodos_pago_catalogo SET activo = FALSE WHERE codigo = 'nequi'",
        """UPDATE config_negocio SET metodos_pago = array_replace(metodos_pago, 'nequi', 'nequi_movil') WHERE 'nequi' = ANY(metodos_pago)""",
        "CREATE SEQUENCE IF NOT EXISTS pedidos_id_seq",
        "ALTER TABLE pedidos ALTER COLUMN id SET DEFAULT nextval('pedidos_id_seq')",
        "ALTER SEQUENCE pedidos_id_seq OWNED BY pedidos.id",
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


def _enviar_telegram_tienda(*args):
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
        import os
        import requests as req
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
                print(f'[telegram tienda] token CONFIGURACION_SISTEMA no disponible: {_e}')
                try:
                    config = conn.execute(
                        "SELECT telegram_token FROM configuracion_sistema WHERE id = 1"
                    ).fetchone()
                    if config:
                        try:
                            token = config['telegram_token'] or ''
                        except Exception:
                            token = config[0] or ''
                except Exception as _e2:
                    print(f'[telegram tienda] token config no disponible: {_e2}')
        token = token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if not token:
            print('[telegram tienda] sin token configurado')
            return
        resp = req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'},
            timeout=10
        )
        if resp.status_code >= 400:
            print(f'[telegram tienda] error {resp.status_code}: {resp.text[:200]}')
    except Exception as _e:
        print(f'[telegram tienda] envio fallido: {_e}')


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
        detalle = f"{nombre}: ${float(pago.get('monto') or 0):,.0f}"
        try:
            recibido = float(pago.get('recibido_con') or 0)
            devuelta = float(pago.get('devuelta') or max(0, recibido - float(pago.get('monto') or 0)))
        except (TypeError, ValueError):
            recibido, devuelta = 0, 0
        if codigo.lower() in ('efectivo', 'contraentrega') and recibido > 0:
            detalle += f" | recibe con ${recibido:,.0f}"
            if devuelta >= 0:
                detalle += f" | devuelta ${devuelta:,.0f}"
        partes.append(detalle)
    alerta = "\n⚠️ Contraentrega: cobrar efectivo al entregar." if contraentrega else ""
    return ' + '.join(partes) + alerta


def _telegram_detalle_entrega_tienda(tipo_entrega, direccion, nombre_cajero):
    if tipo_entrega == 'domicilio':
        return f"Domicilio. Llevar a: {direccion or 'direccion pendiente'}"
    if tipo_entrega == 'caja':
        return f"Entrega en el local / caja. Atendio: {nombre_cajero or 'caja'}"
    if tipo_entrega == 'recoger':
        return "Cliente recoge en el local."
    return f"{tipo_entrega or 'Pedido'}: {direccion or 'N/A'}"


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


def _ip_cliente():
    reenviada = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return reenviada or request.remote_addr or ''


def _registrar_visita_publica(conn, tienda_id, tipo='tienda', proyecto_id=None):
    titulos = {
        'tienda': 'Portada de tienda',
        'proyecto_solar': 'Propuesta solar',
        'proyecto_solar_pdf': 'PDF tecnico de propuesta solar',
        'proyecto_solar_pdf_bloqueado': 'PDF tecnico bloqueado',
    }
    return _registrar_visita_generica(
        conn,
        'tienda',
        tienda_id,
        recurso_tipo=tipo,
        recurso_id=proyecto_id,
        titulo=titulos.get(tipo, tipo),
    )


def _respuesta_con_visitante(response, visita):
    return _respuesta_con_visitante_generica(response, visita)


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
                "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos WHERE tienda_id = %s",
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
        visita = _registrar_visita_generica(
            conn,
            'tienda',
            tienda['id'],
            recurso_tipo='portada',
            titulo=f"Portada de tienda: {tienda['nombre']}",
        )
        bloques_experiencia = []
        if tienda['pantalla_experiencial']:
            bloques = conn.execute("""
                SELECT id, tipo, titulo, texto, media, activo, orden
                FROM tienda_experiencia_bloques
                WHERE tienda_id = %s AND activo = TRUE
                ORDER BY orden, id
            """, (tienda['id'],)).fetchall()
            for b in bloques:
                item = dict(b)
                item['media'] = item.get('media') or []
                bloques_experiencia.append(item)
        response = make_response(render_template(
            'tienda_cliente.html',
            tienda=tienda,
            cliente_data=cliente_data,
            bloques_experiencia=bloques_experiencia,
        ))
        return _respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


# ── Caja POS Genérica ──────────────────────────────────────────────────────────

def _obtener_negocio_por_slug(conn, slug):
    tienda = conn.execute(
        "SELECT id, nombre, 'tienda' as tipo_negocio, tercero_id, color_primario, imagen_header, telegram_chat_id, admin_id, token_acceso FROM tiendas WHERE slug = %s AND activo = TRUE", (slug,)
    ).fetchone()
    if tienda:
        return dict(tienda)
    restaurante = conn.execute(
        "SELECT id, nombre, 'restaurante' as tipo_negocio, tercero_id, NULL as color_primario, NULL as imagen_header, NULL as telegram_chat_id, admin_id, token_acceso FROM restaurantes WHERE slug = %s AND activo = TRUE", (slug,)
    ).fetchone()
    if restaurante:
        res = dict(restaurante)
        res['color_primario'] = '#e11d48'
        res['imagen_header'] = None
        return res
    return None

@bp.route('/caja/<slug>')
@bp.route('/tienda/<slug>/caja')
def tienda_caja(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return "Negocio no encontrado", 404
        return render_template('caja.html', tienda=negocio, slug=slug)
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()

@bp.route('/admin/caja/<slug>')
@bp.route('/admin/tienda/<slug>/caja')
def admin_tienda_caja(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return "Negocio no encontrado", 404
        
        uid = session.get('usuario_id')
        es_admin_sistema = session.get('rol') == 'Administrador'
        tok_tienda = session.get('tienda_token')
        tok_rest = session.get('restaurante_token')
        
        es_dueno = False
        if uid and uid == negocio['admin_id']:
            es_dueno = True
        elif negocio['tipo_negocio'] == 'tienda' and tok_tienda and tok_tienda == negocio.get('token_acceso'):
            es_dueno = True
        elif negocio['tipo_negocio'] == 'restaurante' and tok_rest and tok_rest == negocio.get('token_acceso'):
            es_dueno = True

        if not (es_admin_sistema or es_dueno):
            flash('Acceso denegado. Se requiere ser administrador o dueño del negocio.', 'danger')
            return redirect(url_for('auth.admin_login'))
            
        return render_template('caja.html', tienda=negocio, slug=slug, modo_admin=True)
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()

@bp.route('/caja/<slug>/cliente/<token>')
@bp.route('/tienda/<slug>/caja/cliente/<token>')
def tienda_caja_cliente(slug, token):
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return "Negocio no encontrado", 404
        return render_template('caja_cliente.html', tienda=negocio, slug=slug, token=token)
    finally:
        conn.close()

@bp.route('/api/caja/<slug>/sesion', methods=['POST'])
@bp.route('/api/tienda/<slug>/caja/sesion', methods=['POST'])
def api_tienda_caja_sesion_crear(slug):
    _limpiar_sesiones_caja()
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404

        token = secrets.token_urlsafe(18)
        update_key = secrets.token_urlsafe(24)
        ahora = time.time()
        _sesiones_caja_cliente[token] = {
            'slug': slug,
            'tienda_id': negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
            'restaurante_id': negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None,
            'tienda_nombre': negocio['nombre'],
            'update_key': update_key,
            'estado': 'activa',
            'items': [],
            'recibo': None,
            'total': 0,
            'iva': 0,
            'updated_at': ahora,
            'created_at': ahora,
        }
        return jsonify({'ok': True, 'token': token, 'update_key': update_key, 'url': f'/caja/{slug}/cliente/{token}'})
    finally:
        conn.close()


@bp.route('/api/caja/<slug>/sesion/<token>', methods=['GET', 'POST'])
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
            "SELECT id, nombre, descripcion, precio, imagen FROM productos WHERE id = %s AND negocio_id = (SELECT tercero_id FROM tiendas WHERE id = %s) AND disponible = TRUE AND precio > 0",
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
        visita = _registrar_visita_generica(
            conn,
            'tienda',
            tienda['id'],
            recurso_tipo='producto_compartido',
            recurso_id=producto['id'],
            titulo=f"Producto compartido: {producto['nombre']}",
            detalle=txt or None,
        )
        response = make_response(render_template('promo_tienda.html',
            tienda=tienda, producto=producto, tiene_imagen=tiene_imagen,
            mostrar_foto=mostrar_foto, mostrar_precio=mostrar_precio, mostrar_desc=mostrar_desc,
            txt=txt, leyenda=leyenda))
        return _respuesta_con_visitante(response, visita)
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

@bp.route('/api/caja/<slug>/productos')
@bp.route('/api/tienda/<slug>/productos')
def api_tienda_productos(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        solo_publicos = request.args.get('publico') == '1'
        filtro_publico = " AND disponible = TRUE AND precio > 0" if solo_publicos else ""
        productos = conn.execute(
            "SELECT id, nombre, categoria, precio, costo, imagen, disponible, orden, descripcion, codigo_barra, catalogo_id, iva_pct "
            f"FROM productos WHERE negocio_id = %s{filtro_publico} ORDER BY categoria, orden, nombre",
            (negocio['tercero_id'],)
        ).fetchall()
        
        media_por_categoria = {}
        if negocio['tipo_negocio'] == 'tienda':
            categorias_media = conn.execute(
                """
                SELECT categoria, imagen
                FROM tienda_categorias
                WHERE tienda_id = %s
                """,
                (negocio['id'],)
            ).fetchall()
            media_por_categoria = {c['categoria']: c['imagen'] for c in categorias_media}
        # Bulk queries to optimize database connections and prevent OS thrashing
        p_ids = [p['id'] for p in productos]
        nv_dict = {}
        nf_dict = {}
        nd_dict = {}
        doc_dict = {}

        if p_ids:
            # 1. Variants count
            nv_rows = conn.execute(
                "SELECT producto_id, COUNT(*) as cnt FROM producto_variantes WHERE producto_id IN %s GROUP BY producto_id",
                (tuple(p_ids),)
            ).fetchall()
            nv_dict = {r['producto_id']: r['cnt'] for r in nv_rows}

            # 2. Images count
            nf_rows = conn.execute(
                "SELECT producto_id, COUNT(*) as cnt FROM producto_imagenes WHERE producto_id IN %s GROUP BY producto_id",
                (tuple(p_ids),)
            ).fetchall()
            nf_dict = {r['producto_id']: r['cnt'] for r in nf_rows}

            # 3. Documents count
            nd_rows = conn.execute(
                "SELECT producto_id, COUNT(*) as cnt FROM producto_documentos WHERE producto_id IN %s GROUP BY producto_id",
                (tuple(p_ids),)
            ).fetchall()
            nd_dict = {r['producto_id']: r['cnt'] for r in nd_rows}

            # 4. First visible document per product
            doc_rows = conn.execute(
                "SELECT DISTINCT ON (producto_id) producto_id, id, nombre "
                "FROM producto_documentos "
                "WHERE producto_id IN %s AND visible_cliente = TRUE "
                "ORDER BY producto_id, tipo = 'ficha_tecnica' DESC, orden, id",
                (tuple(p_ids),)
            ).fetchall()
            doc_dict = {r['producto_id']: {'id': r['id'], 'nombre': r['nombre']} for r in doc_rows}

        resultado = []
        for p in productos:
            pid = p['id']
            nv = nv_dict.get(pid, 0)
            nf = nf_dict.get(pid, 0)
            nd = nd_dict.get(pid, 0)
            doc = doc_dict.get(pid)
            resultado.append({
                'id': pid, 'nombre': p['nombre'], 'categoria': p['categoria'] or '',
                'precio': float(p['precio']), 'costo': float(p['costo'] or 0), 'imagen': p['imagen'] or '',
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
            _sync_precio(conn, tienda['tercero_id'], producto_id)
        else:
            row = conn.execute(
                "INSERT INTO productos (negocio_id, nombre, categoria, precio, descripcion, catalogo_id, codigo_barra, iva_pct) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (tienda['tercero_id'], nombre, categoria, precio, descripcion or None, catalogo_id, codigo_barra, iva_pct)
            ).fetchone()
            nuevo_id = row['id']
            _sync_precio(conn, tienda['tercero_id'], nuevo_id)
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
        conn.execute("INSERT INTO productos (negocio_id, nombre, categoria, precio) VALUES (%s,%s,%s,0) RETURNING id", (tienda['tercero_id'], nombre, categoria))
        nuevo_id = conn.fetchone()[0]
        _sync_precio(conn, tienda['tercero_id'], nuevo_id)
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


@bp.route('/api/tienda/<slug>/experiencia-bloques', methods=['GET', 'PUT'])
def api_tienda_experiencia_bloques(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        if request.method == 'GET':
            rows = conn.execute("""
                SELECT id, tipo, titulo, texto, media, activo, orden
                FROM tienda_experiencia_bloques
                WHERE tienda_id = %s
                ORDER BY orden, id
            """, (tienda['id'],)).fetchall()
            return jsonify({'ok': True, 'bloques': [dict(r) for r in rows]})

        data = request.get_json() or {}
        bloques = data.get('bloques') or []
        if not isinstance(bloques, list):
            return jsonify({'ok': False, 'error': 'Formato invalido'}), 400
        bloques = bloques[:12]
        tipos_validos = {'video', 'collage', 'galeria', 'texto'}
        conn.execute("DELETE FROM tienda_experiencia_bloques WHERE tienda_id = %s", (tienda['id'],))
        for idx, bloque in enumerate(bloques):
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
                INSERT INTO tienda_experiencia_bloques
                    (tienda_id, tipo, titulo, texto, media, activo, orden)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)
            """, (tienda['id'], tipo, titulo, texto, json.dumps(media), activo, idx))
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
            "UPDATE pedidos SET comprobante_pago=%s WHERE id=%s AND tienda_id=%s",
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
        tienda = conn.execute("""
            SELECT id, nombre, admin_id, tercero_id, token_acceso
            FROM tiendas
            WHERE slug=%s AND activo=TRUE
        """, (slug,)).fetchone()
        token_ok = session.get('tienda_token') and tienda and session.get('tienda_token') == tienda['token_acceso']
        autorizado = (
            tienda and (
                es_admin
                or uid == tienda['admin_id']
                or uid == tienda['tercero_id']
                or token_ok
            )
        )
        if not autorizado:
            return jsonify({'ok': False, 'error': 'Sin acceso'}), 403
        if not tienda['tercero_id'] and tienda['admin_id']:
            conn.execute("UPDATE tiendas SET tercero_id=%s WHERE id=%s", (tienda['admin_id'], tienda['id']))
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


@bp.route('/api/caja/<slug>/registrar-cliente-pos', methods=['POST'])
@bp.route('/api/tienda/<slug>/caja/registrar-cliente-pos', methods=['POST'])
def api_caja_registrar_cliente_pos(slug):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    nombre = data.get('nombre', '').strip()
    telefono = ''.join(filter(str.isdigit, data.get('telefono', '')))
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        row_t = None
        if telefono and len(telefono) >= 7:
            row_t = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono,)).fetchone()
        if not row_t:
            row_t = conn.execute("SELECT id FROM terceros WHERE LOWER(nombre) = LOWER(%s) LIMIT 1", (nombre,)).fetchone()
        if row_t:
            cliente_id = row_t['id']
            if telefono:
                conn.execute("UPDATE terceros SET telefono = %s WHERE id = %s", (telefono, cliente_id))
        else:
            row_ins = conn.execute("""
                INSERT INTO terceros (nombre, telefono, tipo_tercero, fecha_creacion)
                VALUES (%s, %s, 'cliente', NOW())
                RETURNING id
            """, (nombre, telefono or None)).fetchone()
            cliente_id = row_ins['id']
        conn.commit()
        return jsonify({'ok': True, 'cliente_id': cliente_id})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
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


@bp.route('/api/caja/<slug>/pedido', methods=['POST'])
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
    cliente_lat      = data.get('cliente_lat')
    cliente_lon      = data.get('cliente_lon')
    items            = data.get('items', [])
    id_cajero        = data.get('id_cajero')
    nombre_cajero    = data.get('nombre_cajero', '').strip() or None
    id_tercero_cajero = data.get('id_tercero_cajero')
    pedido_premontado_id = data.get('pedido_premontado_id')
    fecha_raw        = (data.get('fecha') or '').strip()
    fecha_pedido     = _fecha_o_none(fecha_raw) or date.today()
    if not items:
        return jsonify({'ok': False, 'error': 'El carrito esta vacio'}), 400
    if not nombre_cliente and tipo_entrega != 'caja':
        return jsonify({'ok': False, 'error': 'Nombre requerido'}), 400
    if fecha_pedido > date.today():
        return jsonify({'ok': False, 'error': 'La fecha de la venta no puede ser futura'}), 400

    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        
        if negocio.get('tercero_id'):
            try:
                from .contabilidad import _verificar_periodo_cerrado
                _verificar_periodo_cerrado(conn, negocio['tercero_id'], fecha_pedido)
            except Exception as exc:
                return jsonify({'ok': False, 'error': str(exc)}), 400

        tienda = negocio
        telegram_chat_id = negocio['telegram_chat_id']
        fecha_vence = None
        admin_id = negocio['admin_id']

        if negocio['tipo_negocio'] == 'tienda':
            tienda = conn.execute(
                "SELECT id, nombre, dias_pagados, telegram_chat_id, fecha_vence, tercero_id, admin_id FROM tiendas WHERE id = %s",
                (negocio['id'],)
            ).fetchone()
            telegram_chat_id = tienda['telegram_chat_id']
            fecha_vence = tienda['fecha_vence']
            admin_id = tienda['admin_id']
        else:
            restaurante = conn.execute(
                "SELECT id, nombre, admin_id, token_acceso FROM restaurantes WHERE id = %s",
                (negocio['id'],)
            ).fetchone()
            admin_id = restaurante['admin_id']

        if fecha_vence and date.today() > fecha_vence:
            return jsonify({'ok': False, 'error': 'suscripcion_agotada', 'fecha_vence': str(fecha_vence)}), 402
        total = 0
        items_validos = []
        for item in items:
            producto = conn.execute(
                "SELECT id, nombre, precio, disponible, iva_pct FROM productos "
                "WHERE id = %s AND negocio_id = %s AND disponible = TRUE AND precio > 0",
                (item.get('producto_id'), negocio['tercero_id'])
            ).fetchone()
            if not producto:
                continue
            cantidad  = max(1, int(item.get('cantidad', 1)))
            
            # Allow custom unit price if passed from POS client
            precio_unitario_client = item.get('precio_unitario')
            if precio_unitario_client is not None:
                try:
                    precio_u = float(precio_unitario_client)
                    if precio_u < 0:
                        precio_u = float(producto['precio'])
                except (ValueError, TypeError):
                    precio_u = float(producto['precio'])
            else:
                precio_u = float(producto['precio'])
                
            total    += precio_u * cantidad
            items_validos.append({
                'producto_id': producto['id'], 'nombre_producto': producto['nombre'],
                'cantidad': cantidad, 'precio_unitario': precio_u,
                'iva_pct': float(producto['iva_pct'] or 0)
            })
        if not items_validos:
            return jsonify({'ok': False, 'error': 'Ningun producto valido en el carrito'}), 400
            
        # Consecutivo de tipo de documento usando el motor global (resuelto antes del chequeo de stock para vincular ajustes)
        tipo_doc_id = data.get('tipo_documento_id')
        if not tipo_doc_id:
            # Fallback to predeterminado document type of type 'venta'
            default_doc = conn.execute(
                "SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND activo = TRUE AND predeterminado = TRUE AND tipo_movimiento = 'venta' LIMIT 1",
                (negocio['tercero_id'],)
            ).fetchone()
            if default_doc:
                tipo_doc_id = default_doc['id']
            else:
                # Fallback to first active document of type 'venta'
                any_doc = conn.execute(
                    "SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND activo = TRUE AND tipo_movimiento = 'venta' ORDER BY id LIMIT 1",
                    (negocio['tercero_id'],)
                ).fetchone()
                if any_doc:
                    tipo_doc_id = any_doc['id']

        numero_documento = None
        res_num = None
        tipo_doc_codigo = None
        if tipo_doc_id:
            tipo_doc = conn.execute(
                "SELECT id, codigo, nombre FROM tipos_documento_negocio WHERE id = %s AND negocio_id = %s",
                (tipo_doc_id, negocio['tercero_id'])
            ).fetchone()
            if tipo_doc:
                res_num, es_interno = obtener_siguiente_consecutivo(conn, negocio['tercero_id'], tipo_doc['id'])
                if res_num:
                    tipo_doc_codigo = tipo_doc['codigo'] or 'DOC'
                    try:
                        numero_documento = f"{tipo_doc_codigo}-{int(res_num)}"
                    except (ValueError, TypeError):
                        numero_documento = f"{tipo_doc_codigo}-{res_num}"

        # Procesar ajustes en caliente antes de validar el stock
        adjustments = data.get('adjustments') or []
        applied_adjustments = False
        if adjustments:
            for adj in adjustments:
                prod_id = int(adj.get('producto_id') or 0)
                qty_physical = float(adj.get('cantidad_fisica') or 0.0)
                cost_unit = float(adj.get('costo_unitario') or 0.0)
                if not prod_id:
                    continue
                
                # Obtener stock en base de datos
                saldo = conn.execute(
                    "SELECT stock FROM saldos_inventario WHERE negocio_id = %s AND producto_id = %s AND bodega = 1",
                    (negocio['tercero_id'], prod_id)
                ).fetchone()
                qty_system = float(saldo['stock'] if saldo else 0.0)
                diff = qty_physical - qty_system
                if abs(diff) < 0.000001:
                    continue
                
                # Registrar el movimiento de ajuste con los datos de la factura
                _mov_directo(
                    conn, negocio['tercero_id'], prod_id, abs(diff), 'entrada' if diff > 0 else 'salida', 'ajuste',
                    registrado_por=session.get('usuario_id'),
                    valor_unitario=cost_unit,
                    bodega=1,
                    tipo_documento=tipo_doc_codigo or 'Factura de Venta',
                    documento_numero=numero_documento,
                    documento_fecha=fecha_pedido,
                    tipo_documento_id=tipo_doc_id,
                    referencia_tipo='pedido_tienda'
                )
                
                # Recostear inmediatamente para actualizar el costo promedio en el balance antes de la venta
                _recostear_producto(conn, negocio['tercero_id'], prod_id)
                applied_adjustments = True

        force_negative = data.get('force_negative_stock') == True
        excluir_componentes = data.get('excluir_componentes') or []
        if not force_negative:
            shortages = _verificar_stock_pedido(conn, negocio['tercero_id'], items_validos, excluir_componentes)
            if shortages:
                conn.close()
                return jsonify({'ok': False, 'error': 'insufficient_stock', 'shortages': shortages}), 400
                
        subtotal_productos = total
        tercero_config_id = negocio['tercero_id'] or admin_id
        valor_domicilio, domicilio_estado = _calcular_domicilio(
            conn, tercero_config_id, tipo_entrega, cliente_lat, cliente_lon
        )
        if domicilio_estado == 'fuera_cobertura':
            return jsonify({'ok': False, 'error': 'La direccion esta fuera de cobertura de domicilio'}), 400
        total = subtotal_productos + float(valor_domicilio or 0)
        
        # Consecutivo ya resuelto al inicio del flujo

        # Resolve or create client in terceros if not provided but name is typed
        crear_cliente_flag = data.get('crear_cliente', True)
        if not cliente_id and nombre_cliente:
            nombre_clean = nombre_cliente.strip()
            # Avoid creating third party for generic names
            generic_names = ('venta en caja', 'mostrador', 'anonimo', 'cliente general', 'cliente en local', 'consumo')
            if nombre_clean.lower() not in generic_names:
                telefono_clean = ''.join(filter(str.isdigit, telefono_cliente or ''))
                row_t = None
                if telefono_clean and len(telefono_clean) >= 7:
                    row_t = conn.execute("SELECT id FROM terceros WHERE telefono = %s LIMIT 1", (telefono_clean,)).fetchone()
                
                if not row_t:
                    row_t = conn.execute("SELECT id FROM terceros WHERE LOWER(nombre) = LOWER(%s) LIMIT 1", (nombre_clean,)).fetchone()
                
                if row_t:
                    cliente_id = row_t['id']
                elif crear_cliente_flag:
                    # Create new cliente in terceros
                    row_ins = conn.execute("""
                        INSERT INTO terceros (nombre, telefono, tipo_tercero, fecha_creacion)
                        VALUES (%s, %s, 'cliente', NOW())
                        RETURNING id
                    """, (nombre_clean, telefono_clean or None)).fetchone()
                    cliente_id = row_ins['id']

        # Fallback to Tercero Ocasional if still no cliente_id is resolved
        if not cliente_id:
            row_ocasional = conn.execute("SELECT id FROM terceros WHERE LOWER(nombre) = 'tercero ocasional' LIMIT 1").fetchone()
            if row_ocasional:
                cliente_id = row_ocasional['id']
                if not nombre_cliente:
                    nombre_cliente = "Tercero Ocasional"
            else:
                row_ins = conn.execute("""
                    INSERT INTO terceros (nombre, tipo_tercero, fecha_creacion)
                    VALUES ('Tercero Ocasional', 'cliente', NOW())
                    RETURNING id
                """).fetchone()
                cliente_id = row_ins['id']
                if not nombre_cliente:
                    nombre_cliente = "Tercero Ocasional"

        conn.execute("""
            INSERT INTO pedidos
                (tienda_id, restaurante_id, negocio_id, cliente_id, nombre_cliente, telefono_cliente, direccion_cliente,
                 tipo_entrega, total, notas, metodo_pago, id_cajero, nombre_cajero, id_tercero_cajero,
                 subtotal_productos, valor_domicilio, domicilio_estado, cliente_lat, cliente_lon,
                 tipo_documento_id, numero_documento)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
            negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None,
            negocio['tercero_id'], cliente_id, nombre_cliente or None, telefono_cliente or None,
            direccion_cliente or None, tipo_entrega, total, notas or None, metodo_pago,
            id_cajero, nombre_cajero, id_tercero_cajero, subtotal_productos,
            float(valor_domicilio or 0), domicilio_estado, cliente_lat, cliente_lon,
            tipo_doc_id, numero_documento
        ))
        pedido_id = conn.execute(
            "SELECT currval(pg_get_serial_sequence('pedidos', 'id'))"
        ).fetchone()[0]
        
        # Enlazar los ajustes aplicados al ID del pedido
        if applied_adjustments:
            conn.execute("""
                UPDATE movimientos_inventario
                SET referencia_id = %s
                WHERE negocio_id = %s AND documento_numero = %s AND motivo = 'ajuste' AND referencia_id IS NULL
            """, (pedido_id, negocio['tercero_id'], numero_documento))

        for it in items_validos:
            # Query the unit cost of the product right now
            costo_row = conn.execute("""
                SELECT COALESCE(
                    -- 1. Recipe product: sum of standard recipe components cost
                    (SELECT SUM(t.cantidad * COALESCE(s.costo_und, p_comp.costo, 0))
                     FROM tarjeta_estandar t
                     JOIN productos p_comp ON p_comp.id = t.componente_id
                     LEFT JOIN saldos_inventario s ON s.producto_id = t.componente_id AND s.negocio_id = %s AND s.bodega = 1
                     WHERE t.producto_id = %s
                     HAVING COUNT(*) > 0),
                    -- 2. Simple product
                    (SELECT COALESCE(s.costo_und, p.costo, 0)
                     FROM productos p
                     LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.negocio_id = %s AND s.bodega = 1
                     WHERE p.id = %s)
                ) AS costo_real
            """, (negocio['tercero_id'], it['producto_id'], negocio['tercero_id'], it['producto_id'])).fetchone()
            costo_u = float(costo_row['costo_real']) if (costo_row and costo_row['costo_real'] is not None) else 0.0

            conn.execute("""
                INSERT INTO pedido_items (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, costo_unitario)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (pedido_id, it['producto_id'], it['nombre_producto'], it['cantidad'], it['precio_unitario'], costo_u))
            if negocio['tercero_id']:
                excluded_ids = [
                    int(exc['componente_id']) 
                    for exc in excluir_componentes 
                    if int(exc.get('producto_id') or 0) == it['producto_id']
                ]
                try:
                    conn.execute("SAVEPOINT sp_inv_tienda")
                    _aplicar_tarjeta(
                        conn, negocio['tercero_id'],
                        producto_id    = it['producto_id'],
                        cantidad       = it['cantidad'],
                        tipo           = 'salida',
                        motivo         = 'venta',
                        registrado_por = session.get('usuario_id'),
                        referencia_id  = pedido_id,
                        referencia_tipo= 'pedido_tienda',
                        tipo_documento = tipo_doc['nombre'] if (tipo_doc_id and tipo_doc) else 'Venta POS',
                        documento_numero = numero_documento or str(pedido_id),
                        documento_fecha = fecha_pedido,
                        proveedor_nombre = nombre_cliente or None,
                        tipo_documento_id = tipo_doc_id,
                        excluir_componentes_ids = excluded_ids,
                        proveedor_id   = cliente_id
                    )
                    conn.execute("RELEASE SAVEPOINT sp_inv_tienda")
                except Exception as _e:
                    print(f'[inv] salida tienda {it["producto_id"]}: {_e}')
                    try: conn.execute("ROLLBACK TO SAVEPOINT sp_inv_tienda")
                    except: pass
        pagos_validos = [p for p in pagos if isinstance(p, dict) and float(p.get('monto') or 0) > 0]
        if pagos_validos:
            for p in pagos_validos:
                codigo_pago = (p.get('codigo') or '').strip().lower()
                recibido_con = None
                devuelta = None
                if codigo_pago in ('efectivo', 'contraentrega'):
                    recibido_con = float(p.get('recibido_con') or 0) or None
                    if recibido_con:
                        devuelta = max(0, recibido_con - float(p.get('monto') or 0))
                conn.execute("""
                    INSERT INTO pedido_pagos
                        (pedido_id, metodo_codigo, metodo_nombre, monto, recibido_con, devuelta)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (pedido_id, p['codigo'], p.get('nombre', p['codigo']), float(p['monto']), recibido_con, devuelta))
        else:
            conn.execute("""
                INSERT INTO pedido_pagos (pedido_id, metodo_codigo, metodo_nombre, monto)
                VALUES (%s,%s,%s,%s)
            """, (pedido_id, metodo_pago, metodo_pago, total))
        if negocio['tercero_id'] and _asiento_auto and tipo_doc_id:
            try:
                iva_total = sum(
                    it['precio_unitario'] * it['cantidad'] * it['iva_pct'] / 100
                    for it in items_validos
                )
                _asiento_auto(conn, negocio['tercero_id'], tipo_doc_id,
                              {'subtotal_venta': total - iva_total,
                               'iva_venta': iva_total,
                               'total_venta': total},
                              registrado_por=session.get('usuario_id'),
                              origen_tipo='pedido',
                              origen_id=pedido_id,
                              metodo_pago=metodo_pago,
                              tercero_id=cliente_id,
                              tipo_documento_fisico=tipo_doc_codigo,
                              documento_numero_fisico=res_num,
                              fecha=fecha_pedido)
            except Exception as _e:
                print(f'[cont] venta tienda {slug}: {_e}')
        
        if pedido_premontado_id and numero_documento:
            conn.execute("""
                UPDATE pedidos 
                SET estado = 'entregado', id_cajero = %s, numero_documento = %s
                WHERE id = %s
            """, (session.get('usuario_id'), numero_documento, pedido_premontado_id))

        conn.commit()
        # Notificación Telegram
        chat_id = tienda['telegram_chat_id']
        if not chat_id and tienda['admin_id']:
            admin = conn.execute(
                "SELECT telegram_chat_id FROM terceros WHERE id = %s", (tienda['admin_id'],)
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
                print(f'[telegram tienda] chat global no disponible: {_e}')
        if chat_id:
            items_txt = '\n'.join([f"  {it['cantidad']}x {it['nombre_producto']} - ${it['precio_unitario'] * it['cantidad']:,.0f}" for it in items_validos])
            entrega = _telegram_detalle_entrega_tienda(tipo_entrega, direccion_cliente, nombre_cajero)
            pagos_txt = _telegram_resumen_pagos(pagos_validos, metodo_pago, total)
            cliente_txt = nombre_cliente or nombre_cajero or 'Cliente en local'
            telefono_txt = telefono_cliente or 'Sin telefono'
            msg = (
                f"🛒 <b>Nuevo pedido en {tienda['nombre']}</b>\n"
                f"🧾 Pedido #{pedido_id}\n"
                f"👤 {cliente_txt} - {telefono_txt}\n"
                f"📦 Entrega: {entrega}\n"
                f"💳 Pago elegido: {pagos_txt}\n\n"
                f"{items_txt}\n\n"
                f"Subtotal productos: ${subtotal_productos:,.0f}\n"
                f"Domicilio: {'por confirmar' if domicilio_estado == 'por_confirmar' else '$' + format(float(valor_domicilio or 0), ',.0f')}\n"
                f"💰 Total: ${total:,.0f}"
            )
            _enviar_telegram_tienda(conn, chat_id, msg)
        else:
            print(f'[telegram tienda] sin chat_id para tienda {slug}')
        return jsonify({'ok': True, 'pedido_id': pedido_id, 'total': total, 'numero_documento': numero_documento})
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
                   estado, total, notas, created_at, nombre_cajero, metodo_pago, comprobante_pago,
                   subtotal_productos, valor_domicilio, domicilio_estado
            FROM pedidos WHERE tienda_id = %s AND DATE(created_at) = CURRENT_DATE
            ORDER BY created_at DESC
        """, (tienda['id'],)).fetchall()
        resultado = []
        for p in pedidos:
            items = conn.execute(
                "SELECT nombre_producto, cantidad, precio_unitario FROM pedido_items WHERE pedido_id = %s",
                (p['id'],)
            ).fetchall()
            pagos = conn.execute("""
                SELECT metodo_codigo, metodo_nombre, monto, recibido_con, devuelta
                FROM pedido_pagos
                WHERE pedido_id = %s
                ORDER BY id
            """, (p['id'],)).fetchall()
            pagos_json = [{
                'codigo': pago['metodo_codigo'] or '',
                'nombre': pago['metodo_nombre'] or pago['metodo_codigo'] or '',
                'monto': float(pago['monto'] or 0),
                'recibido_con': float(pago['recibido_con'] or 0),
                'devuelta': float(pago['devuelta'] or 0),
            } for pago in pagos]
            if not pagos_json:
                pagos_json = [{
                    'codigo': p['metodo_pago'] or 'efectivo',
                    'nombre': p['metodo_pago'] or 'efectivo',
                    'monto': float(p['total'] or 0),
                }]
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
                'subtotal_productos': float(p['subtotal_productos'] or p['total'] or 0),
                'valor_domicilio': float(p['valor_domicilio'] or 0),
                'domicilio_estado': p['domicilio_estado'] or 'no_aplica',
                'pagos': pagos_json,
                'items': [{'nombre': i['nombre_producto'], 'cantidad': i['cantidad'], 'precio': float(i['precio_unitario'])} for i in items]
            })
        return jsonify({'ok': True, 'pedidos': resultado})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/caja/<slug>/pedidos-premontados')
def api_caja_pedidos_premontados(slug):
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        
        rows = conn.execute("""
            SELECT p.id, p.nombre_cliente, p.telefono_cliente, p.total, p.notas, p.fecha::text,
                   t.nombre AS vendedor_nombre
            FROM pedidos p
            LEFT JOIN terceros t ON t.id = p.id_tercero_cajero
            WHERE p.negocio_id = %s AND p.estado = 'premontado'
            ORDER BY p.id DESC
        """, (negocio['tercero_id'],)).fetchall()
        
        pedidos = []
        for r in rows:
            items_rows = conn.execute("""
                SELECT producto_id, nombre_producto, cantidad, precio_unitario
                FROM pedido_items
                WHERE pedido_id = %s
            """, (r['id'],)).fetchall()
            
            items = []
            for it in items_rows:
                items.append({
                    'producto_id': it['producto_id'],
                    'nombre_producto': it['nombre_producto'],
                    'cantidad': float(it['cantidad']),
                    'precio_unitario': float(it['precio_unitario'])
                })
                
            pedidos.append({
                'id': r['id'],
                'nombre_cliente': r['nombre_cliente'] or '',
                'telefono_cliente': r['telefono_cliente'] or '',
                'total': float(r['total']),
                'notas': r['notas'] or '',
                'fecha': r['fecha'],
                'vendedor_nombre': r['vendedor_nombre'] or 'Vendedor',
                'items': items
            })
            
        return jsonify({'ok': True, 'pedidos': pedidos})
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
            "UPDATE pedidos SET estado = %s WHERE id = %s AND tienda_id = %s",
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
            "SELECT COUNT(DISTINCT DATE(created_at)) as dias FROM pedidos WHERE tienda_id = %s",
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


# ── Caja PIN y cajeros POS Genérica ─────────────────────────────────────────────

@bp.route('/api/caja/<slug>/verificar-pin-caja', methods=['POST'])
@bp.route('/api/tienda/<slug>/verificar-pin-caja', methods=['POST'])
def api_tienda_verificar_pin_caja(slug):
    pin = ((request.get_json() or {}).get('pin') or '').strip()
    if not pin:
        return jsonify({'ok': False, 'error': 'PIN requerido'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        cajero = conn.execute(
            "SELECT id, nombre, tercero_id FROM tienda_cajeros WHERE "
            "(tienda_id = %s OR restaurante_id = %s) AND pin = %s AND activo = TRUE",
            (negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
             negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None,
             pin)
        ).fetchone()
        if not cajero:
            return jsonify({'ok': False, 'error': 'PIN incorrecto o cajero inactivo'}), 403
        return jsonify({'ok': True, 'id_cajero': cajero['id'], 'nombre_cajero': cajero['nombre'], 'tercero_id': cajero['tercero_id']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/caja/<slug>/pin-caja', methods=['GET', 'POST'])
@bp.route('/api/tienda/<slug>/pin-caja', methods=['GET', 'POST'])
def api_tienda_pin_caja(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        if negocio['tipo_negocio'] == 'tienda':
            tienda = conn.execute("SELECT id, pin_caja FROM tiendas WHERE id = %s", (negocio['id'],)).fetchone()
            pin_caja = tienda['pin_caja'] or ''
        else:
            restaurante = conn.execute("SELECT id, pin_mesero as pin_caja FROM restaurantes WHERE id = %s", (negocio['id'],)).fetchone()
            pin_caja = restaurante['pin_caja'] or ''

        if request.method == 'GET':
            return jsonify({'ok': True, 'pin_caja': pin_caja})
            
        nuevo_pin = ((request.get_json() or {}).get('pin_caja') or '').strip()
        if negocio['tipo_negocio'] == 'tienda':
            conn.execute("UPDATE tiendas SET pin_caja = %s WHERE id = %s", (nuevo_pin or None, negocio['id']))
        else:
            conn.execute("UPDATE restaurantes SET pin_mesero = %s WHERE id = %s", (nuevo_pin or None, negocio['id']))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/caja/<slug>/cajeros', methods=['GET'])
@bp.route('/api/tienda/<slug>/cajeros', methods=['GET'])
def api_tienda_cajeros_listar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        cajeros = conn.execute(
            "SELECT id, nombre, pin, activo FROM tienda_cajeros WHERE "
            "(tienda_id = %s OR restaurante_id = %s) ORDER BY id",
            (negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
             negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None)
        ).fetchall()
        return jsonify({'ok': True, 'cajeros': [dict(c) for c in cajeros]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/caja/<slug>/cajero', methods=['POST'])
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
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        dup = conn.execute(
            "SELECT id FROM tienda_cajeros WHERE "
            "(tienda_id = %s OR restaurante_id = %s) AND pin = %s",
            (negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
             negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None,
             pin)
        ).fetchone()
        if dup:
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
            "INSERT INTO tienda_cajeros (tienda_id, restaurante_id, tercero_id, nombre, pin) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
             negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None,
             tercero_id, nombre, pin)
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


@bp.route('/api/caja/<slug>/cajero/<int:cajero_id>/toggle', methods=['POST'])
@bp.route('/api/tienda/<slug>/cajero/<int:cajero_id>/toggle', methods=['POST'])
def api_tienda_cajero_toggle(slug, cajero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        conn.execute(
            "UPDATE tienda_cajeros SET activo = NOT activo WHERE id = %s AND "
            "(tienda_id = %s OR restaurante_id = %s)",
            (cajero_id,
             negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
             negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None)
        )
        conn.commit()
        nuevo = conn.execute("SELECT activo FROM tienda_cajeros WHERE id = %s", (cajero_id,)).fetchone()
        return jsonify({'ok': True, 'activo': nuevo['activo']})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/caja/<slug>/cajero/<int:cajero_id>', methods=['DELETE'])
@bp.route('/api/tienda/<slug>/cajero/<int:cajero_id>', methods=['DELETE'])
def api_tienda_cajero_eliminar(slug, cajero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        conn.execute(
            "DELETE FROM tienda_cajeros WHERE id = %s AND "
            "(tienda_id = %s OR restaurante_id = %s)",
            (cajero_id,
             negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None,
             negocio['id'] if negocio['tipo_negocio'] == 'restaurante' else None)
        )
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


@bp.route('/api/tienda/<slug>/fichas-solares')
def api_tienda_fichas_solares(slug):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT tercero_id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        filas = conn.execute("""
            SELECT p.id AS producto_id, p.nombre, p.categoria, f.tipo, f.datos, f.updated_at
            FROM productos p
            LEFT JOIN producto_fichas_solares f ON f.producto_id = p.id
            WHERE p.negocio_id = %s
            ORDER BY (f.producto_id IS NULL) DESC, p.categoria, p.nombre
        """, (tienda['tercero_id'],)).fetchall()
        fichas = []
        for f in filas:
            fichas.append({
                'producto_id': f['producto_id'],
                'nombre': f['nombre'],
                'categoria': f['categoria'] or '',
                'tipo': f['tipo'] or '',
                'datos': f['datos'] or {},
                'updated_at': str(f['updated_at']) if f['updated_at'] else '',
            })
        return jsonify({'ok': True, 'fichas': fichas})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/producto/<int:producto_id>/ficha-solar', methods=['GET', 'POST'])
def api_tienda_producto_ficha_solar(slug, producto_id):
    if request.method == 'POST' and 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
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

        if request.method == 'GET':
            ficha = conn.execute(
                "SELECT tipo, datos, updated_at FROM producto_fichas_solares WHERE producto_id = %s",
                (producto_id,)
            ).fetchone()
            return jsonify({
                'ok': True,
                'ficha': {
                    'producto_id': producto_id,
                    'tipo': ficha['tipo'] if ficha else '',
                    'datos': ficha['datos'] if ficha else {},
                    'updated_at': str(ficha['updated_at']) if ficha else '',
                }
            })

        data = request.get_json() or {}
        tipo = (data.get('tipo') or '').strip()
        datos = data.get('datos') or {}
        if tipo not in ('', 'panel', 'bateria', 'inversor'):
            return jsonify({'ok': False, 'error': 'Tipo solar invalido'}), 400
        if not isinstance(datos, dict):
            return jsonify({'ok': False, 'error': 'Datos invalidos'}), 400

        if not tipo:
            conn.execute("DELETE FROM producto_fichas_solares WHERE producto_id = %s", (producto_id,))
        else:
            conn.execute("""
                INSERT INTO producto_fichas_solares (producto_id, tipo, datos, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (producto_id) DO UPDATE
                SET tipo = EXCLUDED.tipo, datos = EXCLUDED.datos, updated_at = NOW()
            """, (producto_id, tipo, json.dumps(datos)))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


def _normalizar_telefono_tercero(valor):
    return ''.join(filter(str.isdigit, valor or ''))


def _resolver_tercero_cliente(conn, cliente_id=None, nombre='', telefono=''):
    nombre = (nombre or '').strip()
    telefono = _normalizar_telefono_tercero(telefono)
    try:
        cliente_id = int(cliente_id or 0)
    except (TypeError, ValueError):
        cliente_id = 0
    if cliente_id:
        row = conn.execute(
            "SELECT id, nombre, telefono FROM terceros WHERE id = %s LIMIT 1",
            (cliente_id,)
        ).fetchone()
        if not row:
            raise ValueError('Tercero no encontrado')
        if nombre or telefono:
            conn.execute(
                "UPDATE terceros SET nombre = COALESCE(NULLIF(%s, ''), nombre), telefono = COALESCE(NULLIF(%s, ''), telefono) WHERE id = %s",
                (nombre, telefono, row['id'])
            )
        return {
            'id': row['id'],
            'nombre': nombre or row['nombre'] or '',
            'telefono': telefono or row['telefono'] or '',
        }
    if not nombre:
        raise ValueError('Cliente requerido')
    if telefono:
        row = conn.execute(
            "SELECT id, nombre, telefono FROM terceros WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
            (telefono,)
        ).fetchone()
        if row:
            conn.execute("UPDATE terceros SET nombre = %s WHERE id = %s", (nombre, row['id']))
            return {'id': row['id'], 'nombre': nombre, 'telefono': telefono}
    row = conn.execute(
        "INSERT INTO terceros (nombre, telefono, fecha_creacion) VALUES (%s, %s, NOW()) RETURNING id",
        (nombre, telefono or None)
    ).fetchone()
    return {'id': row['id'], 'nombre': nombre, 'telefono': telefono}


def _slug_publico_proyecto(valor):
    texto = (valor or '').strip().lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^a-z0-9]+', '-', texto)
    texto = re.sub(r'-+', '-', texto).strip('-')
    return texto or 'proyecto'


def _url_publica_proyecto(slug_tienda, cliente, escenario, token=None):
    cliente_slug = _slug_publico_proyecto(cliente)
    escenario_slug = _slug_publico_proyecto(escenario or 'proyecto-solar')
    return f'https://{slug_tienda}.tuc-tuc.co/{cliente_slug}/{escenario_slug}'


def _slug_tienda_desde_host():
    return resolver_slug_por_host(request.host, 'tienda')


def solar_proyecto_publico_desde_slugs(tienda_slug, cliente_slug, escenario_slug):
    cliente_slug = _slug_publico_proyecto(cliente_slug)
    escenario_slug = _slug_publico_proyecto(escenario_slug)
    if not tienda_slug or not cliente_slug or not escenario_slug:
        return None
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        filas = conn.execute("""
            SELECT p.token_publico, p.cliente_nombre, p.escenario
            FROM proyectos_solares p
            JOIN tiendas t ON t.id = p.tienda_id
            WHERE t.slug = %s AND t.activo = TRUE
            ORDER BY p.updated_at DESC, p.id DESC
        """, (tienda_slug,)).fetchall()
        for fila in filas:
            if (
                _slug_publico_proyecto(fila['cliente_nombre']) == cliente_slug
                and _slug_publico_proyecto(fila['escenario']) == escenario_slug
            ):
                return solar_proyecto_publico(fila['token_publico'])
        return None
    finally:
        conn.close()


def _proyecto_solar_dict(p, incluir_detalle=True):
    tienda_slug = p['slug'] if 'slug' in p.keys() else ''
    item = {
        'id': p['id'],
        'cliente_id': p['cliente_id'] if 'cliente_id' in p.keys() else None,
        'cliente_nombre': p['cliente_nombre'] or '',
        'cliente_telefono': p['cliente_telefono'] or '',
        'ubicacion': p['ubicacion'] or '',
        'escenario': p['escenario'] or '',
        'tipo_sistema': p['tipo_sistema'] or '',
        'total': float(p['total'] or 0),
        'estado': p['estado'] or 'borrador',
        'asesoria_pagada': bool(p['asesoria_pagada']) if 'asesoria_pagada' in p.keys() else False,
        'pdf_habilitado': bool(p['pdf_habilitado']) if 'pdf_habilitado' in p.keys() else False,
        'token_publico': p['token_publico'],
        'url_publica': _url_publica_proyecto(tienda_slug, p['cliente_nombre'], p['escenario'], p['token_publico']) if tienda_slug else f'/solar/proyecto/{p["token_publico"]}',
        'url_pdf': f'/solar/proyecto/{p["token_publico"]}/pdf',
        'created_at': str(p['created_at']) if p['created_at'] else '',
        'updated_at': str(p['updated_at']) if p['updated_at'] else '',
    }
    if incluir_detalle:
        item['datos_tecnicos'] = p['datos_tecnicos'] or {}
        item['presupuesto'] = p['presupuesto'] or {}
    return item


def _enriquecer_lineas_proyecto_solar(conn, slug, proyecto):
    presupuesto = proyecto.get('presupuesto') or {}
    lineas = presupuesto.get('lineas') or []
    producto_ids = [int(l.get('producto_id') or 0) for l in lineas if l.get('producto_id')]
    if not producto_ids:
        return proyecto
    productos = conn.execute("""
        SELECT id, nombre, categoria, imagen, descripcion
        FROM productos
        WHERE id = ANY(%s)
    """, (producto_ids,)).fetchall()
    producto_por_id = {p['id']: p for p in productos}
    docs = conn.execute("""
        SELECT DISTINCT ON (producto_id) producto_id, id, nombre
        FROM producto_documentos
        WHERE producto_id = ANY(%s) AND visible_cliente = TRUE
        ORDER BY producto_id, tipo = 'ficha_tecnica' DESC, orden, id
    """, (producto_ids,)).fetchall()
    doc_por_producto = {d['producto_id']: d for d in docs}
    tienda_url = f'https://{slug}.tuc-tuc.co'
    for linea in lineas:
        producto_id = int(linea.get('producto_id') or 0)
        producto = producto_por_id.get(producto_id)
        doc = doc_por_producto.get(producto_id)
        if producto:
            linea['imagen'] = producto['imagen'] or ''
            linea['descripcion'] = producto['descripcion'] or ''
            linea['categoria'] = producto['categoria'] or linea.get('categoria') or ''
            linea['producto_url'] = f'{tienda_url}?producto={producto_id}'
        if doc:
            linea['ficha_tecnica_url'] = f'/api/tienda/{slug}/producto/{producto_id}/documento/{doc["id"]}'
            linea['ficha_tecnica_nombre'] = doc['nombre'] or 'Ficha tecnica'
    presupuesto['lineas'] = lineas
    proyecto['presupuesto'] = presupuesto
    return proyecto


@bp.route('/api/tienda/<slug>/proyectos-solares')
def api_tienda_proyectos_solares(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id, slug FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        filas = conn.execute("""
            SELECT id, %s AS slug, cliente_id, cliente_nombre, cliente_telefono, ubicacion, escenario, tipo_sistema,
                   total, estado, asesoria_pagada, pdf_habilitado, token_publico, created_at, updated_at
            FROM proyectos_solares
            WHERE tienda_id = %s
            ORDER BY updated_at DESC, id DESC
            LIMIT 60
        """, (tienda['slug'], tienda['id'])).fetchall()
        return jsonify({'ok': True, 'proyectos': [_proyecto_solar_dict(p, False) for p in filas]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/proyecto-solar', methods=['POST'])
def api_tienda_proyecto_solar_guardar(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute("SELECT id, slug FROM tiendas WHERE slug = %s", (slug,)).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        proyecto_id = data.get('id')
        tercero = _resolver_tercero_cliente(
            conn,
            data.get('cliente_id'),
            data.get('cliente_nombre') or '',
            data.get('cliente_telefono') or ''
        )
        cliente = tercero['nombre']
        telefono = tercero['telefono']
        presupuesto = data.get('presupuesto') or {}
        datos = data.get('datos_tecnicos') or {}
        total = float(presupuesto.get('total') or data.get('total') or 0)
        asesoria_pagada = bool(data.get('asesoria_pagada'))
        pdf_habilitado = bool(data.get('pdf_habilitado'))
        if proyecto_id:
            existente = conn.execute(
                "SELECT token_publico FROM proyectos_solares WHERE id = %s AND tienda_id = %s",
                (proyecto_id, tienda['id'])
            ).fetchone()
            if not existente:
                return jsonify({'ok': False, 'error': 'Proyecto no encontrado'}), 404
            token = existente['token_publico']
            conn.execute("""
                UPDATE proyectos_solares
                SET cliente_id=%s, cliente_nombre=%s, cliente_telefono=%s, ubicacion=%s, escenario=%s,
                    tipo_sistema=%s, datos_tecnicos=%s, presupuesto=%s, total=%s,
                    estado=%s, asesoria_pagada=%s, pdf_habilitado=%s, updated_at=NOW()
                WHERE id=%s AND tienda_id=%s
            """, (
                tercero['id'],
                cliente,
                telefono,
                (data.get('ubicacion') or '').strip(),
                (data.get('escenario') or '').strip(),
                (data.get('tipo_sistema') or '').strip(),
                json.dumps(datos),
                json.dumps(presupuesto),
                total,
                (data.get('estado') or 'borrador').strip(),
                asesoria_pagada,
                pdf_habilitado,
                proyecto_id,
                tienda['id'],
            ))
        else:
            token = secrets.token_urlsafe(18)
            row = conn.execute("""
                INSERT INTO proyectos_solares
                    (tienda_id, cliente_id, cliente_nombre, cliente_telefono, ubicacion, escenario,
                     tipo_sistema, datos_tecnicos, presupuesto, total, estado, asesoria_pagada, pdf_habilitado, token_publico)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                tienda['id'],
                tercero['id'],
                cliente,
                telefono,
                (data.get('ubicacion') or '').strip(),
                (data.get('escenario') or '').strip(),
                (data.get('tipo_sistema') or '').strip(),
                json.dumps(datos),
                json.dumps(presupuesto),
                total,
                (data.get('estado') or 'borrador').strip(),
                asesoria_pagada,
                pdf_habilitado,
                token,
            )).fetchone()
            proyecto_id = row['id']
        conn.commit()
        return jsonify({
            'ok': True,
            'proyecto_id': proyecto_id,
            'cliente_id': tercero['id'],
            'token_publico': token,
            'url_publica': _url_publica_proyecto(tienda['slug'], cliente, data.get('escenario') or '', token)
        })
    except ValueError as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/proyecto-solar/<int:proyecto_id>')
def api_tienda_proyecto_solar_ver(slug, proyecto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        p = conn.execute("""
            SELECT p.*, t.slug
            FROM proyectos_solares p
            JOIN tiendas t ON t.id = p.tienda_id
            WHERE p.id = %s AND t.slug = %s
        """, (proyecto_id, slug)).fetchone()
        if not p:
            return jsonify({'ok': False, 'error': 'Proyecto no encontrado'}), 404
        return jsonify({'ok': True, 'proyecto': _proyecto_solar_dict(p, True)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/visitas-publicas')
def api_tienda_visitas_publicas(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        tienda = conn.execute(
            "SELECT id, admin_id FROM tiendas WHERE slug = %s AND activo = TRUE",
            (slug,)
        ).fetchone()
        if not tienda:
            return jsonify({'ok': False, 'error': 'Tienda no encontrada'}), 404
        if session.get('rol') != 'Administrador' and session.get('usuario_id') != tienda['admin_id']:
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        visitantes_out, visitas_out = listar_visitas_publicas(conn, 'tienda', tienda['id'])
        visitantes_legacy = conn.execute("""
            SELECT v.id, v.visitante_token, v.usuario_id, v.primer_path, v.ultimo_path, v.ip_primera, v.ip_ultima,
                   v.visitas, v.first_seen, v.last_seen, v.user_agent,
                   t.nombre AS usuario_nombre, t.telefono AS usuario_telefono
            FROM tienda_visitantes_publicos v
            LEFT JOIN terceros t ON t.id = v.usuario_id
            WHERE v.tienda_id = %s
            ORDER BY v.last_seen DESC
            LIMIT 80
        """, (tienda['id'],)).fetchall()
        visitas_legacy = conn.execute("""
            SELECT vi.id, vi.visitante_id, vi.usuario_id, vi.proyecto_id, vi.tipo, vi.path,
                   vi.referrer, vi.ip, vi.user_agent, vi.created_at,
                   t.nombre AS usuario_nombre, p.cliente_nombre, p.escenario,
                   vp.visitante_token
            FROM tienda_visitas_publicas vi
            LEFT JOIN terceros t ON t.id = vi.usuario_id
            LEFT JOIN proyectos_solares p ON p.id = vi.proyecto_id
            LEFT JOIN tienda_visitantes_publicos vp ON vp.id = vi.visitante_id
            WHERE vi.tienda_id = %s
            ORDER BY vi.created_at DESC
            LIMIT 120
        """, (tienda['id'],)).fetchall()
        for v in visitantes_legacy:
            item = dict(v)
            item['id'] = f"legacy-{v['id']}"
            item['first_seen'] = str(v['first_seen']) if v['first_seen'] else ''
            item['last_seen'] = str(v['last_seen']) if v['last_seen'] else ''
            visitantes_out.append(item)
        for v in visitas_legacy:
            item = dict(v)
            item['id'] = f"legacy-{v['id']}"
            item['visitante_id'] = f"legacy-{v['visitante_id']}" if v['visitante_id'] else None
            item['created_at'] = str(v['created_at']) if v['created_at'] else ''
            if not item.get('titulo'):
                if v['tipo'] == 'proyecto_solar' and v['cliente_nombre']:
                    item['titulo'] = f"Proyecto solar: {v['cliente_nombre']} / {v['escenario']}"
                elif v['tipo'] == 'proyecto_solar_pdf' and v['cliente_nombre']:
                    item['titulo'] = f"PDF tecnico: {v['cliente_nombre']} / {v['escenario']}"
                elif v['tipo'] == 'proyecto_solar_pdf_bloqueado' and v['cliente_nombre']:
                    item['titulo'] = f"PDF bloqueado: {v['cliente_nombre']} / {v['escenario']}"
                else:
                    item['titulo'] = 'Portada de tienda'
            visitas_out.append(item)
        visitantes_out.sort(key=lambda item: item.get('last_seen') or '', reverse=True)
        visitas_out.sort(key=lambda item: item.get('created_at') or '', reverse=True)
        return jsonify({
            'ok': True,
            'zona_horaria': 'America/Bogota',
            'visitantes': visitantes_out,
            'visitas': visitas_out,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/solar/proyecto/<token>')
def solar_proyecto_publico(token):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        row = conn.execute("""
            SELECT p.*, t.nombre AS tienda_nombre, t.slug, t.admin_telefono, t.color_accion,
                   t.imagen_header, t.imagen_header_movil, t.descripcion
            FROM proyectos_solares p
            JOIN tiendas t ON t.id = p.tienda_id
            WHERE p.token_publico = %s AND t.activo = TRUE
        """, (token,)).fetchone()
        if not row:
            return "Proyecto no encontrado", 404
        tienda = {
            'nombre': row['tienda_nombre'],
            'slug': row['slug'],
            'admin_telefono': row['admin_telefono'] or '',
            'color_accion': row['color_accion'] or '#e11d48',
            'imagen_header': row['imagen_header'] or '',
            'imagen_header_movil': row['imagen_header_movil'] or '',
            'descripcion': row['descripcion'] or '',
            'url': f'https://{row["slug"]}.tuc-tuc.co',
        }
        proyecto = _proyecto_solar_dict(row, True)
        proyecto = _enriquecer_lineas_proyecto_solar(conn, row['slug'], proyecto)
        visita = _registrar_visita_generica(
            conn,
            'tienda',
            row['tienda_id'],
            recurso_tipo='proyecto_solar',
            recurso_id=row['id'],
            titulo=f"Proyecto solar: {row['cliente_nombre']} / {row['escenario']}",
        )
        response = make_response(render_template('solar_proyecto_publico.html', tienda=tienda, proyecto=proyecto))
        return _respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/proyecto/<cliente_slug>/<path:resto>')
def solar_proyecto_publico_bonito(cliente_slug, resto):
    tienda_slug = _slug_tienda_desde_host()
    respuesta = solar_proyecto_publico_desde_slugs(tienda_slug, cliente_slug, resto)
    if respuesta is None:
        return "Proyecto no encontrado", 404
    return respuesta


@bp.route('/solar/proyecto/<token>/pdf')
def solar_proyecto_pdf(token):
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        row = conn.execute("""
            SELECT p.*, t.nombre AS tienda_nombre, t.slug, t.admin_telefono, t.color_accion,
                   t.imagen_header, t.imagen_header_movil, t.descripcion
            FROM proyectos_solares p
            JOIN tiendas t ON t.id = p.tienda_id
            WHERE p.token_publico = %s AND t.activo = TRUE
        """, (token,)).fetchone()
        if not row:
            return "Proyecto no encontrado", 404
        if not row['asesoria_pagada'] or not row['pdf_habilitado']:
            visita = _registrar_visita_generica(
                conn,
                'tienda',
                row['tienda_id'],
                recurso_tipo='proyecto_solar_pdf_bloqueado',
                recurso_id=row['id'],
                titulo=f"PDF bloqueado: {row['cliente_nombre']} / {row['escenario']}",
            )
            response = make_response("PDF tecnico no habilitado para este proyecto", 403)
            return _respuesta_con_visitante(response, visita)
        tienda = {
            'nombre': row['tienda_nombre'],
            'slug': row['slug'],
            'admin_telefono': row['admin_telefono'] or '',
            'color_accion': row['color_accion'] or '#e11d48',
            'url': f'https://{row["slug"]}.tuc-tuc.co',
        }
        proyecto = _enriquecer_lineas_proyecto_solar(conn, row['slug'], _proyecto_solar_dict(row, True))
        visita = _registrar_visita_generica(
            conn,
            'tienda',
            row['tienda_id'],
            recurso_tipo='proyecto_solar_pdf',
            recurso_id=row['id'],
            titulo=f"PDF tecnico: {row['cliente_nombre']} / {row['escenario']}",
        )
        response = make_response(render_template('solar_proyecto_pdf.html', tienda=tienda, proyecto=proyecto))
        return _respuesta_con_visitante(response, visita)
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/docs/tienda')
def docs_tienda():
    return render_template('docs_tienda.html')


@bp.route('/admin/docs/tienda')
def admin_docs_tienda():
    return render_template('docs_tienda_admin.html')


@bp.route('/api/caja/<slug>/tipos-doc', methods=['GET'])
@bp.route('/api/tienda/<slug>/tipos-doc', methods=['GET'])
def api_tienda_tipos_doc_get(slug):
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        
        # Get active document types for the business (tercero_id) of type 'venta'
        rows = conn.execute(
            "SELECT id, codigo, nombre, predeterminado, mueve_inventario, tipo_movimiento, consecutivo, numero_inicio "
            "FROM tipos_documento_negocio "
            "WHERE negocio_id=%s AND activo=TRUE AND tipo_movimiento='venta' ORDER BY nombre", 
            (negocio['tercero_id'],)
        ).fetchall()
        
        tipos = []
        for r in rows:
            next_num = max((r['consecutivo'] or 0) + 1, (r['numero_inicio'] or 1))
            codigo_prefix = r['codigo'] or 'DOC'
            siguiente = f"{codigo_prefix}-{next_num}"
            
            t_dict = dict(r)
            t_dict['siguiente_numero'] = siguiente
            tipos.append(t_dict)
            
        return jsonify({'ok': True, 'tipos': tipos})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
