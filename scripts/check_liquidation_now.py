import sys
import os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.db import get_db_connection, init_db

class DummyApp: pass
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
init_db(DummyApp())

def main():
    conn = get_db_connection()
    print("=== RECENT MOVEMENTS ===")
    rows = conn.execute("""
        SELECT m.id, m.comprobante_id, m.tipo_documento, m.numero_documento, m.cuenta, 
               m.concepto, m.tipo, m.monto, m.fecha, m.created_at, m.movimiento_origen_id, m.origen_tipo
        FROM movimientos_contables m
        WHERE m.negocio_id = 59
        ORDER BY m.id DESC LIMIT 25
    """).fetchall()
    for r in rows:
        print(f"ID:{r['id']} | Comp:{r['comprobante_id']} | Doc:{r['tipo_documento']}-{r['numero_documento']} | Cta:{r['cuenta']} | Tipo:{r['tipo']} | Monto:{float(r['monto']):,.2f} | OrigID:{r['movimiento_origen_id']} | Concepto:{r['concepto']}")

    print("\n=== RECENT COMPROBANTES ===")
    comps = conn.execute("""
        SELECT id, tipo_documento_id, fecha, concepto, total_debito, total_credito, cuadrado, estado, created_at
        FROM comprobantes_contables
        WHERE negocio_id = 59
        ORDER BY id DESC LIMIT 10
    """).fetchall()
    for c in comps:
        print(dict(c._data))

    conn.close()

if __name__ == '__main__':
    main()
