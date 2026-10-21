import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== ALL COMPROBANTES DETAILED ===")
cur.execute('''
    SELECT comprobante_id, tipo_documento, numero_documento, 
           SUM(CASE WHEN tipo IN ('debito', 'D') THEN monto ELSE 0 END) AS total_deb,
           SUM(CASE WHEN tipo IN ('credito', 'C') THEN monto ELSE 0 END) AS total_cred,
           COUNT(*) AS cant_lineas
    FROM movimientos_contables
    WHERE tipo_documento = 'GASTO_DE_ENTREGAS'
    GROUP BY comprobante_id, tipo_documento, numero_documento
    ORDER BY CAST(REGEXP_REPLACE(numero_documento, '[^0-9]', '', 'g') AS INTEGER), comprobante_id ASC
''')
for r in cur.fetchall():
    diff = round(float(r['total_deb']) - float(r['total_cred']), 2)
    nd = r['numero_documento']
    is_open = (nd == '5')
    status = "OPEN (RELACION ACTIVA)" if is_open else ("✓ CUADRADO" if diff == 0 else f"⚠️ DESCUADRADO ({diff:,.2f})")
    print(f"Comp {r['comprobante_id']:4d} | Doc #{nd:5s} | Deb: {float(r['total_deb']):12,.2f} | Cred: {float(r['total_cred']):12,.2f} | Diff: {diff:12,.2f} | Lin: {r['cant_lineas']:2d} -> {status}")
