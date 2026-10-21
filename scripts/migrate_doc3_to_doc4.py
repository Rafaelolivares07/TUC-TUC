import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
import main
from app.db import get_db_connection

def run():
    conn = get_db_connection()
    # 1. Update unliquidated lines from doc 3 to doc 4
    conn.execute("""
        UPDATE movimientos_contables
        SET numero_documento = '4'
        WHERE tipo_documento = 'GASTO_DE_ENTREGAS' 
          AND numero_documento = '3' 
          AND id NOT IN (3671, 4889, 4890)
    """)
    conn.commit()

    # 2. Verify
    doc3 = conn.execute("SELECT count(*), sum(monto) FROM movimientos_contables WHERE tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = '3'").fetchone()
    doc4 = conn.execute("SELECT count(*), sum(monto) FROM movimientos_contables WHERE tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = '4'").fetchone()

    print(f"Doc 3 (Liquidado individual): lineas={doc3[0]}, sum={doc3[1]}")
    print(f"Doc 4 (Relacion Activa Abierta): lineas={doc4[0]}, sum={doc4[1]}")

if __name__ == '__main__':
    run()
