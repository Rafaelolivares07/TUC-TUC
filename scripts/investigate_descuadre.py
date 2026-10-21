import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print("=== CONTEO DE MOVIMIENTOS POSTERIORES PARA TOMATE Y LECHUGA ===")
cur.execute('''
    SELECT producto_id, nombre_producto, tipo, COUNT(*), SUM(cantidad)
    FROM movimientos_inventario
    WHERE negocio_id = 59 AND producto_id IN (259, 263) AND created_at > '2026-09-27 14:50:00'
    GROUP BY producto_id, nombre_producto, tipo;
''')
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
