import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import get_db_connection

def check_recent_orders():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        pedidos = conn.execute("""
            SELECT id, fecha, total, cliente_id, nombre_cliente, tipo_entrega, 
                   tienda_id, restaurante_id, centro_utilidad_id, origen
            FROM pedidos 
            ORDER BY id DESC 
            LIMIT 5
        """).fetchall()
        print("ULTIMOS 5 PEDIDOS:")
        for p in pedidos:
            print(dict(p))
            if p['tienda_id']:
                t = conn.execute("SELECT id, nombre, slug, telegram_chat_id, admin_id, tercero_id FROM tiendas WHERE id=%s", (p['tienda_id'],)).fetchone()
                print("  TIENDA:", dict(t) if t else None)
            if p['restaurante_id']:
                r = conn.execute("SELECT id, nombre, slug, telegram_chat_id, admin_id, tercero_id FROM restaurantes WHERE id=%s", (p['restaurante_id'],)).fetchone()
                print("  RESTAURANTE:", dict(r) if r else None)
            if p['centro_utilidad_id']:
                cu = conn.execute("SELECT id, codigo, nombre, telegram_chat_id, tercero_id FROM centros_utilidad WHERE id=%s", (p['centro_utilidad_id'],)).fetchone()
                print("  CENTRO_UTILIDAD:", dict(cu) if cu else None)
        conn.close()

if __name__ == "__main__":
    check_recent_orders()
