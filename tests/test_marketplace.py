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
