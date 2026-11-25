import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from flask import Blueprint, Flask, jsonify, request, session

from app.blueprints import marketplace


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
        return {"id": 51} if "INSERT INTO terceros" in self.sql[-1][0] else self.tercero

    def commit(self):
        pass

    def close(self):
        pass


class MarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates")
        self.app.secret_key = "llave-de-pruebas"
        self.app.register_blueprint(marketplace.bp)
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
                          ("descripcion", "Descripción de prueba"), *[("fotos", foto) for foto in fotos]])
        conn = Registro()
        with patch.object(marketplace, "get_db_connection", return_value=conn):
            respuesta = self.client.post("/marketplace/publicar", data=form, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 303)
        guardado = next(params for sql, params in conn.sql if "INSERT INTO marketplace_solicitudes" in sql)
        self.assertEqual(json.loads(guardado[-2]), fotos)
        self.assertEqual(marketplace._fotos_publicacion([]), [])
        with self.assertRaises(ValueError):
            marketplace._fotos_publicacion(["data:image/jpeg;base64,AAAA"])

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
                      descripcion="Descripción", fotos=[], estado="recibida", revision=1, contacto_publico=False)
        with patch.object(marketplace, "_solicitudes_editor", return_value=(actual, [actual])):
            html = self.client.get(respuesta.location).get_data(as_text=True)
        self.assertIn("Oferta recuperada", html)
        self.assertIn("Guardar cambios", html)
        self.assertIn('id="market-fotos"', html)

    def test_login_administrativo_habilita_revision_y_logout_la_cierra(self):
        from app.blueprints import auth

        class RegistroAdmin(Registro):
            def fetchall(self):
                return []

        host = "https://admin.tuc-tuc.co"
        self.app.register_blueprint(auth.bp)
        conn = RegistroAdmin(dict(id=9, rol="Administrador", nombre="Admin"))
        with patch.object(auth, "get_db_connection", return_value=conn):
            login = self.client.post("/admin/login", base_url=host,
                                     data={"usuario": "admin-prueba", "password": "clave-prueba"})
        self.assertEqual(login.status_code, 302)
        self.assertTrue(any(marketplace.MODERACION in h and "HttpOnly" in h and "Secure" in h
                            for h in login.headers.getlist("Set-Cookie")))
        with patch.object(marketplace, "_conexion_publicaciones", return_value=conn):
            tablero = self.client.get("/admin/marketplace", base_url=host)
        self.assertIn("Aún no hay solicitudes", tablero.get_data(as_text=True))
        salida = self.client.get("/admin/logout", base_url=host)
        self.assertTrue(any(marketplace.MODERACION in h and "Max-Age=0" in h
                            for h in salida.headers.getlist("Set-Cookie")))
        login_revision = self.client.get("/admin/marketplace", base_url=host)
        self.assertIn("Ingresa con tu usuario administrador", login_revision.get_data(as_text=True))

    def test_revision_requiere_la_cookie_de_moderacion(self):
        host = "https://admin.tuc-tuc.co"
        with self.client.session_transaction(base_url=host) as acceso:
            acceso["rol"] = "Administrador"
            acceso["usuario_id"] = 9
        self.assertEqual(self.client.post("/admin/marketplace/aprobar", base_url=host,
                                          data={"solicitud": 27}).status_code, 403)
        portada = self.client.get("/admin/marketplace", base_url=host)
        self.assertIn("Ingresa con tu usuario administrador", portada.get_data(as_text=True))
        self.assertEqual(self.client.get("/admin/marketplace", base_url="https://tuc-tuc.co").status_code, 404)

    def test_aprobacion_reusa_producto_y_su_galeria_en_la_revision(self):
        conn = Registro({"id": 95})
        solicitud = dict(id=27, nombre="Diana", telefono="3151112222", tipo="servicio",
                         titulo="Oferta", descripcion="Detalles", fotos=["portada", "galeria"],
                         estado="recibida", revision=2, producto_id=None)
        marketplace._aprobar_publicacion(conn, solicitud)
        alta = next(params for sql, params in conn.sql if "INSERT INTO productos" in sql)
        self.assertEqual(alta, (95, "Oferta", "Servicios", "Detalles", "portada"))
        self.assertTrue(any(params == (95, "galeria", 1) for sql, params in conn.sql
                            if "INSERT INTO producto_imagenes" in sql))
        conn.sql.clear()
        solicitud["producto_id"] = 95
        marketplace._aprobar_publicacion(conn, solicitud)
        self.assertFalse(any("INSERT INTO productos" in sql for sql, _ in conn.sql))
        self.assertTrue(any("UPDATE productos" in sql for sql, _ in conn.sql))

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


if __name__ == "__main__":
    unittest.main()
