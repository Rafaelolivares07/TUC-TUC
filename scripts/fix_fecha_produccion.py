import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection
from app.blueprints.inventarios import _recostear_producto

conn = get_db_connection()

print("Simulando ajuste de fecha a 2026-10-15 para la produccion 1792240718:")

# Actualizar documento_fecha y created_at en movimientos_inventario
conn.execute("""
    UPDATE movimientos_inventario
    SET documento_fecha = '2026-10-15',
        created_at = '2026-10-15 06:00:00'
    WHERE negocio_id = 59 AND referencia_id = 1792240718
""")

# Actualizar fecha y created_at en movimientos_contables
conn.execute("""
    UPDATE movimientos_contables
    SET fecha = '2026-10-15',
        created_at = '2026-10-15 06:00:00'
    WHERE negocio_id = 59 AND origen_id = '1792240718'
""")

# Recostear producto 302 y sus componentes
prods_a_recostear = [302, 265, 298, 301, 287, 318]
for pid in prods_a_recostear:
    res = _recostear_producto(conn, 59, pid, bodega=1)
    print(f"Recosteado {pid} ({res['producto_nombre']}): Stock={res['stock_final']}, Costo={res['costo_final']}, PedidosAjustados={res['pedidos_ajustados']}")

# Ver Kardex cronologico de 302 ahora
kardex_302 = conn.execute("""
    SELECT m.id, m.documento_fecha, m.tipo, m.cantidad, m.costo_und, m.referencia_tipo, m.referencia_id
    FROM movimientos_inventario m
    WHERE m.negocio_id = 59 AND m.producto_id = 302 AND m.documento_fecha >= '2026-10-13'
    ORDER BY m.documento_fecha ASC, m.id ASC
""").fetchall()

print("\n--- KARDEX REORGANIZADO CRONOLOGICAMENTE ---")
saldo_acum = 0
hay_negativos = False
for k in kardex_302:
    cant = float(k['cantidad'])
    saldo_acum += (cant if k['tipo'] == 'entrada' else -cant)
    if saldo_acum < 0:
        hay_negativos = True
    if k['referencia_id'] == 1792240718 or saldo_acum < 0:
        print(f"ID:{k['id']} | Fecha:{k['documento_fecha']} | Tipo:{k['tipo']:7s} | Cant:{cant:8.2f} | SaldoAcum:{saldo_acum:8.2f} | Ref:{k['referencia_tipo']} #{k['referencia_id']}")

print(f"\n¿Hubo saldos negativos durante el periodo?: {hay_negativos}")
print(f"Saldo final de Pechuga Preparada (302): {saldo_acum} gr")

# Commit de la correccion
conn.commit()
conn.close()
print("Correccion guardada exitosamente en la base de datos.")
