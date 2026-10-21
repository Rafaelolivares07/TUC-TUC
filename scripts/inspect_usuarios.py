import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.db import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    try:
        t = conn.execute("SELECT id, nombre, telefono, telegram_chat_id FROM terceros WHERE telegram_chat_id IS NOT NULL").fetchall()
        print("TERCEROS CON TELEGRAM:")
        for r in t:
            print(dict(r))
        
        t_raf = conn.execute("SELECT id, nombre, telefono, telegram_chat_id FROM terceros WHERE nombre ILIKE %s", ('%rafael%',)).fetchall()
        print("\nTERCEROS RAFAEL:")
        for r in t_raf:
            print(dict(r))

        cs = conn.execute('SELECT * FROM "CONFIGURACION_SISTEMA"').fetchall()
        print("\nCONFIGURACION_SISTEMA:")
        for r in cs:
            print(dict(r))
    finally:
        conn.close()
