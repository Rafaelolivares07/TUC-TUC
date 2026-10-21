import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable', cursor_factory=RealDictCursor)
cur = conn.cursor()

print("=== ENTRADAS EN 2026-09-27 (PRICESMART Y OTROS) ===")
cur.execute("""
    SELECT m.id, m.created_at, m.documento_fecha, m.tipo, m.motivo, m.cantidad, m.valor_unitario, m.valor_total, m.costo_und,
           m.documento_numero, m.proveedor_nombre,
           p.id as prod_id, p.nombre as producto, p.costo as prod_costo_actual,
           pr.id as pres_id, pr.nombre as pres_nombre, pr.equivalencia as pres_equiv
    FROM movimientos_inventario m
    JOIN productos p ON p.id = m.producto_id
    LEFT JOIN presentaciones pr ON pr.id = m.presentacion_id
    WHERE m.tipo = 'entrada'
    ORDER BY m.id DESC LIMIT 30
""")
for row in cur.fetchall():
    print(dict(row))
