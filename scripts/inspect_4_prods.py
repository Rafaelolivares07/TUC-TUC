import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable', cursor_factory=RealDictCursor)
cur = conn.cursor()

prods = [310, 300, 304, 272]
print("=== MOVIMIENTOS HISTORICOS DE LOS 4 PRODUCTOS ===")
cur.execute("""
    SELECT m.id, m.created_at, m.documento_fecha, m.tipo, m.motivo, m.cantidad, m.valor_unitario, m.valor_total,
           m.stock_anterior, m.stock_nuevo, m.costo_und, m.documento_numero, m.proveedor_nombre,
           m.producto_id, p.nombre as producto, p.costo as prod_costo,
           m.presentacion_id, pr.nombre as pres_nombre, pr.equivalencia as pres_equiv
    FROM movimientos_inventario m
    JOIN productos p ON p.id = m.producto_id
    LEFT JOIN presentaciones pr ON pr.id = m.presentacion_id
    WHERE m.producto_id = ANY(%s)
    ORDER BY m.producto_id, m.id ASC
""", (prods,))
for r in cur.fetchall():
    print(dict(r))

print("\n=== SALDOS INVENTARIO ACTUALES ===")
cur.execute("SELECT * FROM saldos_inventario WHERE producto_id = ANY(%s)", (prods,))
for r in cur.fetchall():
    print(dict(r))
