import os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
import psycopg2

conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
cur = conn.cursor()
cur.execute("""
    SELECT p.id, p.nombre, p.dias_max_stock, p.dias_min_stock, p.stock_minimo,
           s.stock, c.id, c.tercero_id, t.nombre, c.precio, c.unidades_item, c.descripcion_presentacion
    FROM productos p
    LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.bodega = 1
    LEFT JOIN cotizaciones_compras c ON c.item_id = p.id
    LEFT JOIN terceros t ON t.id = c.tercero_id
    WHERE p.nombre ILIKE '%perman%' OR p.nombre ILIKE '%pan%'
    LIMIT 20;
""")
for r in cur.fetchall():
    print(r)

print("\n--- ALERTAS ACTIVAS ---")
cur.execute("""
    SELECT a.id, a.producto_id, p.nombre, a.stock_minimo, a.estado, a.bodega
    FROM inventario_alertas_agotados a
    JOIN productos p ON p.id = a.producto_id
    WHERE a.estado = 'agotado';
""")
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
