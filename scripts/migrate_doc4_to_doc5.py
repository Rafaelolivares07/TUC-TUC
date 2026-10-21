import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
import main
from app.db import get_db_connection

def run():
    conn = get_db_connection()
    # Move unliquidated lines from doc 4 to doc 5
    conn.execute("""
        UPDATE movimientos_contables
        SET numero_documento = '5'
        WHERE tipo_documento = 'GASTO_DE_ENTREGAS' 
          AND numero_documento = '4' 
          AND id NOT IN (3672, 4893, 4894)
    """)
    conn.commit()

    doc4 = conn.execute("SELECT count(*), sum(monto) FROM movimientos_contables WHERE tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = '4'").fetchone()
    doc5 = conn.execute("SELECT count(*), sum(monto) FROM movimientos_contables WHERE tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = '5'").fetchone()

    print(f"Doc 4 (Liquidado individual mesa toppineras): lineas={doc4[0]}, sum={doc4[1]}")
    print(f"Doc 5 (Relacion Activa Abierta): lineas={doc5[0]}, sum={doc5[1]}")

if __name__ == '__main__':
    run()
