import sys
import os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.db import get_db_connection, init_db

class DummyApp: pass
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
init_db(DummyApp())

def main():
    conn = get_db_connection()

    # 1. Move all 24 lines to Document #5 and Comprobante 686
    conn.execute("""
        UPDATE movimientos_contables
        SET numero_documento = '5',
            comprobante_id = 686
        WHERE negocio_id = 59 
          AND tipo_documento = 'GASTO_DE_ENTREGAS' 
          AND id IN (
              3671, 3672, 3731, 3732, 3733, 3734, 3735, 3738, 
              3956, 3958, 3959, 3960, 3961, 3962, 3963, 4214, 
              4215, 4216, 4217, 4218, 4416, 4476, 4887, 4888
          )
    """)

    # 2. Reset consecutivo to 4 so open relation is #5
    conn.execute("""
        UPDATE tipos_documento_negocio
        SET consecutivo = 4
        WHERE negocio_id = 59 AND codigo = 'GASTO_DE_ENTREGAS'
    """)

    # 3. Clean any stray movements/comprobantes for GASTO_DE_ENTREGAS that are not the 24 open lines or closed docs 1 and 2
    conn.execute("""
        DELETE FROM movimientos_contables
        WHERE negocio_id = 59 
          AND tipo_documento = 'GASTO_DE_ENTREGAS'
          AND id NOT IN (
              2904, 4954, 2906, 2907, 2908, 4955,
              3671, 3672, 3731, 3732, 3733, 3734, 3735, 3738, 
              3956, 3958, 3959, 3960, 3961, 3962, 3963, 4214, 
              4215, 4216, 4217, 4218, 4416, 4476, 4887, 4888
          )
    """)

    conn.execute("DELETE FROM comprobantes_contables WHERE id IN (687, 688)")
    conn.execute("DELETE FROM programaciones_contables WHERE negocio_id = 59 AND tipo_doc_id = 7")

    conn.commit()

    # 4. Verification
    rows = conn.execute("""
        SELECT id, comprobante_id, tipo_documento, numero_documento, cuenta, concepto, tipo, monto, meses_duracion
        FROM movimientos_contables
        WHERE negocio_id = 59 AND tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = '5'
        ORDER BY id ASC
    """).fetchall()

    print(f"=== VERIFICACIÓN: Relación #5 contiene {len(rows)} líneas ===")
    total_monto = 0.0
    for r in rows:
        total_monto += float(r['monto'])
        conc = r['concepto'].replace('\n', ' ')
        print(f"  ID:{r['id']} | Cta:{r['cuenta']} | Monto:${float(r['monto']):,.2f} | Meses:{r['meses_duracion']} | {conc[:50]}")
    print(f"\nTOTAL RELACIÓN #5: ${total_monto:,.2f}")

    tdn = conn.execute("SELECT consecutivo FROM tipos_documento_negocio WHERE negocio_id = 59 AND codigo = 'GASTO_DE_ENTREGAS'").fetchone()
    print(f"Consecutivo actual: {tdn['consecutivo']} (Documento activo abierto: #{tdn['consecutivo'] + 1})")

    conn.close()

if __name__ == '__main__':
    main()
