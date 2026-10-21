import sys
import os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.db import get_db_connection, init_db

class DummyApp: pass
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
init_db(DummyApp())

def main():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, tipo_documento, numero_documento, cuenta, concepto, monto, tipo, meses_duracion, modalidad_amortizacion, cuota_1_monto, origen_tipo, comprobante_id
        FROM movimientos_contables
        WHERE id IN (4887, 4888, 4477, 4738) OR concepto ILIKE '%%mueble exhibidor%%' OR concepto ILIKE '%%Lapiz%%'
        ORDER BY id ASC
    """).fetchall()
    for r in rows:
        print(dict(r._data))

    print("\n--- PROGRAMACIONES 6 y 7 ---")
    progs = conn.execute("SELECT * FROM programaciones_contables WHERE id IN (6, 7)").fetchall()
    for p in progs:
        print(dict(p._data))
    conn.close()

if __name__ == '__main__':
    main()
