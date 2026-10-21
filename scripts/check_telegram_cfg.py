import psycopg2
import psycopg2.extras
import os

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

print("=== CONFIGURACION_SISTEMA ===")
cur.execute('SELECT id, telegram_token, telegram_chat_id FROM "CONFIGURACION_SISTEMA"')
for r in cur.fetchall():
    print(dict(r))

print("TELEGRAM_BOT_TOKEN ENV:", os.environ.get('TELEGRAM_BOT_TOKEN'))

print("\n=== CENTROS UTILIDAD (negocio 59) ===")
cur.execute("SELECT id, negocio_id, nombre, codigo, telegram_chat_id FROM centros_utilidad WHERE negocio_id = 59")
for r in cur.fetchall():
    print(dict(r))

print("\n=== TIENDAS / RESTAURANTES (tercero_id 59) ===")
cur.execute("SELECT id, tercero_id, nombre, telegram_chat_id, admin_id FROM tiendas WHERE tercero_id = 59")
for r in cur.fetchall():
    print("TIENDA:", dict(r))
cur.execute("SELECT id, tercero_id, nombre, telegram_chat_id, admin_id FROM restaurantes WHERE tercero_id = 59")
for r in cur.fetchall():
    print("RESTAURANTE:", dict(r))
    if r['admin_id']:
        cur.execute("SELECT id, nombre, telegram_chat_id FROM terceros WHERE id = %s", (r['admin_id'],))
        adm = cur.fetchone()
        print("  ADMIN:", dict(adm) if adm else None)
