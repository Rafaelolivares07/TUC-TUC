import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.db import get_db_connection
from app.blueprints.restaurantes import _enviar_telegram

def test_ping():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        config = conn.execute('SELECT telegram_token, telegram_chat_id FROM "CONFIGURACION_SISTEMA" WHERE id = 1').fetchone()
        token = config['telegram_token'] if config else None
        token = token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        
        bot_info = {}
        if token:
            try:
                r = requests.get(f'https://api.telegram.org/bot{token}/getMe').json()
                bot_info = r.get('result', {})
                print(f"BOT OFICIAL DEL SISTEMA: @{bot_info.get('username')} ({bot_info.get('first_name')})")
            except Exception as e:
                print(f"Error consultando bot: {e}")

        rest = conn.execute("SELECT id, nombre, slug, telegram_chat_id FROM restaurantes WHERE telegram_chat_id IS NOT NULL ORDER BY id DESC LIMIT 5").fetchall()
        print("Restaurantes con Telegram:", [dict(r) for r in rest])
        
        targets = set()
        for r in rest:
            if r['telegram_chat_id']:
                targets.add((r['telegram_chat_id'], f"Restaurante: {r['nombre']}"))

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
