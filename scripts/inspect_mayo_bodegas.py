import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("""
    SELECT m.id, m.created_at, m.documento_fecha, m.bodega, cu.nombre AS bodega_nombre,
           m.documento_numero, m.tipo_documento, m.tipo, m.motivo, m.cantidad,
           m.stock_anterior, m.stock_nuevo, m.valor_unitario, m.valor_total
    FROM movimientos_inventario m
    LEFT JOIN centros_utilidad cu ON cu.id = m.bodega
    WHERE m.negocio_id = 59 AND m.producto_id = 260
    ORDER BY m.id ASC;
""")
rows = cur.fetchall()
print(f"Total movimientos Mayonesa: {len(rows)}")
for r in rows:
    # Print if between Sep 01 and Sep 25
    c_at = str(r[1])[:10]
    if '2026-09-01' <= c_at <= '2026-09-25':
        print(f"ID {r[0]} | {r[1]} | B:{r[3]} ({r[4]}) | Doc: {r[6]} #{r[5]} | {r[7]}/{r[8]} | Cant: {r[9]} | Ant: {r[10]} -> Nvo: {r[11]} | Tot: {r[13]}")

cur.close()
conn.close()
