import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from flask import Blueprint, Flask, jsonify, request, session

from app.blueprints import auth, marketplace


class Registro:
    def __init__(self, tercero=None):
        self.tercero = tercero
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        return self

    def fetchone(self):
        if "INSERT INTO marketplace_solicitudes" in self.sql[-1][0]:
            return {"id": 27, "nombre": "Diana", "telefono": "3151112222"}
        if "SELECT negocio_id FROM productos" in self.sql[-1][0]:
            return {"negocio_id": self.tercero["id"]}
        return {"id": 51} if "INSERT INTO terceros" in self.sql[-1][0] else self.tercero

    def fetchall(self):
        return [self.tercero] if self.tercero else []

    def commit(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class MarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates")
        self.app.secret_key = "llave-de-pruebas"
        self.app.register_blueprint(marketplace.bp)
        self.app.register_blueprint(auth.bp)
        pagos = Blueprint("negocios", __name__)

        @pagos.get("/marketplace/pagar/<int:pedido_id>", endpoint="pagar_marketplace")
        def pagar(pedido_id):
            return jsonify(ids=marketplace.ids_pago(pedido_id, request.args.get("tipo")))

        self.app.register_blueprint(pagos)
        self.client = self.app.test_client()

    def test_registra_invitado_y_recuerda_contacto_sin_crear_sesion_administrativa(self):
        conn = Registro({"id": 19})
        with patch.object(marketplace, "get_db_connection", return_value=conn):
            respuesta = self.client.post("/api/marketplace/comprador", json={
                "nombre": "Diana", "telefono": "+57 315 111 2222", "direccion": "Dirección temporal"
            })
        self.assertEqual(respuesta.json, {"ok": True, "cliente_id": 19})
        self.assertIn("HttpOnly", respuesta.headers["Set-Cookie"])
        self.assertIn("Secure", respuesta.headers["Set-Cookie"])
        self.assertNotIn("Domain=", respuesta.headers["Set-Cookie"])
        self.assertFalse(any("UPDATE terceros" in sql for sql, _ in conn.sql))
        with self.client.session_transaction() as sesion:
            self.assertNotIn("usuario_id", sesion)
            self.assertNotIn("rol", sesion)
        with self.app.test_request_context(headers={"Cookie": respuesta.headers["Set-Cookie"].split(";")[0]}):
            self.assertEqual(marketplace.datos_comprador(), {"nombre": "Diana", "telefono": "3151112222"})
            pedido = marketplace.datos_pedido({
                "tipo_entrega": "recoger", "cliente_id": 1000,
                "items": [{"producto_id": 7, "cantidad": 2, "precio_unitario": 12}],
                "id_cajero": 1000, "ajustes": [1],
            })
            self.assertEqual(pedido["cliente_id"], 19)
            self.assertEqual(pedido["items"], [{"producto_id": 7, "cantidad": 2}])
            self.assertNotIn("id_cajero", pedido)

    def test_resuelve_un_tercero_nuevo_y_rechaza_celular_invalido(self):
        conn = Registro()
        with patch.object(marketplace, "get_db_connection", return_value=conn):
            self.assertEqual(self.client.post("/api/marketplace/comprador", json={
                "nombre": "Diana", "telefono": "3152223333",
            }).json["cliente_id"], 51)
            self.assertEqual(self.client.post("/api/marketplace/comprador", json={
                "nombre": "Diana", "telefono": "2",
            }).status_code, 400)

    def test_pago_limitado_al_grupo_de_pedidos_que_recibio_el_navegador(self):
        with self.app.test_request_context():
            respuesta = marketplace.respuesta_pedido("restaurante", 10, {"ok": True}, [8, 10])
        perfil = respuesta.headers["Set-Cookie"].split(";")[0]
        with self.app.test_request_context(headers={"Cookie": perfil}):
            self.assertEqual(marketplace.ids_pago(10, "restaurante"), [8, 10])
            self.assertFalse(marketplace.ids_pago(10, "tienda"))
            self.assertFalse(marketplace.ids_pago(11, "restaurante"))

    def test_publicacion_rechaza_la_clave_de_desarrollo_y_usa_la_del_marketplace(self):
        self.app.secret_key = "dev-secret-key"
        with patch.dict(os.environ, {"MARKETPLACE_SIGNING_KEY": ""}):
            self.assertEqual(self.client.get("/marketplace/publicar").status_code, 503)
        with patch.dict(os.environ, {"MARKETPLACE_SIGNING_KEY": "clave-de-prueba-independiente"}):
            response = self.client.get("/marketplace/publicar")
            self.assertEqual(response.status_code, 200)
            self.assertIn("__Host-tuctuc_publicar=", response.headers["Set-Cookie"])
            self.assertEqual(self.client.post("/marketplace/publicar", data={"token": "ajeno"}).status_code, 400)

    def test_sugerencias_comparten_busqueda_y_conservan_el_enlace_del_plato(self):
        restaurantes = Blueprint("restaurantes", __name__)

        @restaurantes.get("/r/<slug>")
        def restaurante_publico(slug):
            return slug

        self.app.register_blueprint(restaurantes)
        plato = dict(tipo="platos", id=81, nombre="Sándwich", categoria="Sándwiches",
                     negocio="Pitt", slug="pitt", precio=Decimal("18000"), imagen=None)
        categoria = dict(tipo="categorias", id=0, nombre="Sándwiches", categoria=None,
                         negocio=None, slug=None, precio=None, imagen=None)
        with patch.object(marketplace, "get_db_connection", return_value=Registro()), \
             patch.object(marketplace, "_buscar", return_value=[plato, categoria]) as buscar:
            corto = self.client.get("/marketplace", query_string={"sugerencias": 1, "q": "s"})
            self.assertEqual(corto.json, {"sugerencias": []})
            buscar.assert_not_called()
            resultado = self.client.get("/marketplace", query_string={"sugerencias": 1, "q": "sándwich"})
            self.assertEqual(resultado.status_code, 200)
            self.assertIn("plato=81", resultado.json["sugerencias"][0]["enlace"])
            self.assertIn("rubro=", resultado.json["sugerencias"][1]["enlace"])
            self.assertEqual([r["tipo"] for r in resultado.json["sugerencias"]], ["platos", "categorias"])
        self.assertEqual(marketplace._normalizar_busqueda(" SÁNDWICH  de Atún "), "sandwich de atun")

    def test_servicios_tiene_filtro_propio_para_la_lista_y_las_sugerencias(self):
        servicio = dict(tipo="publicaciones", id=367, nombre="Servicio técnico",
                        categoria="Servicios", negocio="Publicación particular",
                        slug=None, precio=Decimal("50000"), imagen=None, ambito="servicios")
        conn = Registro(servicio)
        with patch.object(marketplace, "_conexion_publicaciones", return_value=conn):
            portada = self.client.get("/marketplace", query_string={"categoria": "servicios"})
            self.assertEqual(portada.status_code, 200)
            self.assertIn('aria-current="true">Servicios', portada.get_data(as_text=True))
            self.assertEqual(conn.sql[-1][1][:2], ("servicios", "servicios"))
            sugerencias = self.client.get("/marketplace", query_string={
                "categoria": "servicios", "sugerencias": 1, "q": "técnico",
            })
            self.assertEqual(sugerencias.status_code, 200)
            self.assertEqual(conn.sql[-1][1]["ambito"], "servicios")
            self.assertIn("oferta=367", sugerencias.json["sugerencias"][0]["enlace"])
            self.assertTrue(sugerencias.json["sugerencias"][0]["es_servicio"])

    def test_serve_foto_publica_con_mime_y_cache(self):
        conn = Registro({"imagen": "data:image/jpeg;base64,/9j/2Q=="})
        ruta = "/static/marketplace/fotos/productos/14"
        with patch.object(marketplace, "get_db_connection", return_value=conn):
            foto = self.client.get(ruta)
            self.assertEqual(foto.status_code, 200)
            self.assertEqual(foto.mimetype, "image/jpeg")
            self.assertEqual(foto.data, bytes([255, 216, 255, 217]))
            self.assertEqual(foto.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(self.client.get(
                ruta, headers={"If-None-Match": foto.headers["ETag"]}
            ).status_code, 304)
            self.assertEqual(self.client.get("/static/marketplace/fotos/interna/14").status_code, 404)
        for invalida in (None, "data:image/jpeg;base64,@@@", "data:image/svg+xml;base64,AAAA"):
            with patch.object(marketplace, "get_db_connection", return_value=Registro({"imagen": invalida})):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_publicacion_guarda_mas_de_cuatro_fotos_en_orden(self):
        from base64 import b64encode
        from io import BytesIO
        from PIL import Image
        from werkzeug.datastructures import MultiDict
        import json
        import re

        fotos = []
        for n in range(6):
            buffer = BytesIO()
            Image.new("RGB", (20, 30), (n * 30, 120, 40)).save(buffer, "JPEG")
            fotos.append("data:image/jpeg;base64," + b64encode(buffer.getvalue()).decode())
        pagina = self.client.get("/marketplace/publicar")
        token = re.search(r'name="token" value="([^"]+)"', pagina.get_data(as_text=True)).group(1)
        form = MultiDict([("token", token), ("nombre", "Diana"), ("telefono", "3151112222"),
                          ("tipo", "producto"), ("titulo", "Oferta de prueba"),
                          ("descripcion", "Descripción de prueba"), ("precio", "12500,50"),
                          ("contraentrega", "no"), ("icono_ofertante", fotos[0]), ("comision_pct", "20,50"),
                          *[("fotos", foto) for foto in fotos]])
        conn = Registro()
        with patch.object(marketplace, "get_db_connection", return_value=conn):
            respuesta = self.client.post("/marketplace/publicar", data=form, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 303)
        guardado = next(params for sql, params in conn.sql if "INSERT INTO marketplace_solicitudes" in sql)
        self.assertEqual(json.loads(guardado[6]), fotos)
        self.assertEqual(guardado[-8:], (Decimal("12500.50"), False, fotos[0], True, Decimal("20.50"), "Diana", None, None))
        self.assertEqual(marketplace._fotos_publicacion([]), [])
        with self.assertRaises(ValueError):
            marketplace._fotos_publicacion(["data:image/jpeg;base64,AAAA"])

    def test_publicar_pide_precio_positivo_y_respuesta_explicita_de_contraentrega(self):
        import re

        pagina = self.client.get("/marketplace/publicar")
        html = pagina.get_data(as_text=True)
        self.assertIn('name="precio"', html)
        self.assertIn('name="contraentrega"', html)
        self.assertIn('name="comision_pct" type="number" min="10"', html)
        self.assertIn('id="comision-neto"', html)
        self.assertIn('name="icono_ofertante"', html)
        token = re.search(r'name="token" value="([^"]+)"', html).group(1)
        form = dict(token=token, nombre="Diana", telefono="3151112222",
                    tipo="producto", titulo="Oferta", descripcion="Detalles")
        with patch.object(marketplace, "_conexion_publicaciones") as conexion:
            for precio, contraentrega in (("", "si"), ("0", "si"), ("100000000", "si"),
                                           ("9.001", "si"), ("10000", "")):
                respuesta = self.client.post("/marketplace/publicar",
                                             data=dict(form, precio=precio, contraentrega=contraentrega))
                self.assertEqual(respuesta.status_code, 400)
            respuesta = self.client.post("/marketplace/publicar", data=dict(
                form, precio="10000", contraentrega="si", comision_pct="9.99"))
            self.assertEqual(respuesta.status_code, 400)
            self.assertIn("La comisión mínima es del 10%", respuesta.get_data(as_text=True))
            conexion.assert_not_called()

    def test_ficha_muestra_precio_canonico_y_metodo_confirmado(self):
        class Detalle(Registro):
            def fetchall(self):
                return []

        fila = dict(id=95, nombre="Oferta", categoria="Productos", descripcion="Detalles",
                    imagen=None, contacto=None, precio=Decimal("12500.50"),
                    metodo_pago="Contraentrega en efectivo", nombre_ofertante="Diana",
                    tiene_icono_ofertante=True)
        with patch.object(marketplace, "_conexion_publicaciones", return_value=Detalle(fila)):
            ficha = self.client.get("/marketplace?oferta=95")
        self.assertEqual(ficha.status_code, 200)
        self.assertIn("$12.500,5 COP", ficha.get_data(as_text=True))
        html = ficha.get_data(as_text=True)
        self.assertIn("Contraentrega en efectivo", html)
        self.assertIn("Ofrecido por <strong>Diana</strong>", html)
        self.assertIn("/static/marketplace/fotos/ofertantes/95", html)
        self.assertNotIn("wa.me", html)

    def test_foto_del_ofertante_usa_solo_el_icono_aprobado(self):
        ruta = "/static/marketplace/fotos/ofertantes/95"
        conn = Registro({"imagen": None})
        with patch.object(marketplace, "_conexion_publicaciones", return_value=conn):
            self.assertEqual(self.client.get(ruta).status_code, 404)
            self.assertIn("ofertante.icono_marketplace AS imagen", conn.sql[-1][0])
            self.assertIn("ofertante.id=p.negocio_id", conn.sql[-1][0])
            conn.tercero["imagen"] = "data:image/jpeg;base64,/9j/2Q=="
            icono = self.client.get(ruta)
        self.assertEqual(icono.mimetype, "image/jpeg")
        self.assertIn("must-revalidate", icono.headers["Cache-Control"])

    def test_enlace_recupera_solicitud_anterior_y_rechaza_id_ajeno(self):
        with self.app.test_request_context():
            acceso = marketplace._firma("enlace-edicion").dumps(27)
        self.assertEqual(self.client.get("/marketplace/publicar?solicitud=27").status_code, 404)
        conn = Registro({"id": 27})
        with patch.object(marketplace, "_conexion_publicaciones", return_value=conn):
            respuesta = self.client.get("/marketplace/publicar", query_string={"acceso": acceso})
        self.assertEqual(respuesta.status_code, 303)
        self.assertIn("solicitud=27", respuesta.location)
        self.assertNotIn(acceso, respuesta.location)
        self.assertEqual(self.client.get("/marketplace/publicar?solicitud=28").status_code, 404)
        actual = dict(id=27, nombre="Diana", telefono="3151112222", tipo="servicio", titulo="Oferta recuperada",
                      descripcion="Descripción", fotos=[], estado="recibida", revision=1, contacto_publico=False,
                      icono_actual="data:image/jpeg;base64,/9j/2Q==")
        with patch.object(marketplace, "_solicitudes_editor", return_value=(actual, [actual])):
            html = self.client.get(respuesta.location).get_data(as_text=True)
        self.assertIn("Oferta recuperada", html)
        self.assertIn("Guardar cambios", html)
        self.assertIn('id="market-fotos"', html)
        self.assertIn('data-icono-actual="data:image/jpeg;base64,/9j/2Q=="', html)
        self.assertIn('name="icono_ofertante" value="" disabled', html)

    def test_desk_reusa_su_inicio_de_sesion_para_revision(self):
        class RegistroAdmin(Registro):
            def fetchall(self):
                return []

        host = "https://desk.tuc-tuc.co"
        acceso = "/entrar?destino=revision-marketplace"
        anonimo = self.client.get("/admin/marketplace", base_url=host)
        self.assertEqual(anonimo.location, acceso)
        self.assertIn(acceso, self.client.get(acceso, base_url=host).get_data(as_text=True))
        conn = RegistroAdmin(dict(id=9, rol="Administrador", nombre="Admin"))
        with patch.object(auth, "get_db_connection", return_value=conn):
            login = self.client.post(acceso, base_url=host,
                                     data={"usuario": "admin-prueba", "password": "clave-prueba"})
        self.assertEqual(login.location, "/admin/marketplace")
        cookies = login.headers.getlist("Set-Cookie")
        self.assertEqual(len(cookies), 1)
        self.assertTrue(cookies[0].startswith("session="))
        with patch.object(marketplace, "_conexion_publicaciones", return_value=conn):
            revision = self.client.get(login.location, base_url=host)
        self.assertIn("Aún no hay solicitudes", revision.get_data(as_text=True))
        with patch.object(marketplace, "_conexion_publicaciones", return_value=Registro()):
            self.assertEqual(self.client.get(login.location, base_url=host).status_code, 403)
        salida = self.client.get("/logout", base_url=host)
        self.assertEqual(salida.location, "/entrar")
        self.assertEqual(self.client.get(login.location, base_url=host).location, acceso)

        with patch.object(auth, "get_db_connection", return_value=conn):
            login_normal = self.client.post("/entrar", base_url=host,
                                            data={"usuario": "admin-prueba", "password": "clave-prueba"})
        self.assertEqual(login_normal.location, "/")
        with patch.object(marketplace, "_conexion_publicaciones", return_value=conn):
            self.assertEqual(self.client.get("/admin/marketplace", base_url=host).status_code, 200)

    def test_revision_rechaza_dispositivo_reconocido_y_sesion_admin_heredada(self):
        host = "https://desk.tuc-tuc.co"
        for rol in ("Vendedor", "Administrador"):
            with self.client.session_transaction(base_url=host) as acceso:
                acceso["rol"] = rol
                acceso["usuario_id"] = 9
            portada = self.client.get("/admin/marketplace", base_url=host)
            self.assertEqual(portada.status_code, 403)
            self.assertIn("requiere una cuenta administradora", portada.get_data(as_text=True))
            self.assertEqual(self.client.post("/admin/marketplace/aprobar", base_url=host,
                                              data={"solicitud": 27}).status_code, 403)
        self.assertEqual(self.client.get("/admin/marketplace", base_url="https://tuc-tuc.co").status_code, 404)

    def test_revision_no_usa_la_clave_de_desarrollo(self):
        self.app.secret_key = "dev-secret-key"
        host = "https://desk.tuc-tuc.co"
        with self.client.session_transaction(base_url=host) as acceso:
            acceso.update(rol="Administrador", usuario_id=9, admin_autenticado_id=9)
        self.assertEqual(self.client.get("/admin/marketplace", base_url=host).status_code, 403)

    def test_omni_encuentra_revision_solo_para_admin_autenticado(self):
        from app.buscador_motor import _filas_desde_semilla, buscar_omni

        filas = _filas_desde_semilla()
        for texto in ("revisar", "aprobar"):
            for acceso in (False, True):
                rutas = buscar_omni(texto, filas=filas, incluir_manuales=False,
                                    revision_marketplace=acceso)["rutas"]
                self.assertEqual(any(r["url"] == "/admin/marketplace" for r in rutas), acceso)

    def _aprobar_en_negocio(self, conn, solicitud, titular=None):
        destino = {"id": conn.tercero["id"], "nombre": "Marca", "plan_marketplace": False, "activo": True}
        with patch.object(marketplace, "_negocio_para_publicar", return_value=destino) as elegir:
            marketplace._aprobar_publicacion(conn, solicitud, titular)
        return elegir.call_args.args[1]

    def test_aprobacion_reusa_producto_y_su_galeria_en_la_revision(self):
        conn = Registro({"id": 95})
        solicitud = dict(id=27, nombre="Diana", telefono="3151112222", tipo="servicio",
                         titulo="Oferta", descripcion="Detalles", fotos=["portada", "galeria"],
                         estado="recibida", revision=2, producto_id=None,
                         precio=Decimal("12500.50"), acepta_contraentrega=True)
        self._aprobar_en_negocio(conn, solicitud)
        alta = next(params for sql, params in conn.sql if "INSERT INTO productos" in sql)
        self.assertEqual(alta, (95, "Oferta", "Servicios", "Detalles", "portada", Decimal("12500.50"), "servicio"))
        self.assertTrue(any(params == ("contraentrega",) for sql, params in conn.sql
                            if "FROM metodos_pago_catalogo" in sql))
        aprobacion_sql, params = next((sql, params) for sql, params in conn.sql
                                      if "metodo_pago_aprobado_id" in sql)
        self.assertEqual(params, (95, 95, 95, 95, 27))
        self.assertIn("cambiar_icono_ofertante=FALSE", aprobacion_sql)
        self.assertFalse(any("UPDATE terceros" in sql for sql, _ in conn.sql))
        self.assertTrue(any(params == (95, "galeria", 1) for sql, params in conn.sql
                            if "INSERT INTO producto_imagenes" in sql))
        conn.sql.clear()
        solicitud.update(producto_id=95, precio=Decimal("13900.00"), acepta_contraentrega=False)
        self._aprobar_en_negocio(conn, solicitud)
        self.assertFalse(any("INSERT INTO productos" in sql for sql, _ in conn.sql))
        self.assertTrue(any(params[-4:] == (Decimal("13900.00"), "servicio", 95, 95) for sql, params in conn.sql
                            if "UPDATE productos" in sql))
        self.assertTrue(any(params == (95, 95, 95, None, 27) for sql, params in conn.sql
                            if "metodo_pago_aprobado_id" in sql))

    def test_icono_del_tercero_se_preserva_al_publicar_otra_oferta(self):
        conn = Registro({"id": 95})
        solicitud = dict(id=27, nombre="Diana", telefono="3151112222", tipo="producto",
                         titulo="Oferta", descripcion="Detalles", fotos=[], producto_id=None,
                         precio=Decimal("15000"), acepta_contraentrega=False,
                         cambiar_icono_ofertante=True, icono_ofertante="icono")
        self._aprobar_en_negocio(conn, solicitud)
        self.assertIn(("UPDATE terceros SET icono_marketplace=%s WHERE id=%s", ("icono", 95)), conn.sql)

        conn.sql.clear()
        otra = dict(solicitud, id=28, cambiar_icono_ofertante=False, icono_ofertante=None)
        self._aprobar_en_negocio(conn, otra)
        self.assertFalse(any("UPDATE terceros" in sql for sql, _ in conn.sql))

        conn.sql.clear()
        self._aprobar_en_negocio(conn, dict(otra, producto_id=96, cambiar_icono_ofertante=True))
        self.assertIn(("UPDATE terceros SET icono_marketplace=%s WHERE id=%s", (None, 95)), conn.sql)

    def test_aprobacion_exige_seleccion_si_hay_dos_terceros(self):
        from werkzeug.exceptions import Conflict

        conn = Registro({"id": 95})
        solicitud = dict(id=27, nombre="Diana", telefono="3151112222", tipo="producto",
                         titulo="Oferta", descripcion="Detalles", fotos=[], producto_id=None,
                         precio=Decimal("15000"), acepta_contraentrega=False)
        with patch.object(marketplace, "_terceros_de_publicacion", return_value=[{"id": 95}, {"id": 122}]):
            with self.assertRaises(Conflict):
                marketplace._aprobar_publicacion(conn, solicitud)
            self.assertFalse(any("INSERT INTO productos" in sql for sql, _ in conn.sql))
            self.assertEqual(self._aprobar_en_negocio(conn, solicitud, 122), 122)
        alta = next(params for sql, params in conn.sql if "INSERT INTO productos" in sql)
        self.assertEqual(alta[0], 95)

    def test_campos_publicos_y_rechazo_de_url_no_apta(self):
        tienda = Blueprint("tiendas", __name__)

        @tienda.get("/t/<slug>")
        def tienda_publica(slug):
            return slug

        self.app.register_blueprint(tienda)
        with self.app.test_request_context():
            ficha = marketplace._oferta({
                "tipo": "productos", "id": 14, "nombre": "Café", "categoria": "Mercado",
                "negocio": "Tienda", "slug": "tienda", "precio": Decimal("20000.00"),
                "imagen": "javascript:alert(1)", "costo": 3, "admin_id": 1,
            })
        self.assertEqual(ficha["precio"], "$20.000")
        self.assertFalse(ficha["imagen"])
        self.assertIn("producto=14", ficha["enlace"])
        self.assertNotIn("admin_id", ficha)
        self.assertNotIn("costo", ficha)


class OfertasFalsas:
    def __init__(self, filas):
        self.filas = filas

    def execute(self, *args, **kwargs):
        return self

    def fetchall(self):
        return self.filas

    def close(self):
        pass


class SesionConn(Registro):
    def __init__(self, tercero=None, negocios=()):
        super().__init__(tercero)
        self.negocios = list(negocios)

    def fetchall(self):
        if self.sql and "UNION ALL" in self.sql[-1][0]:
            return self.negocios
        return super().fetchall()


class CompraMarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates")
        self.app.secret_key = "llave-de-pruebas"
        self.app.register_blueprint(marketplace.bp)
        tiendas = Blueprint("tiendas", __name__)

        @tiendas.get("/t/<slug>")
        def tienda_publica(slug):
            return slug

        restaurantes = Blueprint("restaurantes", __name__)

        @restaurantes.get("/r/<slug>")
        def restaurante_publico(slug):
            return slug

        self.app.register_blueprint(tiendas)
        self.app.register_blueprint(restaurantes)
        self.client = self.app.test_client()

    def _fila(self, tipo="productos", **kw):
        base = {"tipo": tipo, "id": 368, "nombre": "Delantal", "categoria": "Ropa",
                "negocio": "Andrea", "slug": "andrea-rendon",
                "precio": Decimal("10000"), "imagen": None}
        base.update(kw)
        return base

    def test_enlace_absoluto_al_subdominio_en_prod(self):
        with self.app.test_request_context(base_url="https://tuc-tuc.co/"):
            prod = marketplace._oferta(self._fila("productos"))
            plato = marketplace._oferta(self._fila("platos", id=81, slug="pitt"))
            tienda = marketplace._oferta(self._fila("tiendas", id=7, precio=None))
            rest = marketplace._oferta(self._fila("restaurantes", id=3, slug="pitt", precio=None))
        self.assertEqual(prod["enlace"], "https://andrea-rendon.tuc-tuc.co/?producto=368&origen=marketplace")
        self.assertEqual(plato["enlace"], "https://pitt.tuc-tuc.co/?plato=81&origen=marketplace")
        self.assertEqual(tienda["enlace"], "https://andrea-rendon.tuc-tuc.co/?origen=marketplace")
        self.assertEqual(rest["enlace"], "https://pitt.tuc-tuc.co/?origen=marketplace")
        for ficha in (prod, plato, tienda, rest):
            self.assertTrue(ficha["externa"])
        self.assertTrue(prod["comprable"])
        self.assertTrue(plato["comprable"])
        self.assertFalse(tienda["comprable"])
        self.assertFalse(rest["comprable"])
        self.assertEqual(prod["precio_num"], 10000.0)
        self.assertIsNone(tienda["precio_num"])
        self.assertEqual(prod["negocio_slug"], "andrea-rendon")
        self.assertEqual(prod["oferta_id"], 368)

    def test_enlace_relativo_fuera_de_prod(self):
        with self.app.test_request_context(base_url="http://localhost/"):
            prod = marketplace._oferta(self._fila("productos"))
            plato = marketplace._oferta(self._fila("platos", id=81, slug="pitt"))
        self.assertTrue(prod["enlace"].startswith("/t/andrea-rendon?"))
        self.assertIn("producto=368", prod["enlace"])
        self.assertTrue(plato["enlace"].startswith("/r/pitt?"))
        self.assertIn("plato=81", plato["enlace"])
        self.assertTrue(prod["externa"])

    def test_servicio_compra_igual_y_particular_solo_visita(self):
        with self.app.test_request_context(base_url="https://tuc-tuc.co/"):
            serv = marketplace._oferta(self._fila("productos", ambito="servicios"))
            part = marketplace._oferta(self._fila("publicaciones", id=95, slug=None,
                                                  negocio="Particular"))
            cat = marketplace._oferta(self._fila("categorias", id=0, nombre="Ropa",
                                                 slug=None, precio=None))
        self.assertTrue(serv["es_servicio"])
        self.assertTrue(serv["comprable"])
        self.assertFalse(part["comprable"])
        self.assertFalse(part["externa"])
        self.assertIn("oferta=95", part["enlace"])
        self.assertFalse(cat["externa"])
        self.assertFalse(cat["comprable"])

    def test_portada_con_comprar_visitar_y_carrito(self):
        filas = [self._fila("productos"),
                 self._fila("publicaciones", id=95, slug=None, negocio="Particular")]
        with patch.object(marketplace, "_conexion_publicaciones", return_value=OfertasFalsas(filas)):
            pagina = self.client.get("/marketplace", base_url="https://tuc-tuc.co/")
        self.assertEqual(pagina.status_code, 200)
        html = pagina.get_data(as_text=True)
        self.assertIn("https://andrea-rendon.tuc-tuc.co/?producto=368", html)
        self.assertIn('target="_blank"', html)
        self.assertIn("mp-add", html)
        self.assertIn('data-precio="10000.0"', html)
        self.assertIn(">Comprar<", html)
        self.assertIn("Visitar tienda", html)
        self.assertIn("mp-cart-open", html)
        self.assertIn("mp-cart-confirm", html)
        self.assertIn("/api/marketplace/comprador", html)
        self.assertIn("/api/marketplace/tienda/", html)
        self.assertRegex(html, r'<a href="[^"]*oferta=95">')
        self.assertNotRegex(html, r"(?s)<a\b[^>]*>(?:(?!</a>).)*<a\b")

    def test_tarjeta_deja_ver_boton_comprar(self):
        filas = [self._fila("productos")]
        with patch.object(marketplace, "_conexion_publicaciones", return_value=OfertasFalsas(filas)):
            pagina = self.client.get("/marketplace", base_url="https://tuc-tuc.co/")
        html = pagina.get_data(as_text=True)
        self.assertIn(".card>a{height:auto}", html)

    def test_usuario_sesion_reconoce_todos_los_origenes(self):
        from flask import session as fsession
        fila = {"id": 61, "nombre": "David", "telefono": "3001112233", "direccion": "Calle 5"}
        conn = SesionConn(fila)
        casos = [
            {"chat_tercero_id": 61, "rol": "Administrador", "usuario_id": 4},
            {"usuario_id": 61, "rol": "Tienda"},
            {"usuario_id": 61, "rol": "Restaurante"},
            {"usuario_id": 61, "rol": "Cliente"},
        ]
        for ses in casos:
            with self.app.test_request_context():
                for k, v in ses.items():
                    fsession[k] = v
                with patch.object(marketplace, "get_db_connection", return_value=conn):
                    u = marketplace.usuario_sesion()
            self.assertEqual(u["nombre"], "David")
            self.assertEqual(u["telefono"], "3001112233")
            self.assertEqual(u["direccion"], "Calle 5")
            self.assertEqual(u["negocios"], [])

    def test_usuario_sesion_ignora_admin_sin_tercero_e_invitado(self):
        from flask import session as fsession
        conn = Registro(None)
        with self.app.test_request_context():
            fsession["usuario_id"] = 4
            fsession["rol"] = "Administrador"
            with patch.object(marketplace, "get_db_connection", return_value=conn):
                self.assertIsNone(marketplace.usuario_sesion())
        with self.app.test_request_context():
            with patch.object(marketplace, "get_db_connection", return_value=conn):
                self.assertIsNone(marketplace.usuario_sesion())

    def test_portada_saluda_y_prellena(self):
        filas = [self._fila("productos")]
        fila_u = {"id": 61, "nombre": "David", "telefono": "3001112233", "direccion": "Calle 5"}
        with patch.object(marketplace, "_conexion_publicaciones", return_value=OfertasFalsas(filas)):
            with patch.object(marketplace, "get_db_connection", return_value=SesionConn(fila_u)):
                with self.client.session_transaction(base_url="https://tuc-tuc.co/") as s:
                    s["chat_tercero_id"] = 61
                pagina = self.client.get("/marketplace", base_url="https://tuc-tuc.co/")
        html = pagina.get_data(as_text=True)
        self.assertIn("Hola, David", html)
        self.assertIn('"telefono": "3001112233"', html)
        self.assertNotIn('href="/entrar"', html)
        self.assertIn("@media(max-width:1024px){.head nav a{display:none}}", html)
        self.assertIn(".head-inner{flex-wrap:wrap", html)

    def test_portada_invitada_muestra_entrar(self):
        filas = [self._fila("productos")]
        with patch.object(marketplace, "_conexion_publicaciones", return_value=OfertasFalsas(filas)):
            pagina = self.client.get("/marketplace", base_url="https://tuc-tuc.co/")
        html = pagina.get_data(as_text=True)
        self.assertIn('href="/entrar"', html)
        self.assertNotIn('<span class="mp-hello">', html)
        self.assertIn("const MP_USUARIO = null;", html)
        self.assertIn("mp-pinrow", html)
        self.assertIn("/api/marketplace/identificar", html)

    def test_usuario_sesion_trae_negocios_donde_vende(self):
        from flask import session as fsession
        fila = {"id": 61, "nombre": "David", "telefono": "3001112233", "direccion": None}
        negs = [{"tipo": "tienda", "nombre": "Pitt", "slug": "pitt"},
                {"tipo": "restaurante", "nombre": "Bistro", "slug": "bistro"}]
        with self.app.test_request_context():
            fsession["usuario_id"] = 61
            fsession["rol"] = "Tienda"
            with patch.object(marketplace, "get_db_connection",
                              return_value=SesionConn(fila, negs)):
                u = marketplace.usuario_sesion()
        self.assertEqual([n["slug"] for n in u["negocios"]], ["pitt", "bistro"])

    def test_portada_muestra_donde_vende(self):
        filas = [self._fila("productos")]
        fila_u = {"id": 61, "nombre": "David", "telefono": "3001112233", "direccion": None}
        negs = [{"tipo": "tienda", "nombre": "Pitt", "slug": "pitt"}]
        with patch.object(marketplace, "_conexion_publicaciones", return_value=OfertasFalsas(filas)):
            with patch.object(marketplace, "get_db_connection",
                              return_value=SesionConn(fila_u, negs)):
                with self.client.session_transaction(base_url="https://tuc-tuc.co/") as s:
                    s["usuario_id"] = 61
                    s["rol"] = "Tienda"
                pagina = self.client.get("/marketplace", base_url="https://tuc-tuc.co/")
        html = pagina.get_data(as_text=True)
        self.assertIn("Hola, David", html)
        self.assertIn("Vendes:", html)
        self.assertIn("https://pitt.tuc-tuc.co/", html)

    def test_identificar_con_pin(self):
        from werkzeug.security import generate_password_hash
        bueno = generate_password_hash("1234")
        with patch.object(marketplace, "get_db_connection",
                          return_value=SesionConn({"id": 61, "nombre": "D",
                                                   "pin_seguridad": bueno})):
            r = self.client.post("/api/marketplace/identificar",
                                 json={"telefono": "3001112233", "pin": "1234"})
            self.assertEqual(r.json, {"ok": True, "tercero_id": 61, "nombre": "D"})
            with self.client.session_transaction() as s:
                self.assertEqual(s["usuario_id"], 61)
                self.assertEqual(s["rol"], "Cliente")
        with patch.object(marketplace, "get_db_connection",
                          return_value=SesionConn({"id": 61, "nombre": "D",
                                                   "pin_seguridad": bueno})):
            r = self.client.post("/api/marketplace/identificar",
                                 json={"telefono": "3001112233", "pin": "9999"})
            self.assertEqual(r.status_code, 401)
            self.assertIn("PIN incorrecto", r.json["error"])
        conn = SesionConn({"id": 61, "nombre": "D", "pin_seguridad": None})
        with patch.object(marketplace, "get_db_connection", return_value=conn):
            r = self.client.post("/api/marketplace/identificar",
                                 json={"telefono": "3001112233", "pin": "1234"})
            self.assertTrue(r.json["ok"])
            self.assertTrue(any("UPDATE terceros SET pin_seguridad" in s for s, _ in conn.sql))
        with patch.object(marketplace, "get_db_connection", return_value=SesionConn(None)):
            r = self.client.post("/api/marketplace/identificar",
                                 json={"telefono": "3001112233", "pin": "1234"})
            self.assertEqual(r.status_code, 400)
            r = self.client.post("/api/marketplace/identificar",
                                 json={"telefono": "3009998877", "nombre": "Nuevo",
                                       "pin": "1234"})
            self.assertEqual(r.json["tercero_id"], 51)
            r = self.client.post("/api/marketplace/identificar",
                                 json={"telefono": "3001112233", "pin": "12"})
            self.assertEqual(r.status_code, 400)

    def _contacto(self, ses=None, galleta=None, fila=None):
        from flask import session as fsession
        if fila is None:
            fila = {"id": 61, "nombre": "David", "telefono": "3001112233",
                    "direccion": None}
        with patch.dict(os.environ, {"MARKETPLACE_SIGNING_KEY": "k"}):
            env = {}
            if galleta:
                firmado = marketplace._firma_comprador().dumps(galleta)
                env = {"HTTP_COOKIE": f"{marketplace.COMPRADOR}={firmado}"}
            with self.app.test_request_context("/", environ_overrides=env):
                for k, v in (ses or {}).items():
                    fsession[k] = v
                with patch.object(marketplace, "get_db_connection",
                                  return_value=SesionConn(fila)):
                    return marketplace._contacto_publicar()

    def test_contacto_publicar_usuario_gana_a_invitado(self):
        galleta = {"nombre": "G", "telefono": "1", "cliente_id": 5}
        self.assertEqual(self._contacto({"chat_tercero_id": 61}),
                         {"nombre": "David", "telefono": "3001112233"})
        self.assertEqual(self._contacto(None, galleta),
                         {"nombre": "G", "telefono": "1"})
        self.assertEqual(self._contacto({"chat_tercero_id": 61}, galleta),
                         {"nombre": "David", "telefono": "3001112233"})
        self.assertEqual(self._contacto(), {"nombre": "", "telefono": ""})
        sin_tel = {"id": 61, "nombre": "David", "telefono": None, "direccion": None}
        self.assertEqual(self._contacto({"chat_tercero_id": 61}, galleta, sin_tel),
                         {"nombre": "David", "telefono": "1"})

    def test_publicar_prellena_datos_del_usuario(self):
        fila_u = {"id": 61, "nombre": "David", "telefono": "3001112233",
                  "direccion": None}
        with patch.dict(os.environ, {"MARKETPLACE_SIGNING_KEY": "k"}):
            with patch.object(marketplace, "get_db_connection", return_value=SesionConn(fila_u)), \
                 patch.object(marketplace, "_asegurar_tiendas_publicacion"), \
                 patch.object(marketplace, "_negocios_del_titular", return_value=[]):
                with self.client.session_transaction(base_url="https://tuc-tuc.co/") as s:
                    s["chat_tercero_id"] = 61
                pagina = self.client.get("/marketplace/publicar",
                                         base_url="https://tuc-tuc.co/")
        html = pagina.get_data(as_text=True)
        self.assertIn('value="David"', html)
        self.assertIn('value="3001112233"', html)
        self.assertIn('name="nombre_negocio"', html)
        self.assertIn('data-sugerido="David"', html)

    def test_campana_abre_oferta_directa_y_firma_origen_por_producto(self):
        comercial = marketplace.comercial
        ficha = dict(tipo="productos", id=19, negocio_id=61, nombre="Combo de prueba",
                     categoria="Productos", negocio="Tienda", slug="tienda", precio=Decimal("25000"),
                     imagen=None, ambito="productos")
        codigo = "A" * 24
        conn = Registro()
        with patch.object(comercial, "asegurar_comisiones"), \
             patch.object(marketplace, "get_db_connection") as db, \
             patch.object(comercial, "buscar_campana", return_value={"producto_id": 19, "negocio_id": 61}), \
             patch.object(marketplace, "_ficha_campana", return_value=ficha):
            db.return_value.__enter__.return_value = conn
            pagina = self.client.get("/marketplace", query_string={"campana": codigo}, base_url="https://tuc-tuc.co")
        self.assertEqual(pagina.status_code, 200)
        html = pagina.get_data(as_text=True)
        self.assertIn('data-id="19"', html)
        self.assertIn("Comprar</button>", html)
        self.assertNotIn("Visitar tienda", html)
        self.assertIn("no-store", pagina.headers["Cache-Control"])
        cookie = self.client.get_cookie(comercial.COOKIE_CAMPANA, domain="tuc-tuc.co")
        self.assertTrue(cookie.http_only)
        with self.app.test_request_context(headers={"Cookie": f"{comercial.COOKIE_CAMPANA}={cookie.value}"}):
            self.assertEqual(marketplace.origenes_campana(), {"19": codigo})
        with self.app.test_request_context(headers={"Cookie": f"{comercial.COOKIE_CAMPANA}={codigo}"}):
            self.assertEqual(marketplace.origenes_campana(), {})

    def test_busqueda_abre_externa_en_pestana_nueva(self):
        with open("../static/marketplace/busqueda.js", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("item.externa", js)
        self.assertIn("_blank", js)

    def test_volver_url_usa_subdominio(self):
        with open("../app/blueprints/negocios.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn(".tuc-tuc.co/?origen=marketplace", src)


if __name__ == "__main__":
    unittest.main()
