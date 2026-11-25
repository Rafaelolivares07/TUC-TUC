"""Portada pública y datos de compra de invitado de Tuc-Tuc."""
import os
import re
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, url_for
from itsdangerous import BadData, URLSafeTimedSerializer

from ..asegurar import asegurar_una_vez
from ..db import get_db_connection

bp = Blueprint("marketplace", __name__)
COMPRADOR = "__Host-tuctuc_comprador"
PUBLICACION = "__Host-tuctuc_publicar"
VIGENCIA_PUBLICACION = 1800
VIGENCIA_COMPRADOR = 90 * 24 * 60 * 60
CATEGORIAS = frozenset(("productos", "restaurantes"))
LIMITE = 24

_OFERTAS = """
WITH ofertas AS (
    SELECT 'productos' AS tipo, p.id, p.nombre, p.categoria,
           t.nombre AS negocio, t.slug, p.precio, p.imagen
      FROM productos p
      JOIN tiendas t ON t.tercero_id = p.negocio_id
     WHERE t.activo IS TRUE AND (t.fecha_vence IS NULL OR t.fecha_vence >= CURRENT_DATE)
       AND p.disponible IS TRUE AND p.precio > 0 AND COALESCE(p.es_adicion, FALSE) = FALSE
    UNION ALL
    SELECT 'restaurantes', r.id, r.nombre, 'Carta y menú', r.nombre,
           r.slug, NULL::numeric, r.imagen_header
      FROM restaurantes r
     WHERE r.activo IS TRUE AND COALESCE(r.es_ejemplo, FALSE) = FALSE
)
SELECT tipo, id, nombre, categoria, negocio, slug, precio, imagen
  FROM ofertas
 WHERE (%s = '' OR tipo = %s)
   AND (%s = '' OR strpos(lower(concat_ws(' ', nombre, categoria, negocio)), lower(%s)) > 0)
 ORDER BY negocio, nombre, tipo, id
 LIMIT %s OFFSET %s
"""


def _texto(valor, maximo):
    return valor.strip()[:maximo] if isinstance(valor, str) else ""


def _telefono(valor):
    numero = re.sub(r"[^0-9]", "", _texto(valor, 25))
    if len(numero) == 12 and numero.startswith("57"):
        numero = numero[2:]
    return numero if len(numero) == 10 and numero.startswith("3") else ""


def _foto_publica(valor):
    if not isinstance(valor, str) or not valor or len(valor) > 1500:
        return ""
    valor = valor.strip()
    if valor.startswith(("/static/", "/uploads/")) and "\\" not in valor:
        return valor
    try:
        partes = urlsplit(valor)
        if partes.scheme == "https" and partes.hostname and not partes.username and not partes.password:
            return valor
    except ValueError:
        pass
    return ""


def _oferta(fila):
    producto = fila["tipo"] == "productos"
    if producto:
        enlace = url_for("tiendas.tienda_publica", slug=fila["slug"],
                         producto=fila["id"], origen="marketplace")
    else:
        enlace = url_for("restaurantes.restaurante_publico", slug=fila["slug"],
                         origen="marketplace")
    precio = fila["precio"]
    return dict(
        nombre=fila["nombre"], categoria=fila["categoria"], negocio=fila["negocio"],
        tipo=fila["tipo"], enlace=enlace, imagen=_foto_publica(fila["imagen"]),
        precio=("$" + f"{precio:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", "."))
        if precio is not None else "",
    )


@bp.get("/marketplace")
def portada():
    busqueda = _texto(request.args.get("q"), 100)
    categoria = _texto(request.args.get("categoria"), 20)
    categoria = categoria if categoria in CATEGORIAS else ""
    pagina = min(max(request.args.get("pagina", 1, type=int), 1), 1000)
    conn = get_db_connection()
    try:
        filas = conn.execute(
            _OFERTAS, (categoria, categoria, busqueda, busqueda, LIMITE + 1,
                       (pagina - 1) * LIMITE)
        ).fetchall()
    finally:
        conn.close()
    return render_template(
        "marketplace.html", ofertas=[_oferta(fila) for fila in filas[:LIMITE]],
        busqueda=busqueda, categoria=categoria, pagina=pagina, siguiente=len(filas) > LIMITE,
        comprador=datos_comprador(), aviso=request.args.get("publicacion") == "recibida",
    )


def _firma(uso):
    clave = os.environ.get("MARKETPLACE_SIGNING_KEY") or current_app.secret_key
    if not clave or clave == "dev-secret-key":
        abort(503)
    return URLSafeTimedSerializer(clave, salt="tuctuc-marketplace-" + uso)


def _firma_comprador():
    return _firma("comprador")


def _perfil_comprador():
    token = request.cookies.get(COMPRADOR)
    if not token:
        return None
    try:
        return _firma_comprador().loads(token, max_age=VIGENCIA_COMPRADOR)
    except BadData:
        return None


def datos_comprador():
    perfil = _perfil_comprador()
    return {campo: perfil[campo] for campo in ("nombre", "telefono")} if perfil else None


def _recordar(respuesta, nombre, telefono, cliente_id=None):
    actual = _perfil_comprador() or {}
    if cliente_id is None and actual.get("telefono") == telefono:
        cliente_id = actual.get("cliente_id")
    comprador = dict(nombre=nombre, telefono=telefono, cliente_id=cliente_id)
    if comprador != actual:
        respuesta.set_cookie(COMPRADOR, _firma_comprador().dumps(comprador),
                             max_age=VIGENCIA_COMPRADOR, secure=True, httponly=True, samesite="Lax")
    return respuesta


def _entero(valor, maximo=2_147_483_647):
    return valor if type(valor) is int and 1 <= valor <= maximo else None


def _coordenada(valor, limite):
    if type(valor) in (int, float) and -limite <= valor <= limite:
        return valor
    return None


def _lineas_pedido(lineas, clave, *, restaurante=False):
    if not isinstance(lineas, list) or not lineas or len(lineas) > 40:
        raise ValueError("Revisa los productos de tu pedido.")
    resultado = []
    for item in lineas:
        if not isinstance(item, dict):
            raise ValueError("Revisa los productos de tu pedido.")
        identidad = _entero(item.get(clave))
        cantidad = _entero(item.get("cantidad", 1), 99)
        if not identidad or not cantidad:
            raise ValueError("Revisa las cantidades de tu pedido.")
        linea = {clave: identidad, "cantidad": cantidad}
        if restaurante:
            linea["nota"] = _texto(item.get("nota"), 200)
            if item.get("adiciones"):
                linea["adiciones"] = _lineas_pedido(item["adiciones"], "producto_id")
        elif item.get("variante_id") is not None:
            variante = _entero(item["variante_id"])
            if not variante:
                raise ValueError("Revisa la variante de tu producto.")
            linea["variante_id"] = variante
        resultado.append(linea)
    return resultado


def datos_pedido(data, *, restaurante=False):
    perfil = _perfil_comprador()
    if not perfil or not perfil.get("cliente_id"):
        raise ValueError("Confirma de nuevo tus datos de contacto.")
    if not isinstance(data, dict):
        raise ValueError("Revisa los datos de tu pedido.")
    entrega = data.get("tipo_entrega")
    direccion = _texto(data.get("direccion_cliente"), 250)
    if entrega not in ("domicilio", "recoger") or (entrega == "domicilio" and not direccion):
        raise ValueError("Elige cómo quieres recibir tu pedido.")
    pedido = dict(
        cliente_id=perfil["cliente_id"], nombre_cliente=perfil["nombre"],
        telefono_cliente=perfil["telefono"], tipo_entrega=entrega,
        direccion_cliente=direccion, notas=_texto(data.get("notas"), 500),
        metodo_pago=_texto(data.get("metodo_pago"), 50) or "efectivo",
        cliente_lat=_coordenada(data.get("cliente_lat"), 90),
        cliente_lon=_coordenada(data.get("cliente_lon"), 180),
    )
    if not restaurante:
        pedido["items"] = _lineas_pedido(data.get("items"), "producto_id")
    elif data.get("platos"):
        pedido["platos"] = _lineas_pedido(data["platos"], "plato_id", restaurante=True)
    else:
        tipo_menu = data.get("tipo")
        if tipo_menu not in ("completo", "bandeja", "sopa"):
            raise ValueError("Elige un tipo de menú.")
        pedido["tipo"] = tipo_menu
        for campo in ("sopa_id", "proteina_id", "principio_id"):
            pedido[campo] = _entero(data.get(campo))
        if not any(pedido[campo] for campo in ("sopa_id", "proteina_id", "principio_id")):
            raise ValueError("Selecciona las opciones de tu menú.")
    return pedido


@bp.post("/api/marketplace/comprador")
def registrar_comprador():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, error="Envía los datos del pedido."), 400
    nombre = _texto(data.get("nombre"), 100)
    telefono = _telefono(data.get("telefono"))
    if not nombre or not telefono:
        return jsonify(ok=False, error="Escribe tu nombre y un celular colombiano válido."), 400

    conn = get_db_connection()
    try:
        # Serializa las altas de invitado del mismo celular.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("comprador:" + telefono,))
        tercero = conn.execute(
            """SELECT id FROM terceros
                WHERE telefono IN (%s, %s, %s)
                  AND COALESCE(tipo_tercero, '') <> 'negocio' AND es_empresa IS NOT TRUE
                ORDER BY CASE WHEN telefono = %s THEN 0 ELSE 1 END, id LIMIT 1""",
            (telefono, "57" + telefono, "+57" + telefono, telefono),
        ).fetchone()
        if not tercero:
            tercero = conn.execute(
                """INSERT INTO terceros (nombre, telefono, tipo_tercero, fecha_creacion)
                   VALUES (%s, %s, 'cliente', NOW()) RETURNING id""",
                (nombre, telefono),
            ).fetchone()
        conn.commit()
    except Exception:
        current_app.logger.exception("Error al registrar comprador del Marketplace")
        conn.rollback()
        return jsonify(ok=False, error="No pudimos registrar los datos del pedido. Intenta otra vez."), 503
    finally:
        conn.close()
    return _recordar(jsonify(ok=True, cliente_id=tercero["id"]), nombre, telefono, tercero["id"])

def _firma_pedidos():
    return _firma("pedidos")


def _pedidos_navegador():
    token = request.cookies.get("__Host-tuctuc_pedidos")
    if token:
        try:
            return _firma_pedidos().loads(token, max_age=86400)
        except BadData:
            pass
    return {}


def respuesta_pedido(tipo, pedido_id, cuerpo, pedidos=None):
    historial = _pedidos_navegador()
    historial[str(pedido_id)] = [tipo, pedidos or [pedido_id]]
    permitidos = dict(list(historial.items())[-6:])
    cuerpo["url_pago"] = url_for("negocios.pagar_marketplace", pedido_id=pedido_id, tipo=tipo)
    respuesta = jsonify(cuerpo)
    respuesta.set_cookie("__Host-tuctuc_pedidos", _firma_pedidos().dumps(permitidos),
                         max_age=86400, secure=True, httponly=True, samesite="Lax")
    return respuesta


def ids_pago(pedido_id, tipo):
    permiso = _pedidos_navegador().get(str(pedido_id))
    return permiso[1] if permiso and permiso[0] == tipo else ()


def _crear_solicitudes(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketplace_solicitudes (
            id bigserial PRIMARY KEY,
            token text NOT NULL UNIQUE,
            nombre text NOT NULL,
            telefono text NOT NULL,
            tipo text NOT NULL CHECK (tipo IN ('producto', 'servicio')),
            titulo text NOT NULL,
            descripcion text NOT NULL,
            estado text NOT NULL DEFAULT 'recibida',
            creado_en timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.commit()


def _token_publicacion():
    valor = request.cookies.get(PUBLICACION)
    if valor:
        try:
            return _firma("publicar").loads(valor, max_age=VIGENCIA_PUBLICACION)
        except BadData:
            pass
    return None


@bp.get("/marketplace/publicar")
def publicar():
    anterior = _token_publicacion()
    token = anterior or secrets.token_urlsafe(32)
    respuesta = make_response(render_template(
        "marketplace_publicar.html", token=token, comprador=datos_comprador(), datos={}, error=None,
    ))
    if not anterior:
        respuesta.set_cookie(PUBLICACION, _firma("publicar").dumps(token),
                             max_age=VIGENCIA_PUBLICACION, secure=True, httponly=True, samesite="Lax")
    return respuesta


@bp.post("/marketplace/publicar")
def recibir_publicacion():
    token = _token_publicacion()
    if not token or not secrets.compare_digest(token.encode(), _texto(request.form.get("token"), 60).encode()):
        return render_template("marketplace_publicar.html", token=None, comprador=datos_comprador(),
                               datos={}, error="Abre de nuevo el formulario para enviar tu publicación."), 400
    datos = {clave: _texto(request.form.get(clave), limite) for clave, limite in
             (("nombre", 100), ("telefono", 25), ("tipo", 12), ("titulo", 120), ("descripcion", 1000))}
    datos["telefono"] = _telefono(datos["telefono"])
    if (not all(datos.values()) or datos["tipo"] not in ("producto", "servicio")):
        return render_template("marketplace_publicar.html", token=token, comprador=datos_comprador(),
                               datos=datos, error="Completa los datos y escribe un celular colombiano válido."), 400
    conn = get_db_connection()
    try:
        asegurar_una_vez("marketplace.solicitudes", lambda: _crear_solicitudes(conn))
        conn.execute(
            """INSERT INTO marketplace_solicitudes (token, nombre, telefono, tipo, titulo, descripcion)
               VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (token) DO NOTHING""",
            (token, datos["nombre"], datos["telefono"], datos["tipo"], datos["titulo"], datos["descripcion"]),
        )
        conn.commit()
    except Exception:
        current_app.logger.exception("Error al registrar solicitud de Marketplace")
        conn.rollback()
        return render_template("marketplace_publicar.html", token=token, comprador=datos_comprador(),
                               datos=datos, error="No pudimos guardar tu solicitud. Intenta otra vez."), 503
    finally:
        conn.close()
    respuesta = redirect(url_for("marketplace.portada", publicacion="recibida"), code=303)
    respuesta.delete_cookie(PUBLICACION, secure=True, httponly=True, samesite="Lax")
    return _recordar(respuesta, datos["nombre"], datos["telefono"])
