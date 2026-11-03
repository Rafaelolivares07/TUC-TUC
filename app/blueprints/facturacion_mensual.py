# -*- coding: utf-8 -*-
"""Facturacion mensual recurrente (tema 9, 2026-11-03).

Caso: empresa administrator factura cada mes a LOPEZ REFRIGERACION.
El servidor genera la factura el dia 1 (mes vencido), salta el contador
un aleatorio 5-15 (solo contador, sin rastro), renderiza la imagen,
avisa a Telegram con boton directo al WhatsApp del cliente y deja
pendiente en agenda. Rafa solo da Enviar.

Sin tablas nuevas: terceros, tipos_documento_negocio, productos,
precios, pedidos, pedido_items, agenda_items (+ 5 columnas _asegurar).
"""
import random
import secrets
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, session, Response, render_template

from ..db import get_db_connection

bp = Blueprint('facturacion_mensual', __name__)

BOGOTA = ZoneInfo('America/Bogota')

EMPRESA = {
    'nombre': 'RAFAEL OLIVARES GIRALDO',
    'marca': 'administrator',
    'documento': '16781009-4',
    'rol': 'ADMINISTRADOR',
}
CLIENTE = {
    'nombre': 'LOPEZ REFRIGERACION',
    'telefono': '+19142747117',
    'contacto': 'Jesus',
}
SERVICIOS = [
    {'nombre': 'ALOJAMIENTO DE DATOS', 'precio': 500000},
    {'nombre': 'HORA DE SOPORTE', 'precio': 50000},
]
TIPO_DOC_CODIGO = 'FC'
TIPO_DOC_NOMBRE = 'FACTURA CREDITO'
CONTADOR_ARRANQUE = 1768
SALTO_MIN, SALTO_MAX = 5, 15
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
BASE_URL = 'https://admin.tuc-tuc.co'


def _ahora_bogota():
    return datetime.now(BOGOTA)


def _mes_vencido(ahora=None):
    """(mes, anio) del mes vencido: el anterior al de generacion."""
    ahora = ahora or _ahora_bogota()
    if ahora.month == 1:
        return 12, ahora.year - 1
    return ahora.month - 1, ahora.year


def _saludo(hora=None):
    """dias antes de las 12, tardes despues (hora Bogota)."""
    h = hora if hora is not None else _ahora_bogota().hour
    return 'días' if h < 12 else 'tardes'


def _telefono_wa():
    return ''.join(c for c in CLIENTE['telefono'] if c.isdigit())


def _mensaje_whatsapp(link_factura, ahora=None):
    ahora = ahora or _ahora_bogota()
    mes, anio = _mes_vencido(ahora)
    return (
        "Don %s muy buenos %s, aquí le envío la factura de %s %d:\n%s"
        % (CLIENTE['contacto'], _saludo(ahora.hour), MESES[mes - 1], anio, link_factura)
    )


def _url_wa(mensaje):
    return 'https://wa.me/%s?text=%s' % (_telefono_wa(), urllib.parse.quote(mensaje))


def _formato_numero(n):
    return '$%s' % format(int(n), ',').replace(',', '.')


def _asegurar_columnas(conn):
    for sql in [
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS documento VARCHAR(30)",
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS contacto VARCHAR(100)",
        "ALTER TABLE terceros ADD COLUMN IF NOT EXISTS es_empresa BOOLEAN DEFAULT FALSE",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS numero INTEGER",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS tipo_documento_id INTEGER",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS token_publico VARCHAR(64)",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        conn.commit()
    except Exception:
        pass


def _asegurar_datos(conn):
    """Crea si faltan: empresa, tipo doc, cliente, servicios. Retorna ids."""
    _asegurar_columnas(conn)
    try:
        from .inventarios import _crear_tablas
        _crear_tablas(conn)
    except Exception:
        pass
    emp = conn.execute(
        "SELECT id FROM terceros WHERE tipo_tercero = 'negocio' AND nombre = %s LIMIT 1",
        (EMPRESA['nombre'],)).fetchone()
    if not emp:
        emp = conn.execute(
            "INSERT INTO terceros (nombre, tipo_tercero, es_empresa, documento) "
            "VALUES (%s, 'negocio', TRUE, %s) RETURNING id",
            (EMPRESA['nombre'], EMPRESA['documento'])).fetchone()
    empresa_id = emp['id']
    conn.execute(
        """INSERT INTO tipos_documento_negocio
           (negocio_id, codigo, nombre, numero_inicio, consecutivo,
            predeterminado, mueve_inventario, tipo_movimiento, es_interno, activo)
           VALUES (%s, %s, %s, %s, %s, TRUE, FALSE, 'venta', TRUE, TRUE)
           ON CONFLICT (negocio_id, codigo) DO NOTHING""",
        (empresa_id, TIPO_DOC_CODIGO, TIPO_DOC_NOMBRE,
         CONTADOR_ARRANQUE + 1, CONTADOR_ARRANQUE))
    td = conn.execute(
        "SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND codigo = %s",
        (empresa_id, TIPO_DOC_CODIGO)).fetchone()
    cli = conn.execute(
        "SELECT id FROM terceros WHERE telefono = %s LIMIT 1",
        (CLIENTE['telefono'],)).fetchone()
    if not cli:
        cli = conn.execute(
            "INSERT INTO terceros (nombre, telefono, tipo_tercero, contacto) "
            "VALUES (%s, %s, 'persona', %s) RETURNING id",
            (CLIENTE['nombre'], CLIENTE['telefono'], CLIENTE['contacto'])).fetchone()
    else:
        conn.execute("UPDATE terceros SET contacto = %s WHERE id = %s",
                     (CLIENTE['contacto'], cli['id']))
    servicios = []
    for s in SERVICIOS:
        p = conn.execute(
            "SELECT id, precio FROM productos WHERE negocio_id = %s AND nombre = %s LIMIT 1",
            (empresa_id, s['nombre'])).fetchone()
        if not p:
            p = conn.execute(
                "INSERT INTO productos (negocio_id, nombre, categoria, precio, costo, iva_pct, disponible) "
                "VALUES (%s, %s, 'servicio', %s, 0, 0, TRUE) RETURNING id, precio",
                (empresa_id, s['nombre'], s['precio'])).fetchone()
        servicios.append({'id': p['id'], 'nombre': s['nombre'],
                          'precio': float(p['precio'] or s['precio'])})
        try:
            from .inventarios import _sync_precio
            _sync_precio(conn, empresa_id, p['id'])
        except Exception:
            pass
    conn.commit()
    return {'empresa_id': empresa_id, 'tipodoc_id': td['id'],
            'cliente_id': cli['id'], 'servicios': servicios}


def _factura_del_mes(conn, empresa_id, tipodoc_id):
    """Factura ya generada este mes (idempotencia). JSON-safe."""
    row = conn.execute(
        """SELECT id, numero, token_publico, total, created_at FROM pedidos
           WHERE negocio_id = %s AND tipo_documento_id = %s
             AND date_trunc('month', created_at) = date_trunc('month', NOW())
           ORDER BY id DESC LIMIT 1""",
        (empresa_id, tipodoc_id)).fetchone()
    if not row:
        return None
    mes, anio = _mes_vencido(row['created_at'].replace(tzinfo=BOGOTA)
                             if row['created_at'] and not row['created_at'].tzinfo
                             else (row['created_at'] or _ahora_bogota()))
    return {'pedido_id': row['id'], 'numero': int(row['numero']),
            'token': row['token_publico'], 'total': float(row['total'] or 0),
            'mes': MESES[mes - 1], 'anio': anio,
            'fecha': row['created_at'].isoformat() if row['created_at'] else ''}


def _generar_factura(conn):
    """Genera la factura del mes vencido. Idempotente por mes."""
    from .contabilidad import obtener_siguiente_consecutivo
    datos = _asegurar_datos(conn)
    empresa_id = datos['empresa_id']
    tipodoc_id = datos['tipodoc_id']
    conn.execute("SELECT id FROM tipos_documento_negocio WHERE id = %s FOR UPDATE",
                 (tipodoc_id,))
    existente = _factura_del_mes(conn, empresa_id, tipodoc_id)
    if existente:
        try:
            conn.rollback()
        except Exception:
            pass
        return {'ok': True, 'repetida': True, 'factura': existente}
    ahora = _ahora_bogota()
    mes_v, anio_v = _mes_vencido(ahora)
    num_str, _es_interno = obtener_siguiente_consecutivo(conn, empresa_id, tipodoc_id)
    numero = int(num_str)
    servicio = datos['servicios'][0]
    total = servicio['precio']
    token = secrets.token_urlsafe(16)
    notas = 'FACTURA CREDITO %s-%d - %s %d (mes vencido)' % (
        TIPO_DOC_CODIGO, numero, MESES[mes_v - 1], anio_v)
    ped = conn.execute(
        """INSERT INTO pedidos (negocio_id, cliente_id, nombre_cliente, telefono_cliente,
            estado, cartera_estado, total, subtotal_productos, notas, numero,
            tipo_documento_id, token_publico)
           VALUES (%s, %s, %s, %s, 'nuevo', 'pendiente', %s, %s, %s, %s, %s, %s)
           RETURNING id, created_at""",
        (empresa_id, datos['cliente_id'], CLIENTE['nombre'], CLIENTE['telefono'],
         total, total, notas, numero, tipodoc_id, token)).fetchone()
    conn.execute(
        """INSERT INTO pedido_items (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario)
           VALUES (%s, %s, %s, 1, %s)""",
        (ped['id'], servicio['id'], servicio['nombre'], total))
    salto = random.randint(SALTO_MIN, SALTO_MAX)
    conn.execute("UPDATE tipos_documento_negocio SET consecutivo = %s WHERE id = %s",
                 (numero + salto, tipodoc_id))
    conn.commit()
    return {'ok': True, 'repetida': False,
            'factura': {'pedido_id': ped['id'], 'numero': numero, 'token': token,
                        'total': total, 'mes': MESES[mes_v - 1], 'anio': anio_v,
                        'salto': salto,
                        'fecha': ped['created_at'].isoformat() if ped['created_at'] else ''}}


def _fuente(size, bold=False):
    from PIL import ImageFont
    suf = '-Bold' if bold else ''
    for p in (
        'C:/Windows/Fonts/%s' % ('arialbd.ttf' if bold else 'arial.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % suf,
        '/usr/share/fonts/dejavu/DejaVuSans%s.ttf' % suf,
    ):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _linea_punteada(draw, x0, x1, y, fill=(150, 150, 150)):
    x = x0
    while x < x1:
        draw.line([(x, y), (min(x + 5, x1), y)], fill=fill, width=2)
        x += 10


def _render_imagen(factura):
    """PNG de la factura estilo administrator mejorado. Retorna bytes."""
    from PIL import Image, ImageDraw
    import io
    W = 720
    M = 40
    ROJO = (178, 34, 34)
    NEGRO = (20, 20, 20)
    GRIS = (110, 110, 110)
    f_a = _fuente(92, bold=True)
    f_marca = _fuente(40, bold=True)
    f_tit = _fuente(26, bold=True)
    f_txt = _fuente(26)
    f_tot = _fuente(30, bold=True)
    f_pie = _fuente(22)
    img = Image.new('RGB', (W, 1600), 'white')
    d = ImageDraw.Draw(img)
    y = 24
    d.rectangle([(0, 0), (W, 150)], fill=ROJO)
    d.text((M + 8, 62), 'a', font=f_a, fill='white', anchor='lm')
    d.text((150, 62), 'administrator', font=f_marca, fill='white', anchor='lm')
    y = 185
    for txt, fnt in ((EMPRESA['nombre'], f_tit), (EMPRESA['documento'], f_txt),
                     ('%s - %s' % (EMPRESA['nombre'], EMPRESA['rol']), f_txt)):
        d.text((W // 2, y), txt, font=fnt, fill=NEGRO, anchor='ma')
        y += 40
    fecha_txt = factura.get('fecha', '')
    try:
        fch = datetime.fromisoformat(fecha_txt)
        fecha_txt = fch.strftime('%d/%m/%Y %I:%M:%S %p')
    except Exception:
        pass
    d.text((W // 2, y), fecha_txt, font=f_txt, fill=NEGRO, anchor='ma')
    y += 52
    _linea_punteada(d, M, W - M, y)
    y += 28
    d.text((M, y), 'CLIENTE', font=f_tit, fill=NEGRO)
    y += 40
    d.text((M, y), CLIENTE['nombre'], font=f_tot, fill=NEGRO)
    y += 56
    _linea_punteada(d, M, W - M, y)
    y += 28
    d.text((M, y), 'FACTURA CREDITO.', font=f_tit, fill=NEGRO)
    y += 40
    d.text((M, y), 'NRO: %d' % factura['numero'], font=f_tit, fill=NEGRO)
    y += 52
    _linea_punteada(d, M, W - M, y)
    y += 28
    d.text((M, y), 'VENDEDOR', font=f_txt, fill=GRIS)
    d.text((W - M, y), '0', font=f_txt, fill=NEGRO, anchor='ra')
    y += 44
    _linea_punteada(d, M, W - M, y)
    y += 28
    d.text((M, y), 'DESCRIPCION DE PRODUCTOS', font=f_tit, fill=NEGRO)
    y += 44
    d.text((M, y), 'CANT.', font=f_txt, fill=GRIS)
    d.text((M + 110, y), 'NOMBRE', font=f_txt, fill=GRIS)
    d.text((W - M, y), 'PRECIO', font=f_txt, fill=GRIS, anchor='ra')
    y += 40
    _linea_punteada(d, M, W - M, y)
    y += 24
    d.text((M + 20, y), '1', font=f_tot, fill=NEGRO)
    d.text((M + 110, y), 'ALOJAMIENTO DE DATOS', font=f_tot, fill=NEGRO)
    d.text((W - M, y), _formato_numero(factura['total']), font=f_tot, fill=NEGRO, anchor='ra')
    y += 56
    _linea_punteada(d, M, W - M, y)
    y += 28
    for etiqueta, valor, fnt in (
            ('TOTAL PRODUCTOS', factura['total'], f_txt),
            ('TOTAL SIN I.V.A', factura['total'], f_txt),
            ('I.V.A', 0, f_txt),
            ('TOTAL FACTURA', factura['total'], f_tot)):
        d.text((M, y), etiqueta, font=fnt, fill=NEGRO)
        d.text((W - M, y), _formato_numero(valor), font=fnt, fill=NEGRO, anchor='ra')
        y += 44
    _linea_punteada(d, M, W - M, y)
    y += 30
    d.text((W // 2, y), 'Mes vencido: %s %d' % (factura['mes'], factura['anio']),
           font=f_pie, fill=GRIS, anchor='ma')
    y += 44
    img = img.crop((0, 0, W, y + 20))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _credenciales_telegram(conn):
    try:
        row = conn.execute(
            'SELECT telegram_token, telegram_chat_id FROM "CONFIGURACION_SISTEMA" WHERE id = 1'
        ).fetchone()
        if row and row['telegram_token'] and row['telegram_chat_id']:
            return row['telegram_token'], str(row['telegram_chat_id'])
    except Exception:
        pass
    return None, None


def _avisar_telegram(conn, png, numero, mes, anio, total, wa_url):
    import requests as _req
    import json as _json
    token, chat = _credenciales_telegram(conn)
    if not token:
        return False
    caption = 'Factura %s-%d · %s %d · %s lista para %s' % (
        TIPO_DOC_CODIGO, numero, mes, anio, _formato_numero(total), CLIENTE['nombre'])
    kb = _json.dumps({'inline_keyboard': [[{'text': 'Abrir WhatsApp de López', 'url': wa_url}]]})
    try:
        r = _req.post('https://api.telegram.org/bot%s/sendPhoto' % token,
                      data={'chat_id': chat, 'caption': caption, 'reply_markup': kb},
                      files={'photo': ('factura.png', png, 'image/png')}, timeout=25)
        return r.status_code == 200
    except Exception as e:
        print('[facturacion_mensual] telegram: %s' % e)
        return False


def _pendiente_agenda(conn, numero, mes, anio, total, link_factura):
    try:
        from .agenda import _asegurar_tabla
        _asegurar_tabla()
    except Exception:
        pass
    marca = '%s-%d' % (TIPO_DOC_CODIGO, numero)
    row = conn.execute(
        "SELECT id FROM agenda_items WHERE categoria = 'facturacion' AND texto LIKE %s "
        "AND completado = FALSE LIMIT 1",
        ('%' + marca + '%',)).fetchone()
    if row:
        return row['id']
    texto = 'Enviar factura %s (%s %d, %s) a %s: %s' % (
        marca, mes, anio, _formato_numero(total), CLIENTE['nombre'], link_factura)
    ins = conn.execute(
        "INSERT INTO agenda_items (texto, categoria) VALUES (%s, 'facturacion') RETURNING id",
        (texto,)).fetchone()
    conn.commit()
    return ins['id']


def _link_factura(token):
    return '%s/f/%s' % (BASE_URL, token)


def _emitir_aviso(conn, factura):
    """Telegram + agenda para una factura recien creada."""
    link = _link_factura(factura['token'])
    png = _render_imagen(factura)
    wa = _url_wa(_mensaje_whatsapp(link))
    ok_tg = _avisar_telegram(conn, png, factura['numero'], factura['mes'],
                             factura['anio'], factura['total'], wa)
    item_id = _pendiente_agenda(conn, factura['numero'], factura['mes'],
                                factura['anio'], factura['total'], link)
    return {'telegram': ok_tg, 'agenda_id': item_id, 'link': link, 'wa': wa}


def job_facturacion_mensual():
    conn = None
    try:
        if _ahora_bogota().day != 1:
            return
        conn = get_db_connection()
        res = _generar_factura(conn)
        if res.get('repetida'):
            return
        _emitir_aviso(conn, res['factura'])
    except Exception as e:
        print('[facturacion_mensual] job: %s' % e)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _es_admin():
    return session.get('rol') == 'Administrador'


@bp.route('/api/facturacion-mensual/generar', methods=['POST'])
def api_generar():
    if 'usuario_id' not in session or not _es_admin():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        res = _generar_factura(conn)
        if not res.get('repetida'):
            res.update(_emitir_aviso(conn, res['factura']))
        else:
            res['link'] = _link_factura(res['factura']['token'])
        return jsonify(res)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


@bp.route('/api/facturacion-mensual/estado')
def api_estado():
    if 'usuario_id' not in session or not _es_admin():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        datos = _asegurar_datos(conn)
        ult = _factura_del_mes(conn, datos['empresa_id'], datos['tipodoc_id'])
        td = conn.execute("SELECT consecutivo FROM tipos_documento_negocio WHERE id = %s",
                          (datos['tipodoc_id'],)).fetchone()
        return jsonify({'ok': True, 'ultima': ult,
                        'consecutivo': td['consecutivo'] if td else None,
                        'salto': [SALTO_MIN, SALTO_MAX]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _pedido_por_token(conn, token):
    _asegurar_columnas(conn)
    row = conn.execute(
        """SELECT id, numero, token_publico, total, created_at FROM pedidos
           WHERE token_publico = %s LIMIT 1""", (token,)).fetchone()
    if not row:
        return None
    mes, anio = _mes_vencido(row['created_at'].replace(tzinfo=BOGOTA)
                             if row['created_at'] and not row['created_at'].tzinfo
                             else (row['created_at'] or _ahora_bogota()))
    return {'pedido_id': row['id'], 'numero': int(row['numero']),
            'token': row['token_publico'], 'total': float(row['total'] or 0),
            'mes': MESES[mes - 1], 'anio': anio,
            'fecha': row['created_at'].isoformat() if row['created_at'] else ''}


@bp.route('/f/<token>')
def ver_factura(token):
    conn = get_db_connection()
    try:
        f = _pedido_por_token(conn, token)
        if not f:
            return 'Factura no encontrada', 404
        link = _link_factura(token)
        return render_template('factura_mensual.html', f=f, link=link,
                               imagen=link + '/imagen.png',
                               wa=_url_wa(_mensaje_whatsapp(link)),
                               total_fmt=_formato_numero(f['total']))
    finally:
        try:
            conn.close()
        except Exception:
            pass


@bp.route('/f/<token>/imagen.png')
def imagen_factura(token):
    conn = get_db_connection()
    try:
        f = _pedido_por_token(conn, token)
        if not f:
            return 'no', 404
        png = _render_imagen(f)
        return Response(png, mimetype='image/png',
                        headers={'Cache-Control': 'public, max-age=3600'})
    finally:
        try:
            conn.close()
        except Exception:
            pass
