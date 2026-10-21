import sys
import os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.db import get_db_connection, init_db

class DummyApp: pass
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
init_db(DummyApp())

def main():
    conn = get_db_connection()

    # 1. Revert line 3671 to 1,677,000 full amount
    conn.execute("""
        UPDATE movimientos_contables
        SET monto = 1677000.00,
            cuota_numero = 1,
            cuota_total = 12,
            metodo_desembolso = null
        WHERE id = 3671
    """)

    # 2. Delete partial closure lines and amortization 5-1
    conn.execute("DELETE FROM movimientos_contables WHERE id IN (4956, 4957, 4958, 4959)")
    conn.execute("DELETE FROM comprobantes_contables WHERE id = 688")
    conn.execute("DELETE FROM programaciones_contables WHERE negocio_id = 59 AND variables_h->>'movimiento_origen_id' = '3671'")

    conn.commit()

    print("\n=== AFTER CLEANUP (Relacion #5) ===")
    rows = conn.execute("""
        SELECT id, comprobante_id, tipo_documento, numero_documento, cuenta, concepto, tipo, monto
        FROM movimientos_contables
        WHERE negocio_id = 59 AND tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = '5'
        ORDER BY id ASC
    """).fetchall()
    total_monto = 0.0
    for r in rows:
        total_monto += float(r['monto'])
        conc = r['concepto'].replace('\n', ' ')
        print(f"ID:{r['id']} | Cta:{r['cuenta']} | Monto:${float(r['monto']):,.2f} | {conc[:50]}")
    print(f"Total Relacion 5: ${total_monto:,.2f} ({len(rows)} lineas)")

    conn.close()

if __name__ == '__main__':
    main()
