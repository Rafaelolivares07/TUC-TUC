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
        SELECT id, comprobante_id, tipo_documento, numero_documento, cuenta, concepto, tipo, monto
        FROM movimientos_contables
        WHERE negocio_id = 59 AND tipo_documento = 'GASTO_DE_ENTREGAS'
        ORDER BY numero_documento, id ASC
    """).fetchall()

    docs = {}
    for r in rows:
        num = str(r['numero_documento'])
        if num not in docs:
            docs[num] = []
        docs[num].append(dict(r._data))

    for num, movs in docs.items():
        print(f"\n--- Documento #{num} ({len(movs)} lineas) ---")
        for m in movs:
            print(f"  ID:{m['id']} | Monto:${float(m['monto']):,.2f} | {m['concepto'][:50]}")

    tdn = conn.execute("SELECT consecutivo FROM tipos_documento_negocio WHERE negocio_id = 59 AND codigo = 'GASTO_DE_ENTREGAS'").fetchone()
    print(f"\nConsecutivo actual de GASTO_DE_ENTREGAS: {tdn['consecutivo']}")
    conn.close()

if __name__ == '__main__':
    main()
