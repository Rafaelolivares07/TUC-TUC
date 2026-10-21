import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
import os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')

from app import create_app
from app.blueprints.inventarios import api_compras_sugerencias
from flask import session

app = create_app()

with app.test_request_context('/api/inventario/59/compras/sugerencias'):
    session['usuario_id'] = 1
    session['negocio_id'] = 59
    resp = api_compras_sugerencias(59)
    data = resp.get_json() if hasattr(resp, 'get_json') else resp[0].get_json()
    print("Status:", data.get('ok'), "Error:", data.get('error'))
    provs = data.get('proveedores', [])
    print(f"Total proveedores en sugerencias: {len(provs)}")
    encontrado_pan = False
    for p in provs:
        print(f"\nProveedor: '{p['proveedor_nombre']}' (ID: {p['proveedor_id']}) - Total: ${p['total_compras']:,.2f}")
        for prod in p['productos']:
            print(f"   - {prod['producto_nombre']}: Sugerido={prod['cantidad_sugerida_unidades']} | Stock={prod['stock_actual']} | DDP={prod['demanda_diaria']} | DiasMax={prod['dias_max_stock_aplicado']}")
            if 'PAN' in prod['producto_nombre'].upper():
                encontrado_pan = True
                print(f"     *** AQUÍ ESTÁ EL PAN! ***")

    if not encontrado_pan:
        print("\nPAN TIPO ARABE PERMAN NO APARECE EN NINGÚN PROVEEDOR DE SUGERENCIAS!")

    print("\nAlertas activas en sugerencias:")
    for a in data.get('alertas_activas', []):
        print(f"  * {a['nombre']} (ID: {a['producto_id']}) - Stock: {a['stock_actual']} - Min: {a['stock_minimo']} - EsProd: {a['es_produccion']}")
