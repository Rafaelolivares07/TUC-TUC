import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("--- Step 1: Fix Saldo por Amortizar lines ---")
mappings = [
    # (saldo_id, target_comp, target_doc)
    (4889, 548, '3'),
    (4893, 653, '4'),
    (4898, 657, '6'),
    (4902, 658, '7'),
    (4906, 660, '8'),
    (4910, 662, '9'),
    (4914, 664, '10'),
    (4918, 666, '11'),
    (4922, 668, '12'),
    (4926, 670, '13'),
    (4930, 672, '14'),
    (4934, 674, '15'),
    (4938, 676, '16'),
    (4942, 678, '17'),
    (4946, 680, '18'),
    (4950, 682, '19'),
]

for saldo_id, target_comp, target_doc in mappings:
    cur.execute('''
        UPDATE movimientos_contables
        SET comprobante_id = %s, numero_documento = %s
        WHERE id = %s
    ''', (target_comp, target_doc, saldo_id))

print(f"Updated {len(mappings)} saldo lines.")

print("--- Step 2: Clean orphan lines in Doc 5 ---")
# id 4477 and id 4738 were replaced by 4888 and 4887
cur.execute("DELETE FROM movimientos_contables WHERE id IN (4477, 4738)")
print("Deleted old superseded lines 4477, 4738.")

# Ensure Doc 5 has only id 3732 and 4897, both under comp 655
cur.execute("UPDATE movimientos_contables SET comprobante_id = 655 WHERE id IN (3732, 4897)")

# Ensure remaining open lines are under comp 684 and doc 20
cur.execute('''
    UPDATE movimientos_contables
    SET comprobante_id = 684, numero_documento = '20'
    WHERE id IN (3731, 3738, 3956, 3958, 3959, 3961, 3963)
''')

# Update consecutive in tipos_documento_negocio
cur.execute('''
    UPDATE tipos_documento_negocio
    SET consecutivo = 19
    WHERE codigo = 'GASTO_DE_ENTREGAS'
''')

conn.commit()
print("Committed successfully!")

print("\n=== VERIFICATION OF ALL COMPROBANTES ===")
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
all_ok = True
for r in cur.fetchall():
    diff = round(float(r['total_deb']) - float(r['total_cred']), 2)
    nd = r['numero_documento']
    is_open = (nd == '20')
    status = "OPEN (RELACION ACTIVA)" if is_open else ("✓ CUADRADO" if diff == 0 else f"⚠️ DESCUADRADO ({diff:,.2f})")
    if not is_open and diff != 0:
        all_ok = False
    print(f"Comp {r['comprobante_id']:4d} | Doc #{nd:5s} | Deb: {float(r['total_deb']):12,.2f} | Cred: {float(r['total_cred']):12,.2f} | Diff: {diff:12,.2f} | Lin: {r['cant_lineas']:2d} -> {status}")

print(f"\nAll closed documents balanced: {all_ok}")
