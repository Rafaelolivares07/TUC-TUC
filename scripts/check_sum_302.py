import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

total_kardex = conn.execute("""
    SELECT 
        SUM(CASE WHEN tipo = 'entrada' THEN cantidad ELSE -cantidad END) as total_stock,
        SUM(CASE WHEN tipo = 'entrada' THEN cantidad ELSE 0 END) as total_entradas,
        SUM(CASE WHEN tipo = 'salida' THEN cantidad ELSE 0 END) as total_salidas
    FROM movimientos_inventario
    WHERE negocio_id = 59 AND producto_id = 302 AND (bodega = 1 OR bodega IS NULL)
""").fetchone()

print("Kardex completo de 302:", dict(total_kardex))

saldo = conn.execute("SELECT stock, costo_und FROM saldos_inventario WHERE negocio_id = 59 AND producto_id = 302 AND bodega = 1").fetchone()
print("Saldo tabla saldos_inventario:", dict(saldo))

conn.close()
