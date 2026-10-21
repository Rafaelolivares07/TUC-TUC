import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== ORIGINAL 24 EXPENSE LINES ===")
original_line_ids = [
    3671, 3672, 3731, 3732, 3733, 3734, 3735, 3738, 3956, 3958, 3959, 
    3960, 3961, 3962, 3963, 4214, 4215, 4216, 4217, 4218, 4416, 4476, 4887, 4888
]

cur.execute('''
    SELECT id, comprobante_id, numero_documento, tipo_documento, fecha, tipo, monto, cuenta, concepto, tercero_id, meses_duracion, modalidad_amortizacion, cuota_numero, cuota_total
    FROM movimientos_contables
    WHERE id = ANY(%s)
    ORDER BY id ASC
''', (original_line_ids,))

total_orig = 0.0
for r in cur.fetchall():
    print(f"id {r['id']:4d} | doc #{r['numero_documento']:3s} | cta: {r['cuenta']:8s} | monto: {float(r['monto']):12,.2f} | dur: {r['meses_duracion']}m | conc: {r['concepto']}")
    total_orig += float(r['monto'])

print(f"\nTotal sum of current primary lines: {total_orig:,.2f}")
