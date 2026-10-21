import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

print('=== DETALLES DE LA PRODUCCION 63 (referencia_id 1792240718) ===')
movs_63 = conn.execute("""
    SELECT m.id, m.created_at, m.documento_fecha, m.tipo, m.cantidad, m.valor_unitario, m.valor_total,
           m.referencia_tipo, m.referencia_id, m.producto_id, p.nombre as producto_nombre
    FROM movimientos_inventario m
    JOIN productos p ON p.id = m.producto_id
    WHERE m.negocio_id = 59 AND m.referencia_id = 1792240718
""").fetchall()
for m in movs_63:
    print(dict(m))

print('\n=== RECETA DE 302 ===')
te = conn.execute("""
    SELECT te.producto_id, p1.nombre as terminado, te.componente_id, p2.nombre as componente, te.cantidad
    FROM tarjeta_estandar te
    JOIN productos p1 ON p1.id = te.producto_id
    JOIN productos p2 ON p2.id = te.componente_id
    WHERE te.producto_id = 302
""").fetchall()
for row in te:
    print(dict(row))



print('\n=== SALDOS ACTUALES DE 302 Y SUS COMPONENTES ===')
saldos = conn.execute("""
    SELECT s.producto_id, p.nombre, s.bodega, s.stock, s.costo_und
    FROM saldos_inventario s
    JOIN productos p ON p.id = s.producto_id
    WHERE s.negocio_id = 59 AND s.producto_id IN (302, 265, 298, 301, 287, 318)
""").fetchall()
for s in saldos:
    print(dict(s))

print('\n=== HISTORIAL COMPLETO DE MOVIMIENTOS DE PRODUCTO 302 DESDE EL 13 DE OCTUBRE ===')
kardex_302 = conn.execute("""
    SELECT m.id, m.created_at, m.documento_fecha, m.tipo, m.cantidad, m.valor_unitario, m.valor_total,
           m.referencia_tipo, m.referencia_id
    FROM movimientos_inventario m
    WHERE m.negocio_id = 59 AND m.producto_id = 302 AND m.documento_fecha >= '2026-10-13'
    ORDER BY m.documento_fecha ASC, m.id ASC
""").fetchall()
total_stock = 0
for k in kardex_302:
    cant = float(k['cantidad'])
    if k['tipo'] == 'entrada':
        total_stock += cant
    else:
        total_stock -= cant
    print(f"ID:{k['id']} | FechaDoc:{k['documento_fecha']} | Tipo:{k['tipo']:7s} | Cant:{cant:8.2f} | SaldoAcum:{total_stock:8.2f} | Ref:{k['referencia_tipo']} #{k['referencia_id']}")

conn.close()
