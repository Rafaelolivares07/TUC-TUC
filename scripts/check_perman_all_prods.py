import os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
import psycopg2

conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
cur = conn.cursor()
cur.execute("""
    SELECT c.item_id, p.nombre, c.tercero_id, t.nombre, c.precio, c.unidades_item, c.descripcion_presentacion
    FROM cotizaciones_compras c
    JOIN productos p ON p.id = c.item_id
    JOIN terceros t ON t.id = c.tercero_id
    WHERE t.nombre ILIKE '%perman%';
""")
for r in cur.fetchall():
    print(r)
cur.close()
conn.close()
