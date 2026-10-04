import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app
from app.blueprints.contabilidad import api_contabilidad_config_metodos
from app.db import get_db_connection

with app.test_request_context('/api/contabilidad/59/config-metodos'):
    from flask import session
    session['usuario_id'] = 1
    resp = api_contabilidad_config_metodos(59)
    print("Response status:", resp.status_code if hasattr(resp, 'status_code') else 'OK')
    if hasattr(resp, 'get_json'):
        data = resp.get_json()
        print("Metodos returned:", len(data.get('metodos', [])))
        for m in data.get('metodos', []):
            print(f" - {m['icono']} {m['nombre']} ({m['codigo']}): cuenta_id={m['cuenta_id']}, cta={m['cuenta_codigo']} - {m['cuenta_nombre']}, ventas={m['activo_ventas']}, desembolsos={m['activo_desembolsos']}")

with app.app_context():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM parametros_metodos_pago_negocio WHERE negocio_id = 59 ORDER BY orden, id").fetchall()
        print("\nTotal rows in DB now:", len(rows))
        for r in rows:
            print(dict(r))
    finally:
        conn.close()
