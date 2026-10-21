import os, sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
os.environ['DATABASE_URL'] = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc'

from app.db import init_db, get_db_connection
from app.blueprints.contabilidad import _ejecutar_asiento_produccion

init_db(None)
conn = get_db_connection()

# Check RP 51
for doc_num in ['51']:
    cur = conn.execute("""
        SELECT id FROM movimientos_contables 
        WHERE negocio_id = 59 AND numero_documento = %s 
          AND (tipo_documento ILIKE '%%PRODUC%%' OR tipo_documento ILIKE '%%REPORTE%%')
    """, (doc_num,)).fetchall()
    
    if len(cur) == 0:
        rows = conn.execute("""
            SELECT id, producto_id, tipo, cantidad, valor_total, valor_unitario, documento_fecha, proveedor_id, referencia_id, bodega 
            FROM movimientos_inventario 
            WHERE negocio_id = 59 AND documento_numero = %s AND tipo_documento = 'REPORTE DE PRODUCCION'
        """, (doc_num,)).fetchall()
        
        if rows:
            term_rows = [r for r in rows if r['tipo'] == 'entrada']
            comp_rows = [r for r in rows if r['tipo'] == 'salida']
            
            if term_rows:
                term_row = term_rows[0]
                comps = [{'producto_id': r['producto_id'], 'cantidad': float(r['cantidad']), 'costo_und': float(r['valor_unitario'] or 0)} for r in comp_rows]
                costo_tot = float(sum(float(r['valor_total'] or 0) for r in comp_rows))
                
                prod_info = conn.execute("SELECT nombre FROM productos WHERE id = %s", (term_row['producto_id'],)).fetchone()
                nom = prod_info['nombre'] if prod_info else 'Producto'
                
                comp_id = _ejecutar_asiento_produccion(
                    conn, 59, term_row['producto_id'], costo_tot, comps,
                    registrado_por=58,
                    descripcion=f'Producción: {nom} x{float(term_row["cantidad"])}',
                    origen_tipo='produccion',
                    origen_id=term_row['referencia_id'],
                    tipo_documento='REPORTE DE PRODUCCION',
                    documento_numero=str(doc_num),
                    tipo_documento_id=5,
                    tercero_id=term_row['proveedor_id'] or 58,
                    fecha=term_row['documento_fecha'],
                    centro_utilidad_id=term_row['bodega'] or 1
                )
                conn.commit()
                print(f"Generated comp_id {comp_id} for Reporte de Produccion {doc_num}")
            else:
                print(f"No term_row for doc {doc_num}")
        else:
            print(f"No inv rows for doc {doc_num}")
    else:
        print(f"Doc {doc_num} already has {len(cur)} mc rows")

conn.close()
