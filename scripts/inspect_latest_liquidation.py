import sys
import os
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.db import get_db_connection, init_db

class DummyApp: pass
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
init_db(DummyApp())

import json
from decimal import Decimal
from datetime import date, datetime

def default_json(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def main():
    conn = get_db_connection()

    print('=== ULTIMOS 30 MOVIMIENTOS CONTABLES (negocio_id = 59) ===')
    rows = conn.execute("""
        SELECT m.id, m.comprobante_id, m.tipo_documento, m.numero_documento, m.cuenta, cp.nombre as cta_nombre,
               m.concepto, m.tipo, m.monto, m.fecha, m.metodo_desembolso, m.meses_duracion, m.cuota_numero, m.cuota_total, m.created_at
        FROM movimientos_contables m
        LEFT JOIN cuentas_puc cp ON m.cuenta_id = cp.id
        WHERE m.negocio_id = 59
        ORDER BY m.id DESC LIMIT 30
    """).fetchall()
    for r in rows:
        print(json.dumps(dict(r._data), default=default_json))

    print('\n=== ULTIMOS 10 COMPROBANTES CONTABLES (negocio_id = 59) ===')
    rows = conn.execute("""
        SELECT *
        FROM comprobantes_contables
        WHERE negocio_id = 59
        ORDER BY id DESC LIMIT 10
    """).fetchall()
    for r in rows:
        print(json.dumps(dict(r._data), default=default_json))

    print('\n=== ULTIMAS PROGRAMACIONES CONTABLES ===')
    rows = conn.execute("""
        SELECT *
        FROM programaciones_contables
        WHERE negocio_id = 59
        ORDER BY id DESC LIMIT 10
    """).fetchall()
    for r in rows:
        print(json.dumps(dict(r._data), default=default_json))

    conn.close()

if __name__ == '__main__':
    main()
