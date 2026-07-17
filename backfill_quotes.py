import os
import psycopg2
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

def backfill():
    if not db_url:
        print("DATABASE_URL no está configurada en el entorno.")
        return

    print("Conectando a la base de datos...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor if hasattr(psycopg2, 'extras') else None)
    
    # If standard cursor, we can map manually, or use psycopg2.extras
    # Let's write a standard cursor query to be safe of psycopg2.extras availability
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
        cursor.execute(query)
        # Fetch description to map columns manually
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        print(f"Encontrados {len(rows)} movimientos de compra históricos.")
        
        migrados = 0
        actualizados = 0
        
        for r in rows:
            negocio_id = r['negocio_id']
            proveedor_id = r['proveedor_id']
            producto_id = r['producto_id']
            vu = float(r['valor_unitario'])
            doc_num = r['documento_numero'] or f"ENT-{r['created_at'].strftime('%Y%m%d')}"
            
            # handle date formatting safely
            f_cot = r['documento_fecha']
            if not f_cot:
                f_cot = r['created_at'].date()
            f_vence = f_cot + timedelta(days=180)
            
            # Check if a quote exists
            cursor.execute("""
                SELECT id, fecha_cotizacion FROM cotizaciones_compras
                WHERE negocio_id = %s AND tercero_id = %s AND item_id = %s AND origen = 'compra'
                LIMIT 1
            """, (negocio_id, proveedor_id, producto_id))
            cot_row = cursor.fetchone()
            
            if cot_row:
                cot_id = cot_row[0]
                cot_fecha = cot_row[1]
                # Update only if this purchase is newer or same date
                if f_cot >= cot_fecha:
                    cursor.execute("""
                        UPDATE cotizaciones_compras
                        SET numero_cotizacion = %s, fecha_cotizacion = %s, fecha_vencimiento = %s,
                            precio = %s, unidades_item = 1, validada_proveedor = TRUE, updated_at = NOW()
                        WHERE id = %s
                    """, (doc_num, f_cot, f_vence, vu, cot_id))
                    actualizados += 1
            else:
                cursor.execute("""
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
        cursor.close()
        conn.close()

if __name__ == '__main__':
    backfill()
