import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

for cid, tok in [(423, '1787768129'), (373, '1786742355'), (805, '1791581312')]:
    print(f"\n=== PROD COMP {cid} (token: {tok}) ===")
    cur.execute('''
        SELECT id, cuenta, concepto, tipo, monto, producto_id, created_at
        FROM movimientos_contables
        WHERE comprobante_id = %s;
    ''', (cid,))
    print("Contabilidad:")
    for r in cur.fetchall():
        print(" ", r)

    cur.execute('''
        SELECT id, producto_id, nombre_producto, tipo, cantidad, valor_unitario, valor_total, created_at
        FROM movimientos_inventario
        WHERE negocio_id = 59 AND CAST(referencia_id AS text) = %s;
    ''', (tok,))
    print("Inventario:")
    for r in cur.fetchall():
        print(" ", r)

cur.close()
conn.close()
