import sys
import os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.db import get_db_connection, init_db

class DummyApp: pass
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
init_db(DummyApp())

def main():
    conn = get_db_connection()

    # 1. Update lines 4887 and 4888 to full original amounts and clean concepts
    conn.execute("""
        UPDATE movimientos_contables
        SET monto = 950000.00,
            concepto = 'ADECUACIONES LOCAL (Saldo pendiente mueble exhibidor)',
            cuenta = '614304',
            meses_duracion = 12,
            modalidad_amortizacion = 'prorrateo'
        WHERE id = 4887
    """)

    conn.execute("""
        UPDATE movimientos_contables
        SET monto = 42500.00,
            concepto = 'ADECUACIONES LOCAL (Lapiz, nivelador, cinta enmascarar David)',
            cuenta = '614305',
            meses_duracion = 12,
            modalidad_amortizacion = 'prorrateo'
        WHERE id = 4888
    """)

    # 2. Remove test programaciones 6 and 7 (they belong to when it actually gets liquidated)
    conn.execute("DELETE FROM programaciones_contables WHERE id IN (6, 7)")

    conn.commit()

    # 3. Print verified summary of all 24 lines
    rows = conn.execute("""
        SELECT m.id, m.cuenta, cp.nombre as cta_nombre, m.concepto, m.monto, m.meses_duracion, 
               m.modalidad_amortizacion, m.cuota_1_monto, t.nombre as tercero_nombre
        FROM movimientos_contables m
        LEFT JOIN cuentas_puc cp ON m.cuenta_id = cp.id
        LEFT JOIN terceros t ON m.tercero_id = t.id
        WHERE m.negocio_id = 59 AND m.tipo_documento = 'GASTO_DE_ENTREGAS' AND m.numero_documento = '5'
        ORDER BY m.id ASC
    """).fetchall()

    print(f"Total líneas en Relación #5: {len(rows)}")
    total_monto = 0.0
    for idx, r in enumerate(rows, 1):
        m = float(r['monto'])
        total_monto += m
        tipo_str = "Gasto (1m)" if r['meses_duracion'] == 1 else f"Activo/Diferido ({r['meses_duracion']} meses)"
        tercero = r['tercero_nombre'] or 'Sin tercero'
        conc = r['concepto'].replace('\n', ' ')
        print(f"{idx:2d}. [ID {r['id']}] {r['cuenta']} | ${m:,.2f} | {tipo_str} | Tercero: {tercero} | {conc}")
    print(f"\nTOTAL RELACIÓN #5: ${total_monto:,.2f}")

    conn.close()

if __name__ == '__main__':
    main()
