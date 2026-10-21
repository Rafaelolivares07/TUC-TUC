import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Let's inspect each closed line and its corresponding credit, debit cuota 1, and debit saldo activo
cur.execute('''
    SELECT c.id AS cred_id, c.numero_documento AS doc_num, c.comprobante_id AS comp_id, c.monto AS cred_monto, c.concepto AS cred_conc,
           d.id AS deb_id, d.monto AS deb_monto, d.concepto AS deb_conc,
           s.id AS saldo_id, s.monto AS saldo_monto, s.comprobante_id AS saldo_comp, s.numero_documento AS saldo_doc
    FROM movimientos_contables c
    LEFT JOIN movimientos_contables d ON d.tipo IN ('debito', 'D') AND d.numero_documento = c.numero_documento AND d.movimiento_origen_id IS NULL AND (d.origen_tipo != 'cierre' OR d.origen_tipo IS NULL)
    LEFT JOIN movimientos_contables s ON s.tipo IN ('debito', 'D') AND s.movimiento_origen_id = d.id
    WHERE c.tipo IN ('credito', 'C') AND c.tipo_documento = 'GASTO_DE_ENTREGAS' AND c.origen_tipo = 'gasto'
    ORDER BY CAST(REGEXP_REPLACE(c.numero_documento, '[^0-9]', '', 'g') AS INTEGER) ASC
''')
print("=== CLOSED EXPENSE TRANSACTIONS ===")
for r in cur.fetchall():
    cred = float(r['cred_monto'] or 0)
    deb = float(r['deb_monto'] or 0)
    saldo = float(r['saldo_monto'] or 0)
    tot_deb = deb + saldo
    diff = tot_deb - cred
    print(f"Doc #{r['doc_num']:3s} (comp {r['comp_id']:3d}) -> Cred: {cred:12,.2f} | Cuota1: {deb:10,.2f} (id {r['deb_id']}) | SaldoActivo: {saldo:12,.2f} (id {r['saldo_id']}, comp {r['saldo_comp']}, doc {r['saldo_doc']}) | Diff: {diff:,.2f}")
