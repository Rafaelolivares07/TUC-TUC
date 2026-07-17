import os
from datetime import timedelta, datetime
from decimal import Decimal
from app.db import get_db_connection

def backfill():
    conn = get_db_connection()
    try:
        # Fetch all purchase movements with valid provider and price
        query = """
            SELECT id, negocio_id, producto_id, cantidad, valor_unitario, created_at,
                   documento_numero, documento_fecha, proveedor_id
            FROM movimientos_inventario
            WHERE tipo = 'entrada' AND motivo = 'compra'
              AND proveedor_id IS NOT NULL
              AND valor_unitario IS NOT NULL AND valor_unitario > 0
            ORDER BY created_at ASC
        """
        rows = conn.execute(query).fetchall()
        print(f"Encontrados {len(rows)} movimientos de compra históricos.")
        
        migrados = 0
        actualizados = 0
        
        for r in rows:
            negocio_id = r['negocio_id']
            proveedor_id = r['proveedor_id']
            producto_id = r['producto_id']
            vu = float(r['valor_unitario'])
            doc_num = r['documento_numero'] or f"ENT-{r['created_at'].strftime('%Y%m%d')}"
            f_cot = r['documento_fecha'] or r['created_at'].date()
            f_vence = f_cot + timedelta(days=180)
            
            # Check if a quote exists
            cot = conn.execute("""
                SELECT id, fecha_cotizacion FROM cotizaciones_compras
                WHERE negocio_id = %s AND tercero_id = %s AND item_id = %s AND origen = 'compra'
                LIMIT 1
            """, (negocio_id, proveedor_id, producto_id)).fetchone()
            
            if cot:
                # Update only if this purchase is newer or same date
                if f_cot >= cot['fecha_cotizacion']:
                    conn.execute("""
                        UPDATE cotizaciones_compras
                        SET numero_cotizacion = %s, fecha_cotizacion = %s, fecha_vencimiento = %s,
                            precio = %s, unidades_item = 1, validada_proveedor = TRUE, updated_at = NOW()
                        WHERE id = %s
                    """, (doc_num, f_cot, f_vence, vu, cot['id']))
                    actualizados += 1
            else:
                conn.execute("""
                    INSERT INTO cotizaciones_compras
                        (negocio_id, numero_cotizacion, tercero_id, item_id, fecha_cotizacion,
                         fecha_vencimiento, descripcion_presentacion, unidades_item, precio,
                         origen, validada_proveedor, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, 'compra', TRUE, NOW())
                """, (negocio_id, doc_num, proveedor_id, producto_id, f_cot, f_vence, 'Unidad (entrada)', vu))
                migrados += 1
                
        conn.commit()
        print(f"Migración completada exitosamente: {migrados} cotizaciones creadas, {actualizados} actualizadas.")
    except Exception as e:
        conn.rollback()
        print(f"Error durante la migración: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    # Set the working dir context if needed
    backfill()
