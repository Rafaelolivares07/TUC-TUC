import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable', cursor_factory=RealDictCursor)
cur = conn.cursor()

print("=== MOVIMIENTOS INVENTARIO PARA DOCUMENTO 15 Y 13 ===")
cur.execute("""
    SELECT id, documento_numero, created_at, tipo, motivo, cantidad, valor_total, producto_id, bodega
    FROM movimientos_inventario
    WHERE documento_numero IN ('15', '13', '84', '14') OR documento_numero LIKE '%15%' OR documento_numero LIKE '%13%'
    ORDER BY documento_numero, id
""")
for r in cur.fetchall():
    print(dict(r))

print("\n=== MOVIMIENTOS CONTABLES PARA DOCUMENTO 15 Y 13 ===")
cur.execute("""
    SELECT id, comprobante_id, numero_documento, cuenta, concepto, tipo, monto, producto_id, centro_utilidad_id, created_at
    FROM movimientos_contables
    WHERE numero_documento IN ('15', '13', '84', '14') OR numero_documento LIKE '%15%' OR numero_documento LIKE '%13%'
    ORDER BY numero_documento, comprobante_id, id
""")
for r in cur.fetchall():
    print(dict(r))
