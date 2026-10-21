import sys, os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc'
from app.db import init_db, get_db_connection

init_db(None)
conn = get_db_connection()

t = conn.execute("SELECT id, nombre, slug, tercero_id FROM tiendas LIMIT 5").fetchall()
print("Tiendas:", [dict(x) for x in t])

r = conn.execute("SELECT id, nombre, slug, tercero_id FROM restaurantes LIMIT 5").fetchall()
print("Restaurantes:", [dict(x) for x in r])

if t:
    t_id = t[0]['tercero_id']
    cats = conn.execute("SELECT DISTINCT categoria FROM productos WHERE negocio_id = %s", (t_id,)).fetchall()
    print("Categorias para negocio", t_id, ":", [c['categoria'] for c in cats])

conn.close()
