import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import get_db_connection
from app.blueprints.tiendas import _obtener_negocio_por_slug, _enviar_telegram_tienda

def test_slug_resolution():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        negocio = _obtener_negocio_por_slug(conn, 'sandwiches-del-pitt')
        print("Negocio por slug:", negocio)
        assert negocio['telegram_chat_id'] == '7917183791', f"Expected 7917183791 but got {negocio.get('telegram_chat_id')}"
        print("TEST PASSED! telegram_chat_id correctly resolved to:", negocio['telegram_chat_id'])
        conn.close()

if __name__ == "__main__":
    test_slug_resolution()
