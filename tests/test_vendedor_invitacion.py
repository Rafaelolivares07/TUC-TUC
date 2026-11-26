import unittest
from unittest.mock import patch

from flask import Flask, session

from app.blueprints import vendedor


class VendedorInvitacionTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__, template_folder="../templates")
        app.secret_key = "clave-de-pruebas"
        app.register_blueprint(vendedor.bp)
        self.app = app
        self.host = "https://desk.tuc-tuc.co"

    def test_vista_previa_no_gasta_la_invitacion(self):
        navegador = self.app.test_client()
        telegram = self.app.test_client()
        enlace = "/vendedor?invite=token-de-prueba"

        def identificar(token):
            self.assertEqual(token, "token-de-prueba")
            session["dispositivo_id"] = "dispositivo-de-prueba"
            return True

        with patch.object(vendedor, "_procesar_invitacion", side_effect=identificar) as procesar:
            vista = telegram.get(enlace, base_url=self.host, headers={"User-Agent": "TelegramBot"})
            self.assertEqual(vista.status_code, 200)
            self.assertEqual(vista.headers["Referrer-Policy"], "no-referrer")
            self.assertEqual(telegram.head(enlace, base_url=self.host).status_code, 200)
            formulario = navegador.get(enlace, base_url=self.host)
            self.assertIn("Continuar", formulario.get_data(as_text=True))
            procesar.assert_not_called()
            with navegador.session_transaction(base_url=self.host) as sesion:
                csrf = sesion["vendedor_invitacion_csrf"]

            datos = {"invite": "token-de-prueba", "csrf": csrf}
            cruzado = telegram.post("/vendedor/invitacion", base_url=self.host, data=datos)
            self.assertEqual(cruzado.status_code, 400)
            procesar.assert_not_called()

            acceso = navegador.post("/vendedor/invitacion", base_url=self.host, data=datos)
            self.assertEqual(acceso.status_code, 303)
            self.assertEqual(acceso.location, "/vendedor")
            self.assertTrue(any(x.startswith("tuctuc_device=") for x in acceso.headers.getlist("Set-Cookie")))
            procesar.assert_called_once_with("token-de-prueba")

    def test_enlace_usado_muestra_el_estado(self):
        navegador = self.app.test_client()
        navegador.get("/vendedor?invite=ya-usado", base_url=self.host)
        with navegador.session_transaction(base_url=self.host) as sesion:
            csrf = sesion["vendedor_invitacion_csrf"]
        with patch.object(vendedor, "_procesar_invitacion", return_value=False):
            respuesta = navegador.post("/vendedor/invitacion", base_url=self.host,
                                       data={"invite": "ya-usado", "csrf": csrf})
        self.assertEqual(respuesta.status_code, 410)
        self.assertIn("ya se usó", respuesta.get_data(as_text=True))
