import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import get_db_connection
from app.blueprints.restaurantes import _enviar_telegram

def test_ping():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        rest = conn.execute("SELECT id, nombre, slug, telegram_chat_id FROM restaurantes WHERE telegram_chat_id IS NOT NULL ORDER BY id DESC LIMIT 5").fetchall()
        tiendas = conn.execute("SELECT id, nombre, slug, telegram_chat_id FROM tiendas WHERE telegram_chat_id IS NOT NULL ORDER BY id DESC LIMIT 5").fetchall()
        terceros = conn.execute("SELECT id, nombre, telegram_chat_id FROM terceros WHERE telegram_chat_id IS NOT NULL ORDER BY id DESC LIMIT 5").fetchall()
        
        print("Restaurantes con Telegram:", [dict(r) for r in rest])
        print("Tiendas con Telegram:", [dict(t) for t in tiendas])
        print("Terceros con Telegram:", [dict(t) for t in terceros])
        
        targets = set()
        for r in rest:
            if r['telegram_chat_id']:
                targets.add((r['telegram_chat_id'], f"Restaurante: {r['nombre']}"))
        for t in tiendas:
            if t['telegram_chat_id']:
                targets.add((t['telegram_chat_id'], f"Tienda: {t['nombre']}"))
        for te in terceros:
            if te['telegram_chat_id']:
                targets.add((te['telegram_chat_id'], f"Tercero: {te['nombre']}"))

        for cid, desc in targets:
            msg = f"🔔 *Prueba de Notificación TucTuc*\n\n✅ Tu conexión con Telegram está funcionando correctamente para *{desc}*.\n\nRecibirás aquí los avisos de tus pedidos y ventas en tiempo real."
            print(f"Enviando prueba a {cid} ({desc})...")
            try:
                _enviar_telegram(conn, cid, msg)
                print(f"Enviado con éxito a {cid}!")
            except Exception as e:
                print(f"Fallo enviando a {cid}: {e}")
        conn.close()

if __name__ == "__main__":
    test_ping()
