import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable', cursor_factory=RealDictCursor)
cur = conn.cursor()

print("=== TODOS LOS MOVIMIENTOS DE AJUSTE FISICO ===")
cur.execute("""
    SELECT m.id, m.documento_numero, m.created_at, m.tipo, m.motivo, m.cantidad, m.valor_total,
           m.producto_id, p.nombre as producto, m.bodega, m.referencia_id, m.referencia_tipo
    FROM movimientos_inventario m
    JOIN productos p ON p.id = m.producto_id
    WHERE m.motivo = 'ajuste'
    ORDER BY m.id DESC
""")
for r in cur.fetchall():
    print(dict(r))

print("\n=== MOVIMIENTOS CONTABLES VINCULADOS A ESOS DOCUMENTOS ===")
cur.execute("""
    SELECT mc.id, mc.comprobante_id, mc.numero_documento, mc.cuenta, mc.concepto, mc.tipo, mc.monto, mc.producto_id
    FROM movimientos_contables mc
    WHERE mc.numero_documento IN ('15', '14', '13', '84')
    ORDER BY mc.numero_documento, mc.comprobante_id, mc.id
""")
for r in cur.fetchall():
    print(dict(r))
