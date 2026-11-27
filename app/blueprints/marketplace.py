"""Portada pública y datos de compra de invitado de Tuc-Tuc."""
import json
import os
from base64 import b64decode
from binascii import Error as ErrorBase64
from decimal import Decimal
from io import BytesIO
import re
import secrets
from urllib.parse import urlencode, urlsplit

from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, session, url_for
from itsdangerous import BadData, URLSafeTimedSerializer

from ..asegurar import asegurar_una_vez
from ..db import get_db_connection
from ..tipo_oferta import TIPO_OFERTA_SQL, asegurar_tipo_oferta

bp = Blueprint("marketplace", __name__)
COMPRADOR = "__Host-tuctuc_comprador"
PUBLICACION = "__Host-tuctuc_publicar"
VIGENCIA_PUBLICACION = 30 * 86400
LIMITE_FOTOS_PUBLICACION = 7 * 1024 * 1024
LIMITE_FOTO_PUBLICACION = 450_000
LIMITE_ICONO_OFERTANTE = 160_000
DIMENSION_ICONO_OFERTANTE = 320
VIGENCIA_COMPRADOR = 90 * 24 * 60 * 60
CATEGORIAS = {"": "Todo", "restaurantes": "Comida y bebidas",
              "productos": "Productos", "servicios": "Servicios"}
LIMITE = 24
METODO_CONTRAENTREGA = "contraentrega"

_PRODUCTOS_PUBLICOS = """
      FROM productos p
      JOIN tiendas t ON t.tercero_id = p.negocio_id
     WHERE t.activo IS TRUE AND (t.fecha_vence IS NULL OR t.fecha_vence >= CURRENT_DATE)
       AND p.disponible IS TRUE AND p.precio > 0 AND COALESCE(p.es_adicion, FALSE) = FALSE
"""
_RESTAURANTES_PUBLICOS = """
      FROM restaurantes r
     WHERE r.activo IS TRUE AND COALESCE(r.es_ejemplo, FALSE) = FALSE
"""
_FOTO_PRODUCTO = """
    COALESCE(NULLIF(btrim(p.imagen), ''), (
        SELECT pi.imagen FROM producto_imagenes pi
         WHERE pi.producto_id = p.id AND NULLIF(btrim(pi.imagen), '') IS NOT NULL
         ORDER BY pi.orden, pi.id LIMIT 1
    ))
"""
_FORMATOS_FOTO = {
    "data:image/jpeg;base64": "image/jpeg",
    "data:image/png;base64": "image/png",
    "data:image/webp;base64": "image/webp",
    "data:image/gif;base64": "image/gif",
}
_LIMITE_FOTO = 8 * 1024 * 1024

_PUBLICACIONES_APROBADAS = """
      FROM marketplace_solicitudes s JOIN productos p ON p.id=s.producto_id
      JOIN terceros ofertante ON ofertante.id=p.negocio_id
     WHERE p.disponible IS TRUE
"""
_NOMBRE_OFERTANTE = """CASE WHEN s.contacto_aprobado OR ofertante.icono_marketplace IS NOT NULL
                            THEN s.nombre END"""
_ORIGEN_PUBLICACION = f"COALESCE({_NOMBRE_OFERTANTE}, 'Publicación particular')"
_AMBITO_PRODUCTO = f"CASE WHEN {TIPO_OFERTA_SQL} = 'servicio' THEN 'servicios' ELSE 'productos' END"
_AMBITO_CARTA = f"CASE WHEN {TIPO_OFERTA_SQL} = 'servicio' THEN 'servicios' ELSE 'restaurantes' END"


_PLATOS_PUBLICOS = """
      FROM productos p
      JOIN restaurantes r ON r.tercero_id = p.negocio_id
     WHERE r.activo IS TRUE AND COALESCE(r.es_ejemplo, FALSE) = FALSE
       AND r.tipo_restaurante IN ('carta', 'ambos')
       AND p.disponible IS TRUE AND p.precio > 0 AND COALESCE(p.es_adicion, FALSE) = FALSE
       AND (r.tipo_restaurante = 'carta' OR lower(btrim(COALESCE(p.categoria, '')))
            NOT IN ('sopa', 'proteina', 'proteína', 'principio'))
"""
_OFERTAS = f"""
WITH ofertas AS (
    SELECT 'productos' AS tipo, p.id, p.nombre, p.categoria,
           t.nombre AS negocio, t.slug, p.precio, left({_FOTO_PRODUCTO}, 1501) AS imagen,
           {_AMBITO_PRODUCTO} AS ambito
      {_PRODUCTOS_PUBLICOS}
    UNION ALL
    SELECT 'platos', p.id, p.nombre, p.categoria, r.nombre, r.slug, p.precio,
           left({_FOTO_PRODUCTO}, 1501), 'servicios'
      {_PLATOS_PUBLICOS} AND {TIPO_OFERTA_SQL} = 'servicio'
    UNION ALL
    SELECT 'restaurantes', r.id, r.nombre, 'Carta y menú', r.nombre,
           r.slug, NULL::numeric, left(r.imagen_header, 1501), 'restaurantes'
      {_RESTAURANTES_PUBLICOS}
    UNION ALL
    SELECT 'publicaciones', p.id, p.nombre, p.categoria, {_ORIGEN_PUBLICACION}, NULL,
           NULLIF(p.precio,0), left(p.imagen,1501), {_AMBITO_PRODUCTO}
      {_PUBLICACIONES_APROBADAS}
)
SELECT tipo, id, nombre, categoria, negocio, slug, precio, imagen, ambito
  FROM ofertas
 WHERE (%s = '' OR ambito = %s)
   AND (%s = '' OR strpos(lower(concat_ws(' ', nombre, categoria, negocio)), lower(%s)) > 0)
 ORDER BY (NULLIF(btrim(imagen), '') IS NOT NULL) DESC, negocio, nombre, tipo, id
 LIMIT %s OFFSET %s
"""

_ACENTOS = "áéíóúüñ"
_SIN_ACENTOS = "aeiouun"
_TRADUCCION = str.maketrans(_ACENTOS, _SIN_ACENTOS)


def _normalizar_busqueda(texto):
    return " ".join(re.findall(r"\w+", texto.lower().translate(_TRADUCCION)))


_CATEGORIA_BUSQUEDA = """
    btrim(regexp_replace(COALESCE(p.categoria, ''),
          '^[[:space:]]*[0-9]+[.)-][[:space:]]*', ''))
"""


_BUSQUEDA = f"""
WITH venta AS (
    SELECT 'productos' AS tipo, p.id, p.nombre, {_CATEGORIA_BUSQUEDA} AS categoria,
           t.nombre AS negocio, t.slug, p.precio, {_AMBITO_PRODUCTO} AS ambito, 0 AS grupo
      {_PRODUCTOS_PUBLICOS}
    UNION ALL
    SELECT 'platos', p.id, p.nombre, {_CATEGORIA_BUSQUEDA}, r.nombre, r.slug, p.precio, {_AMBITO_CARTA}, 0
      {_PLATOS_PUBLICOS}
    UNION ALL
    SELECT 'publicaciones', p.id, p.nombre, p.categoria, {_ORIGEN_PUBLICACION},
           NULL, NULLIF(p.precio,0), {_AMBITO_PRODUCTO}, 0
      {_PUBLICACIONES_APROBADAS}
), fichas AS (
    SELECT * FROM venta
    UNION ALL
    SELECT 'categorias', 0, min(categoria), NULL, NULL, NULL, NULL, '', 1
      FROM venta
     WHERE NULLIF(categoria, '') IS NOT NULL
       AND lower(categoria) NOT IN ('carta', 'sin categoria', 'sin categoría')
       AND (%(ambito)s = '' OR ambito = %(ambito)s)
     GROUP BY translate(lower(categoria), '{_ACENTOS}', '{_SIN_ACENTOS}')
    UNION ALL
    SELECT 'tiendas', t.id, t.nombre, 'Tienda', t.nombre, t.slug, NULL, 'productos', 2
      FROM tiendas t
     WHERE t.activo IS TRUE AND (t.fecha_vence IS NULL OR t.fecha_vence >= CURRENT_DATE)
    UNION ALL
    SELECT 'restaurantes', r.id, r.nombre, 'Restaurante', r.nombre, r.slug, NULL, 'restaurantes', 2
      {_RESTAURANTES_PUBLICOS}
), nombres AS (
    SELECT *, translate(lower(btrim(regexp_replace(nombre, '[^[:alnum:]_]+', ' ', 'g'))),
                        '{_ACENTOS}', '{_SIN_ACENTOS}') AS termino,
           CASE WHEN ambito = 'servicios' THEN
                translate(lower(regexp_replace(negocio, '[^[:alnum:]_]+', ' ', 'g')),
                          '{_ACENTOS}', '{_SIN_ACENTOS}')
           END AS termino_negocio
      FROM fichas
     WHERE (%(ambito)s = '' OR ambito IN ('', %(ambito)s))
       AND (%(rubro)s = '' OR (grupo = 0 AND
            translate(lower(btrim(regexp_replace(categoria, '[^[:alnum:]_]+', ' ', 'g'))),
                      '{_ACENTOS}', '{_SIN_ACENTOS}') = %(rubro)s))
), coincidencias AS (
    SELECT *, CASE
            WHEN termino = %(q)s THEN 3
            WHEN starts_with(termino, %(q)s) THEN 2
            WHEN strpos(termino, %(q)s) > 0 THEN 1
            ELSE 0 END AS relevancia
      FROM nombres
     WHERE %(q)s = '' OR NOT EXISTS (
        SELECT 1 FROM unnest(string_to_array(%(q)s, ' ')) AS palabras(palabra)
         WHERE NOT EXISTS (
            SELECT 1 FROM unnest(string_to_array(concat_ws(' ', termino, termino_negocio), ' ')) AS nombre(palabra_publica)
             WHERE starts_with(palabra_publica, palabra)
         )
     )
), enumeradas AS (
    SELECT *, row_number() OVER (
        PARTITION BY grupo ORDER BY relevancia DESC, termino, negocio, tipo, id
    ) AS posicion
      FROM coincidencias
), pagina AS (
    SELECT * FROM enumeradas
     WHERE NOT %(sugerencias)s OR posicion <= CASE WHEN grupo = 0 THEN 3 ELSE 2 END
     ORDER BY grupo, posicion
     LIMIT %(limite)s OFFSET %(offset)s
)
SELECT f.*, CASE f.tipo
        WHEN 'productos' THEN (SELECT left({_FOTO_PRODUCTO}, 1501) FROM productos p WHERE p.id = f.id)
        WHEN 'platos' THEN (SELECT left({_FOTO_PRODUCTO}, 1501) FROM productos p WHERE p.id = f.id)
        WHEN 'publicaciones' THEN (SELECT left(p.imagen,1501) FROM productos p WHERE p.id=f.id)
        WHEN 'restaurantes' THEN (SELECT left(r.imagen_header, 1501) FROM restaurantes r WHERE r.id = f.id)
        ELSE NULL END AS imagen
  FROM pagina f
 ORDER BY f.grupo, f.posicion
"""


def _buscar(conn, q, ambito="", rubro="", pagina=1, sugerencias=False):
    return conn.execute(_BUSQUEDA, {
        "q": _normalizar_busqueda(q), "ambito": ambito,
        "rubro": _normalizar_busqueda(rubro), "sugerencias": sugerencias,
        "limite": 7 if sugerencias else LIMITE + 1,
        "offset": (pagina - 1) * LIMITE,
    }).fetchall()


_CONSULTAS_FOTO = {
    "publicaciones": f"SELECT p.imagen AS imagen {_PUBLICACIONES_APROBADAS} AND p.id = %s",
    "ofertantes": f"SELECT ofertante.icono_marketplace AS imagen {_PUBLICACIONES_APROBADAS} AND p.id = %s",
    "platos": f"SELECT {_FOTO_PRODUCTO} AS imagen {_PLATOS_PUBLICOS} AND p.id = %s LIMIT 1",
    "productos": f"SELECT {_FOTO_PRODUCTO} AS imagen {_PRODUCTOS_PUBLICOS} AND p.id = %s LIMIT 1",
    "restaurantes": f"SELECT r.imagen_header AS imagen {_RESTAURANTES_PUBLICOS} AND r.id = %s",
}


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


@bp.get("/static/marketplace/fotos/<tipo>/<int:oferta_id>")
def foto(tipo, oferta_id):
    consulta = _CONSULTAS_FOTO.get(tipo)
    if consulta is None or not 1 <= oferta_id <= 2_147_483_647:
        abort(404)
    conn = _conexion_publicaciones() if tipo in ("publicaciones", "ofertantes") else get_db_connection()
    try:
        fila = conn.execute(consulta, (oferta_id,)).fetchone()
    finally:
        conn.close()

    return _servir_imagen(fila, max_age=0 if tipo == "ofertantes" else 300)


def _servir_imagen(fila, max_age=300):
    imagen = fila["imagen"] if fila else None
    if not imagen or len(imagen) > _LIMITE_FOTO:
        abort(404)
    encabezado, separador, contenido = imagen.partition(",")
    formato = _FORMATOS_FOTO.get(encabezado.lower())
    if not separador or not formato:
        abort(404)
    try:
        datos = b64decode(contenido, validate=True)
    except ErrorBase64:
        abort(404)
    if not datos:
        abort(404)

    respuesta = make_response(datos)
    respuesta.mimetype = formato
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.cache_control.public = True
    respuesta.cache_control.max_age = max_age
    if max_age == 0:
        respuesta.cache_control.must_revalidate = True
    respuesta.add_etag()
    return respuesta.make_conditional(request)


def _precio_visible(precio):
    return ("$" + f"{precio:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")) if precio is not None else ""


_HOSTS_MARKETPLACE_PROD = ("tuc-tuc.co", "www.tuc-tuc.co")


def _en_prod_marketplace():
    try:
        return request.host.split(":", 1)[0].lower() in _HOSTS_MARKETPLACE_PROD
    except RuntimeError:
        return False


def _url_negocio(slug, **params):
    base = f"https://{slug}.tuc-tuc.co/"
    return base + ("?" + urlencode(params) if params else "")


def _oferta(fila, ambito=""):
    tipo = fila["tipo"]
    externa = tipo in ("productos", "platos", "tiendas", "restaurantes")
    absoluta = externa and _en_prod_marketplace()
    if tipo == "productos":
        if absoluta:
            enlace = _url_negocio(fila["slug"], producto=fila["id"], origen="marketplace")
        else:
            enlace = url_for("tiendas.tienda_publica", slug=fila["slug"],
                             producto=fila["id"], origen="marketplace")
    elif tipo == "platos":
        if absoluta:
            enlace = _url_negocio(fila["slug"], plato=fila["id"], origen="marketplace")
        else:
            enlace = url_for("restaurantes.restaurante_publico", slug=fila["slug"],
                             plato=fila["id"], origen="marketplace")
    elif tipo == "publicaciones":
        enlace = url_for("marketplace.portada", oferta=fila["id"])
    elif tipo == "categorias":
        enlace = url_for("marketplace.portada", categoria=ambito, rubro=fila["nombre"], _anchor="explorar")
    elif tipo == "tiendas":
        if absoluta:
            enlace = _url_negocio(fila["slug"], origen="marketplace")
        else:
            enlace = url_for("tiendas.tienda_publica", slug=fila["slug"], origen="marketplace")
    else:
        if absoluta:
            enlace = _url_negocio(fila["slug"], origen="marketplace")
        else:
            enlace = url_for("restaurantes.restaurante_publico", slug=fila["slug"], origen="marketplace")

    origen_foto = fila["imagen"] or ""
    if origen_foto.partition(",")[0].lower() in _FORMATOS_FOTO:
        imagen = url_for("marketplace.foto", tipo=tipo, oferta_id=fila["id"])
    else:
        imagen = _foto_publica(origen_foto)
    try:
        precio_num = float(fila["precio"]) if fila["precio"] is not None else None
    except (TypeError, ValueError):
        precio_num = None
    return dict(
        nombre=fila["nombre"], categoria=fila["categoria"], negocio=fila["negocio"],
        tipo=tipo, enlace=enlace, imagen=imagen, es_servicio=fila.get("ambito") == "servicios",
        precio=_precio_visible(fila["precio"]), externa=externa,
        comprable=tipo in ("productos", "platos"),
        negocio_slug=fila.get("slug"), oferta_id=fila.get("id"), precio_num=precio_num,
    )


def _detalle_publicacion(producto_id):
    conn = _conexion_publicaciones()
    try:
        fila = conn.execute(f"""
            SELECT p.id,p.nombre,p.categoria,p.descripcion, NULLIF(p.precio,0) AS precio,
                   left(p.imagen,1501) AS imagen,
                   (SELECT nombre FROM metodos_pago_catalogo
                     WHERE id=s.metodo_pago_aprobado_id AND activo IS TRUE) AS metodo_pago,
                   CASE WHEN s.contacto_aprobado THEN s.telefono ELSE NULL END AS contacto,
                   {_NOMBRE_OFERTANTE} AS nombre_ofertante,
                   ofertante.icono_marketplace IS NOT NULL AS tiene_icono_ofertante
              {_PUBLICACIONES_APROBADAS} AND p.id=%s
        """, (producto_id,)).fetchone()
        if not fila:
            abort(404)
        galeria = conn.execute(
            "SELECT id FROM producto_imagenes WHERE producto_id=%s ORDER BY orden,id", (producto_id,)
        ).fetchall()
    finally:
        conn.close()
    fotos = []
    if fila["imagen"]:
        fotos.append(url_for("marketplace.foto", tipo="publicaciones", oferta_id=producto_id))
    fotos.extend(url_for("marketplace.foto_publicacion_extra", producto_id=producto_id, foto_id=img["id"])
                 for img in galeria)
    return render_template("marketplace_oferta.html", producto=fila, fotos=fotos,
                           precio=_precio_visible(fila["precio"]))


@bp.get("/static/marketplace/fotos/publicaciones/<int:producto_id>/<int:foto_id>")
def foto_publicacion_extra(producto_id, foto_id):
    if not 1 <= producto_id <= 2_147_483_647 or not 1 <= foto_id <= 2_147_483_647:
        abort(404)
    conn = _conexion_publicaciones()
    try:
        fila = conn.execute(f"""
            SELECT (SELECT pi.imagen FROM producto_imagenes pi
                        WHERE pi.producto_id=p.id AND pi.id=%s) AS imagen
              {_PUBLICACIONES_APROBADAS} AND p.id=%s
        """, (foto_id, producto_id)).fetchone()
    finally:
        conn.close()
    return _servir_imagen(fila)


@bp.get("/marketplace")
def portada():
    producto_id = request.args.get("oferta", type=int)
    if producto_id is not None:
        if not 1 <= producto_id <= 2_147_483_647:
            abort(404)
        return _detalle_publicacion(producto_id)
    busqueda = _texto(request.args.get("q"), 100)
    categoria = _texto(request.args.get("categoria"), 20)
    categoria = categoria if categoria in CATEGORIAS else ""
    rubro = _texto(request.args.get("rubro"), 100)
    sugerencias = request.args.get("sugerencias") == "1"
    pagina = 1 if sugerencias else min(max(request.args.get("pagina", 1, type=int), 1), 1000)
    if sugerencias and len(_normalizar_busqueda(busqueda)) < 2:
        return jsonify(sugerencias=[])
    conn = _conexion_publicaciones()
    try:
        if busqueda and not _normalizar_busqueda(busqueda):
            filas = []
        elif busqueda or rubro:
            filas = _buscar(conn, busqueda, categoria, rubro, pagina, sugerencias)
        else:
            filas = conn.execute(
                _OFERTAS, (categoria, categoria, "", "", LIMITE + 1, (pagina - 1) * LIMITE)
            ).fetchall()
    finally:
        conn.close()
    ofertas = [_oferta(fila, categoria) for fila in filas[:LIMITE]]
    if sugerencias:
        return jsonify(sugerencias=ofertas)
    return render_template(
        "marketplace.html", ofertas=ofertas, busqueda=busqueda, categoria=categoria, categorias=CATEGORIAS,
        rubro=rubro, pagina=pagina, siguiente=len(filas) > LIMITE, comprador=datos_comprador(),
        usuario=usuario_sesion(),
        aviso=request.args.get("publicacion") == "recibida",
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


def usuario_sesion():
    """Tercero identificado por la sesión TucTuc (admin, negocio, cliente, SU).

    chat_tercero_id manda (lo escriben admin, core, crm, compras); si falta,
    usuario_id vale cuando el rol no es Administrador (tienda, restaurante,
    cliente, SU). Todo se valida contra terceros: lo que no existe se ignora.
    Incluye los negocios donde vende (tiendas y restaurantes propios).
    """
    candidatos = [session.get("chat_tercero_id")]
    if session.get("rol") != "Administrador":
        candidatos.append(session.get("usuario_id"))
    candidatos = [c for c in candidatos if type(c) is int and c > 0]
    if not candidatos:
        return None
    conn = get_db_connection()
    try:
        for tid in candidatos:
            fila = conn.execute(
                "SELECT id, nombre, telefono, direccion FROM terceros WHERE id = %s",
                (tid,),
            ).fetchone()
            if not fila:
                continue
            negs = conn.execute(
                "SELECT 'tienda' AS tipo, nombre, slug FROM tiendas "
                "WHERE tercero_id = %s AND activo IS TRUE "
                "UNION ALL SELECT 'restaurante', nombre, slug FROM restaurantes "
                "WHERE tercero_id = %s AND activo IS TRUE ORDER BY nombre",
                (fila["id"], fila["id"]),
            ).fetchall()
            return {"id": fila["id"], "nombre": fila["nombre"],
                    "telefono": fila["telefono"] or "", "direccion": fila["direccion"] or "",
                    "negocios": [{"tipo": n["tipo"], "nombre": n["nombre"], "slug": n["slug"]}
                                 for n in negs]}
    finally:
        conn.close()
    return None


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


@bp.post("/api/marketplace/identificar")
def identificar_comprador():
    """Entrada con celular + PIN (mismo molde que rockola/identificar).

    Con PIN correcto abre sesión de Cliente; en primer uso fija el PIN
    (tercero existente sin PIN) o crea el tercero invitado (con nombre).
    """
    from werkzeug.security import check_password_hash, generate_password_hash
    data = request.get_json(silent=True) or {}
    telefono = (data.get("telefono") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    pin = (data.get("pin") or "").strip()
    tel_limpio = "".join(c for c in telefono if c.isdigit())
    if not tel_limpio:
        return jsonify(ok=False, error="Celular requerido."), 400
    if len(pin) != 4 or not pin.isdigit():
        return jsonify(ok=False, error="El PIN debe tener 4 números."), 400
    conn = get_db_connection()
    try:
        tercero = conn.execute(
            "SELECT id, nombre, pin_seguridad FROM terceros "
            "WHERE REGEXP_REPLACE(COALESCE(telefono, ''), '[^0-9]', '', 'g') = %s LIMIT 1",
            (tel_limpio,),
        ).fetchone()
        if tercero:
            if tercero["pin_seguridad"]:
                if not check_password_hash(tercero["pin_seguridad"], pin):
                    return jsonify(ok=False, error="PIN incorrecto."), 401
            else:
                conn.execute("UPDATE terceros SET pin_seguridad = %s WHERE id = %s",
                             (generate_password_hash(pin), tercero["id"]))
                conn.commit()
            tercero_id, nombre_final = tercero["id"], tercero["nombre"]
        else:
            if not nombre:
                return jsonify(ok=False, error="Escribe tu nombre para crear tu cuenta."), 400
            cur = conn.execute(
                "INSERT INTO terceros (nombre, telefono, pin_seguridad, tipo_tercero) "
                "VALUES (%s, %s, %s, 'invitado') RETURNING id",
                (nombre, telefono, generate_password_hash(pin)),
            )
            tercero_id = cur.fetchone()["id"]
            conn.commit()
            nombre_final = nombre
        session["usuario_id"] = tercero_id
        session["nombre"] = nombre_final
        session["telefono"] = telefono
        session["rol"] = "Cliente"
        return jsonify(ok=True, tercero_id=tercero_id, nombre=nombre_final)
    finally:
        conn.close()


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
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("marketplace.solicitudes.schema",))
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
    conn.execute("""
        ALTER TABLE marketplace_solicitudes
        ADD COLUMN IF NOT EXISTS fotos jsonb NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS producto_id integer REFERENCES productos(id),
        ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1,
        ADD COLUMN IF NOT EXISTS contacto_publico boolean NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS contacto_aprobado boolean NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS icono_ofertante text,
        ADD COLUMN IF NOT EXISTS cambiar_icono_ofertante boolean NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS icono_ofertante_aprobado text,
        ADD COLUMN IF NOT EXISTS precio numeric(10,2) CHECK (precio > 0),
        ADD COLUMN IF NOT EXISTS acepta_contraentrega boolean,
        ADD COLUMN IF NOT EXISTS metodo_pago_aprobado_id integer REFERENCES metodos_pago_catalogo(id)
    """)
    if not conn.execute("""
        SELECT 1 FROM pg_attribute
         WHERE attrelid='terceros'::regclass AND attname='icono_marketplace' AND NOT attisdropped
    """).fetchone():
        conn.execute("ALTER TABLE terceros ADD COLUMN IF NOT EXISTS icono_marketplace text")
        conn.execute("""
            UPDATE terceros t SET icono_marketplace=anterior.icono_ofertante_aprobado
              FROM (
                  SELECT DISTINCT ON (p.negocio_id) p.negocio_id, s.icono_ofertante_aprobado
                    FROM marketplace_solicitudes s JOIN productos p ON p.id=s.producto_id
                   WHERE s.icono_ofertante_aprobado IS NOT NULL
                   ORDER BY p.negocio_id, s.id DESC
              ) anterior
             WHERE t.id=anterior.negocio_id
        """)
        conn.execute("""
            UPDATE marketplace_solicitudes SET cambiar_icono_ofertante=TRUE
             WHERE estado='recibida' AND icono_ofertante IS NOT NULL
               AND icono_ofertante IS DISTINCT FROM icono_ofertante_aprobado
        """)
    conn.commit()


def _fotos_publicacion(fotos, *, limite_foto=LIMITE_FOTO_PUBLICACION, dimension=800):
    if sum(map(len, fotos)) > LIMITE_FOTOS_PUBLICACION:
        raise ValueError("Las fotos superan el tamaño total permitido.")
    if not fotos:
        return fotos
    from PIL import Image

    for foto in fotos:
        encabezado, separador, contenido = foto.partition(",")
        if (len(foto) > limite_foto or not separador
                or encabezado != "data:image/jpeg;base64"):
            raise ValueError("Una foto supera el tamaño permitido o tiene un formato inválido.")
        try:
            datos = b64decode(contenido, validate=True)
            with Image.open(BytesIO(datos), formats=("JPEG",)) as imagen:
                if max(imagen.size) > dimension:
                    raise ValueError("Una foto supera el tamaño permitido. Vuelve a seleccionarla.")
                imagen.load()
        except (ErrorBase64, OSError, Image.DecompressionBombError):
            raise ValueError("No se pudo leer una de las fotos. Vuelve a seleccionarla.") from None
    return fotos


def _formulario_publicacion(token, datos, error=None, solicitudes=(), aviso=False):
    return render_template(
        "marketplace_publicar.html", token=token, comprador=datos_comprador(), datos=datos,
        error=error, limite_fotos=LIMITE_FOTOS_PUBLICACION, limite_foto=LIMITE_FOTO_PUBLICACION,
        solicitudes=solicitudes, aviso=aviso, limite_icono=LIMITE_ICONO_OFERTANTE,
        dimension_icono=DIMENSION_ICONO_OFERTANTE,
    )


def _sesion_publicacion():
    valor = request.cookies.get(PUBLICACION)
    if not valor:
        return {}
    try:
        datos = _firma("publicar").loads(valor, max_age=VIGENCIA_PUBLICACION)
    except BadData:
        return {}
    # Los navegadores que ya tenían abierto el formulario conservan su token.
    return {"token": datos} if isinstance(datos, str) else datos


def _cookie_editor(respuesta, sesion, solicitud_id=None):
    if solicitud_id is not None:
        anteriores = sesion.get("solicitudes", [])
        sesion["solicitudes"] = [x for x in anteriores if x != solicitud_id][-49:] + [solicitud_id]
    respuesta.set_cookie(PUBLICACION, _firma("publicar").dumps(sesion),
                         max_age=VIGENCIA_PUBLICACION, secure=True, httponly=True, samesite="Lax")
    return respuesta


def _conexion_publicaciones():
    conn = get_db_connection()
    asegurar_tipo_oferta(conn)
    asegurar_una_vez("marketplace.solicitudes", lambda: _crear_solicitudes(conn))
    return conn


def _solicitudes_editor(identidades, actual=None):
    if not identidades:
        return None, []
    conn = _conexion_publicaciones()
    try:
        resumen = conn.execute(
            """SELECT id, titulo, estado FROM marketplace_solicitudes
                WHERE id = ANY(%s) ORDER BY id DESC""", (identidades,)
        ).fetchall()
        seleccion = conn.execute(
            """SELECT s.id, s.nombre, s.telefono, s.tipo, s.titulo, s.descripcion, s.fotos, s.estado,
                      s.revision, s.contacto_publico, s.acepta_contraentrega,
                      CASE WHEN s.cambiar_icono_ofertante THEN COALESCE(s.icono_ofertante,'') END AS icono_ofertante,
                      ofertante.icono_marketplace AS icono_actual,
                      COALESCE(s.precio, NULLIF(p.precio,0)) AS precio
                 FROM marketplace_solicitudes s LEFT JOIN productos p ON p.id=s.producto_id
                 LEFT JOIN terceros ofertante ON ofertante.id=p.negocio_id
                WHERE s.id = %s""", (actual,)
        ).fetchone() if actual is not None else None
        return seleccion, resumen
    finally:
        conn.close()


@bp.get("/marketplace/publicar")
def publicar():
    sesion = _sesion_publicacion()
    renovar = not sesion.get("token")
    if renovar:
        sesion["token"] = secrets.token_urlsafe(32)
    acceso = request.args.get("acceso")
    if acceso:
        try:
            solicitud_id = _firma("enlace-edicion").loads(acceso, max_age=7 * 86400)
        except BadData:
            return _formulario_publicacion(None, {}, "Este enlace venció. Pide un nuevo enlace de edición."), 400
        conn = _conexion_publicaciones()
        try:
            existe = conn.execute("SELECT 1 FROM marketplace_solicitudes WHERE id = %s", (solicitud_id,)).fetchone()
        finally:
            conn.close()
        if not existe:
            abort(404)
        respuesta = redirect(url_for("marketplace.publicar", solicitud=solicitud_id), code=303)
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        return _cookie_editor(respuesta, sesion, solicitud_id)

    solicitud_id = request.args.get("solicitud", type=int)
    acceso_local = sesion.get("solicitudes", [])
    if solicitud_id is not None and solicitud_id not in acceso_local:
        abort(404)
    actual, solicitudes = _solicitudes_editor(acceso_local, solicitud_id)
    if solicitud_id is not None and actual is None:
        abort(404)
    respuesta = make_response(_formulario_publicacion(
        sesion["token"], actual or {}, solicitudes=solicitudes, aviso=request.args.get("guardada") == "1",
    ))
    if renovar:
        return _cookie_editor(respuesta, sesion)
    return respuesta


@bp.post("/marketplace/publicar")
def recibir_publicacion():
    sesion = _sesion_publicacion()
    token = sesion.get("token")
    if request.content_length and request.content_length > 8 * 1024 * 1024:
        return _formulario_publicacion(token, {}, "Las fotos superan el tamaño total permitido."), 413
    if not token or not secrets.compare_digest(token.encode(), _texto(request.form.get("token"), 60).encode()):
        return _formulario_publicacion(None, {}, "Abre de nuevo el formulario para guardar tu publicación."), 400
    solicitud_id = request.form.get("solicitud", type=int)
    editando = solicitud_id is not None
    if editando and solicitud_id not in sesion.get("solicitudes", []):
        abort(404)
    datos = {clave: _texto(request.form.get(clave), limite) for clave, limite in
             (("nombre", 100), ("telefono", 25), ("tipo", 12), ("titulo", 120), ("descripcion", 1000))}
    datos["telefono"] = _telefono(datos["telefono"])
    datos["id"] = solicitud_id
    datos["revision"] = request.form.get("revision", type=int)
    datos["contacto_publico"] = request.form.get("contacto_publico") == "1"
    datos["precio"] = request.form.get("precio", "").strip()
    datos["acepta_contraentrega"] = {"si": True, "no": False}.get(request.form.get("contraentrega"))
    icono = request.form.get("icono_ofertante")
    if icono:
        try:
            _fotos_publicacion([icono], limite_foto=LIMITE_ICONO_OFERTANTE, dimension=DIMENSION_ICONO_OFERTANTE)
        except ValueError:
            return _formulario_publicacion(token, datos, "Vuelve a seleccionar el ícono del ofertante."), 400
    datos["icono_ofertante"] = icono
    if not all(datos[k] for k in ("nombre", "telefono", "tipo", "titulo", "descripcion")) or datos["tipo"] not in ("producto", "servicio"):
        return _formulario_publicacion(token, datos, "Completa los datos y escribe un celular colombiano válido."), 400
    try:
        fotos = _fotos_publicacion(request.form.getlist("fotos"))
    except ValueError as error:
        return _formulario_publicacion(token, datos, str(error)), 400
    datos["fotos"] = fotos
    monto = datos["precio"].replace(",", ".")
    if not re.fullmatch(r"[0-9]{1,8}(\.[0-9]{1,2})?", monto) or Decimal(monto) <= 0:
        return _formulario_publicacion(token, datos, "Ingresa un precio en pesos colombianos mayor a cero."), 400
    precio = Decimal(monto)
    if datos["acepta_contraentrega"] is None:
        return _formulario_publicacion(token, datos, "Indica si aceptas pago contra entrega."), 400
    conn = _conexion_publicaciones()
    try:
        if editando:
            # El enlace conserva la identidad ya comprobada por quien lo entregó.
            fila = conn.execute(
                """UPDATE marketplace_solicitudes
                      SET tipo=%s, titulo=%s, descripcion=%s, fotos=%s::jsonb,
                          precio=%s, acepta_contraentrega=%s,
                          contacto_publico=%s, contacto_aprobado=contacto_aprobado AND %s,
                          icono_ofertante=CASE WHEN %s THEN %s ELSE icono_ofertante END,
                          cambiar_icono_ofertante=CASE WHEN %s THEN %s OR producto_id IS NOT NULL
                                                       ELSE cambiar_icono_ofertante END,
                          estado='recibida', revision=revision+1
                    WHERE id=%s AND revision=%s RETURNING id, nombre, telefono""",
                (datos["tipo"], datos["titulo"], datos["descripcion"], json.dumps(fotos),
                 precio, datos["acepta_contraentrega"], datos["contacto_publico"],
                 datos["contacto_publico"], icono is not None, icono or None, icono is not None, bool(icono),
                 solicitud_id, datos["revision"]),
            ).fetchone()
            if not fila:
                return _formulario_publicacion(token, datos, "La publicación cambió. Ábrela de nuevo antes de guardar."), 409
        else:
            fila = conn.execute(
                """INSERT INTO marketplace_solicitudes
                          (token, nombre, telefono, tipo, titulo, descripcion, fotos, contacto_publico,
                           precio, acepta_contraentrega, icono_ofertante, cambiar_icono_ofertante)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                   ON CONFLICT (token) DO NOTHING RETURNING id, nombre, telefono""",
                (token, datos["nombre"], datos["telefono"], datos["tipo"], datos["titulo"],
                 datos["descripcion"], json.dumps(fotos), datos["contacto_publico"], precio,
                 datos["acepta_contraentrega"], icono or None, bool(icono)),
            ).fetchone()
            if not fila:
                fila = conn.execute(
                    "SELECT id, nombre, telefono FROM marketplace_solicitudes WHERE token=%s", (token,)
                ).fetchone()
        conn.commit()
    except Exception:
        current_app.logger.exception("Error al guardar solicitud de Marketplace")
        conn.rollback()
        return _formulario_publicacion(token, datos, "No pudimos guardar tu solicitud. Intenta otra vez."), 503
    finally:
        conn.close()
    respuesta = redirect(url_for("marketplace.publicar", solicitud=fila["id"], guardada=1), code=303)
    sesion["token"] = secrets.token_urlsafe(32)
    _cookie_editor(respuesta, sesion, fila["id"])
    return _recordar(respuesta, fila["nombre"], fila["telefono"])


VIGENCIA_FORMULARIO_REVISION = 2 * 3600


def _es_host_revision(host):
    return host.split(":", 1)[0].lower().rstrip(".") in ("admin.tuc-tuc.co", "desk.tuc-tuc.co")


def _host_revision():
    if not _es_host_revision(request.host) and not current_app.testing:
        abort(404)


@bp.get("/admin/marketplace")
def revisar_publicaciones():
    _host_revision()
    from .auth import administrador_autenticado

    moderador = administrador_autenticado()
    if moderador is None:
        if not session.get("usuario_id"):
            return redirect(url_for("auth.entrar", destino="revision-marketplace"))
        return render_template("marketplace_revision.html", autenticado=False), 403
    pagina = max(1, min(request.args.get("pagina", 1, type=int), 1000))
    solicitud_id = request.args.get("solicitud", type=int)
    conn = _conexion_publicaciones()
    try:
        if not conn.execute("SELECT 1 FROM usuarios WHERE id=%s AND rol='Administrador'", (moderador,)).fetchone():
            return render_template("marketplace_revision.html", autenticado=False), 403
        solicitudes = conn.execute(
            """SELECT id, titulo, nombre, tipo, estado, jsonb_array_length(fotos) AS n_fotos
                 FROM marketplace_solicitudes
                ORDER BY (estado='recibida') DESC, id DESC LIMIT 31 OFFSET %s""",
            ((pagina - 1) * 30,),
        ).fetchall()
        solicitud = conn.execute(
            """SELECT id, titulo, nombre, telefono, tipo, estado, descripcion, fotos, revision,
                      producto_id, contacto_publico, precio, acepta_contraentrega,
                      icono_ofertante, cambiar_icono_ofertante
                 FROM marketplace_solicitudes WHERE id=%s""",
            (solicitud_id,),
        ).fetchone() if solicitud_id is not None else None
        terceros = (_terceros_de_publicacion(conn, solicitud["telefono"])
                    if solicitud and solicitud["producto_id"] is None else ())
    finally:
        conn.close()
    if solicitud_id is not None and solicitud is None:
        abort(404)

    enlace = None
    oferta = None
    if solicitud:
        codigo = _firma("enlace-edicion").dumps(solicitud["id"])
        enlace = "https://tuc-tuc.co" + url_for("marketplace.publicar", acceso=codigo)
        if solicitud["producto_id"]:
            oferta = "https://tuc-tuc.co" + url_for("marketplace.portada", oferta=solicitud["producto_id"])
    return render_template(
        "marketplace_revision.html", autenticado=True, solicitudes=solicitudes[:30], solicitud=solicitud,
        enlace=enlace, oferta=oferta, terceros=terceros, aviso=request.args.get("aprobada") == "1",
        precio=_precio_visible(solicitud["precio"]) if solicitud else "",
        token=_firma("revision-csrf").dumps(moderador), pagina=pagina, siguiente=len(solicitudes) > 30,
    )


def _terceros_de_publicacion(conn, telefono):
    return conn.execute(
        """SELECT id,nombre,tipo_tercero,
                  NULLIF(btrim(pin_seguridad),'') IS NOT NULL AS tiene_pin
             FROM terceros
            WHERE regexp_replace(COALESCE(telefono,''),'[^0-9]','','g') IN (%s,%s)
              AND COALESCE(tipo_tercero,'') <> 'negocio' AND es_empresa IS NOT TRUE
            ORDER BY tiene_pin DESC, id""",
        (telefono, "57" + telefono),
    ).fetchall()


def _aprobar_publicacion(conn, solicitud, tercero_elegido=None):
    precio = solicitud["precio"]
    acepta = solicitud["acepta_contraentrega"]
    if not precio or acepta is None:
        abort(409, "El autor debe confirmar el precio y el pago contra entrega.")
    metodo_pago = None
    if acepta:
        fila = conn.execute(
            "SELECT id FROM metodos_pago_catalogo WHERE codigo=%s AND activo IS TRUE", (METODO_CONTRAENTREGA,),
        ).fetchone()
        if not fila:
            abort(409, "El método de pago contra entrega no está disponible.")
        metodo_pago = fila["id"]
    telefono = solicitud["telefono"]
    fotos = solicitud["fotos"] or []
    categoria = "Servicios" if solicitud["tipo"] == "servicio" else "Productos"
    producto_id = solicitud["producto_id"]
    datos = (solicitud["titulo"], categoria, solicitud["descripcion"], fotos[0] if fotos else None, precio,
             solicitud["tipo"])
    if producto_id is None:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("comprador:" + telefono,))
        coincidencias = _terceros_de_publicacion(conn, telefono)
        if tercero_elegido is not None:
            tercero = next((t for t in coincidencias if t["id"] == tercero_elegido), None)
            if tercero is None:
                abort(409, "El usuario seleccionado ya no coincide con el celular de la solicitud.")
        elif len(coincidencias) > 1:
            abort(409, "Elige el usuario correcto entre los que comparten este celular.")
        else:
            tercero = coincidencias[0] if coincidencias else None
        if not tercero:
            tercero = conn.execute(
                """INSERT INTO terceros (nombre, telefono, tipo_tercero, fecha_creacion)
                   VALUES (%s,%s,'persona',NOW()) RETURNING id""",
                (solicitud["nombre"], telefono),
            ).fetchone()
        negocio_id = tercero["id"]
        producto_id = conn.execute(
            """INSERT INTO productos (negocio_id,nombre,categoria,descripcion,imagen,precio,tipo_oferta,disponible)
               VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id""",
            (negocio_id, *datos),
        ).fetchone()["id"]
    else:
        negocio_id = conn.execute(
            """UPDATE productos SET nombre=%s,categoria=%s,descripcion=%s,imagen=%s,precio=%s,tipo_oferta=%s
                WHERE id=%s RETURNING negocio_id""",
            (*datos, producto_id),
        ).fetchone()["negocio_id"]
        conn.execute("DELETE FROM producto_imagenes WHERE producto_id=%s", (producto_id,))
    if solicitud.get("cambiar_icono_ofertante"):
        conn.execute("UPDATE terceros SET icono_marketplace=%s WHERE id=%s",
                     (solicitud["icono_ofertante"], negocio_id))
    for orden, foto in enumerate(fotos[1:], 1):
        conn.execute("INSERT INTO producto_imagenes (producto_id,imagen,orden) VALUES (%s,%s,%s)",
                     (producto_id, foto, orden))
    conn.execute(
        """UPDATE marketplace_solicitudes
              SET producto_id=%s, estado='aprobada', revision=revision+1, contacto_aprobado=contacto_publico,
                  metodo_pago_aprobado_id=%s, icono_ofertante=NULL, cambiar_icono_ofertante=FALSE
            WHERE id=%s""",
        (producto_id, metodo_pago, solicitud["id"]),
    )


@bp.post("/admin/marketplace/aprobar")
def aprobar_publicacion():
    _host_revision()
    from .auth import administrador_autenticado

    moderador = administrador_autenticado()
    if moderador is None:
        abort(403)
    try:
        validez = _firma("revision-csrf").loads(request.form.get("token", ""), max_age=VIGENCIA_FORMULARIO_REVISION)
    except BadData:
        abort(403)
    if validez != moderador:
        abort(403)
    solicitud_id = request.form.get("solicitud", type=int)
    revision = request.form.get("revision", type=int)
    if not solicitud_id or not revision:
        abort(400)
    conn = _conexion_publicaciones()
    try:
        if not conn.execute("SELECT 1 FROM usuarios WHERE id=%s AND rol='Administrador'", (moderador,)).fetchone():
            abort(403)
        solicitud = conn.execute(
            """SELECT id,nombre,telefono,titulo,tipo,descripcion,fotos,estado,revision,producto_id,
                      precio,acepta_contraentrega,icono_ofertante,cambiar_icono_ofertante
                 FROM marketplace_solicitudes WHERE id=%s FOR UPDATE""",
            (solicitud_id,),
        ).fetchone()
        if not solicitud:
            abort(404)
        if solicitud["estado"] != "aprobada":
            if solicitud["revision"] != revision:
                abort(409, "La solicitud cambió. Vuelve a abrirla para revisar la versión más reciente.")
            _aprobar_publicacion(conn, solicitud, request.form.get("tercero", type=int))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return redirect(url_for("marketplace.revisar_publicaciones", solicitud=solicitud_id, aprobada=1), code=303)
