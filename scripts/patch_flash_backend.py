import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Update app/blueprints/tiendas.py with the validation endpoint
with open('app/blueprints/tiendas.py', 'r', encoding='utf-8') as f:
    py_code = f.read()

endpoint_code = """
@bp.route('/api/caja/<slug>/validar-factura-flash', methods=['POST'])
@bp.route('/api/tienda/<slug>/caja/validar-factura-flash', methods=['POST'])
def api_caja_validar_factura_flash(slug):
    conn = get_db_connection()
    try:
        negocio = _obtener_negocio_por_slug(conn, slug)
        if not negocio:
            return jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404
        data = request.get_json() or {}
        pedido_id = data.get('pedido_id')
        num_doc = data.get('numero_documento')
        resultado = (data.get('resultado') or 'ok').lower()
        items_resumen = data.get('items_resumen', '')
        total = float(data.get('total') or 0)
        cajero = data.get('cajero') or session.get('nombre') or 'Caja'
        
        rest_id = negocio['id'] if negocio['tipo_negocio'] != 'tienda' else None
        tienda_id = negocio['id'] if negocio['tipo_negocio'] == 'tienda' else None
        
        conn.execute(\"\"\"
            INSERT INTO pedido_validaciones_flash 
            (pedido_id, numero_documento, restaurante_id, tienda_id, cajero, resultado, items_resumen, total)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        \"\"\", (pedido_id, num_doc, rest_id, tienda_id, cajero, resultado, items_resumen, total))
        conn.commit()
        return jsonify({'ok': True, 'resultado': resultado})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
"""

marker = "@bp.route('/api/caja/<slug>/facturas-guardadas')"
if marker in py_code and "def api_caja_validar_factura_flash" not in py_code:
    py_code = py_code.replace(marker, endpoint_code + "\n" + marker, 1)
    with open('app/blueprints/tiendas.py', 'w', encoding='utf-8') as f:
        f.write(py_code)
    print("Backend validation endpoint added to tiendas.py")
else:
    print("Backend endpoint already present or marker not found")
