import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

print("--- DETALLE COMPROBANTE 811 ---")
for r in conn.execute("SELECT * FROM movimientos_contables WHERE comprobante_id = 811 ORDER BY id").fetchall():
    print(dict(r))

print("\n--- DETALLE COMPROBANTE 457 ---")
for r in conn.execute("SELECT * FROM movimientos_contables WHERE comprobante_id = 457 ORDER BY id").fetchall():
    print(dict(r))

conn.close()
