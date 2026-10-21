import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

comp_ids = [265, 298, 301, 287, 318]
for cid in comp_ids:
    p = conn.execute("SELECT id, nombre, costo FROM productos WHERE id = %s", (cid,)).fetchone()
    s = conn.execute("SELECT stock, costo_und FROM saldos_inventario WHERE negocio_id = 59 AND producto_id = %s AND bodega = 1", (cid,)).fetchone()
    tot = conn.execute("""
        SELECT SUM(CASE WHEN tipo = 'entrada' THEN cantidad ELSE -cantidad END) as total_stock
        FROM movimientos_inventario
        WHERE negocio_id = 59 AND producto_id = %s AND (bodega = 1 OR bodega IS NULL)
    """, (cid,)).fetchone()
    print(f"Producto {cid} ({p['nombre']}):")
    print(f"   Saldo en tabla: {s['stock'] if s else 0} | Total en Kardex: {tot['total_stock']}")

    # Ver los ultimos 5 movimientos de este componente
    ult_movs = conn.execute("""
        SELECT id, documento_fecha, tipo, cantidad, referencia_tipo, referencia_id
        FROM movimientos_inventario
        WHERE negocio_id = 59 AND producto_id = %s
        ORDER BY id DESC LIMIT 5
    """, (cid,)).fetchall()
    for um in ult_movs:
        print(f"      Mov ID:{um['id']} | Fecha:{um['documento_fecha']} | Tipo:{um['tipo']} | Cant:{um['cantidad']} | Ref:{um['referencia_tipo']} #{um['referencia_id']}")

conn.close()
