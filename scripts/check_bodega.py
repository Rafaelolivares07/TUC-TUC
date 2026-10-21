import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

m = conn.execute("SELECT id, bodega, producto_id, cantidad, tipo, documento_fecha FROM movimientos_inventario WHERE id = 5562").fetchone()
print("Movimiento 5562:", dict(m))

saldos = conn.execute("SELECT id, producto_id, bodega, stock, costo_und, valor_existencia FROM saldos_inventario WHERE negocio_id = 59 AND producto_id = 302").fetchall()
print("Saldos 302 en todas las bodegas:")
for s in saldos:
    print(dict(s))

conn.close()
