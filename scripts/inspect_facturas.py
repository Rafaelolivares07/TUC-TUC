import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

for doc in ['193666', '17434', '8870', '111158', '11650', '1125635', '115475']:
    print(f"\n--- INVENTARIO PARA FACTURA {doc} ---")
    cur.execute('''
        SELECT id, producto_id, nombre_producto, cantidad, valor_unitario, valor_total
        FROM movimientos_inventario
        WHERE negocio_id = 59 AND documento_numero = %s;
    ''', (doc,))
    rows = cur.fetchall()
    tot = sum(r[5] for r in rows if r[5] is not None)
    print(f"Total movimientos: {len(rows)} | Suma: {tot}")
    for r in rows:
        print(" ", r)

cur.close()
conn.close()
