import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("""
    SELECT id, documento_fecha, created_at, tipo, motivo, cantidad, valor_unitario, valor_total, documento_numero, tipo_documento
    FROM movimientos_inventario
    WHERE negocio_id = 59 AND producto_id = 260
    ORDER BY created_at ASC;
""")
all_movs = cur.fetchall()

print("=== DIFERENCIA ENTRE ORDER BY created_at Y ORDER BY documento_fecha ===")
print("Movimientos donde documento_fecha difiere sustancialmente de created_at::date:")
for m in all_movs:
    f_doc = str(m[1]) if m[1] else ''
    c_at = str(m[2])[:10]
    if f_doc and f_doc != c_at:
        print(f"ID {m[0]} | f_doc={f_doc} vs created_at={c_at} | Doc: {m[9]} #{m[8]} | {m[3]}/{m[4]} | Cant: {m[5]}")

cur.close()
conn.close()
