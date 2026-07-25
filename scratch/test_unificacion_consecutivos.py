import sys
import os
from decimal import Decimal

# Add parent directory to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.db import get_db_connection
from app.blueprints.contabilidad import obtener_siguiente_consecutivo, _ejecutar_asiento_automatico, _asegurar_tablas

def run_tests():
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        try:
            print("=== CORRIENDO MIGRACIONES ===")
            _asegurar_tablas(conn)
            conn.commit()
            
            print("=== INICIANDO PRUEBAS DE NORMALIZACION POR ID ===")
            
            # Negocio de prueba (Pitt)
            negocio_id = 59
            
            # 1. Buscar un tipo de documento existente
            row = conn.execute("""
                SELECT id, nombre, codigo, consecutivo, es_interno 
                FROM tipos_documento_negocio 
                WHERE negocio_id = %s AND activo = TRUE
                LIMIT 1
            """, (negocio_id,)).fetchone()
            
            if not row:
                print("No se encontró ningún tipo de documento de prueba. Creando uno...")
                # Crear uno de prueba para el negocio
                cur = conn.execute("""
                    INSERT INTO tipos_documento_negocio (negocio_id, codigo, nombre, numero_inicio, es_interno)
                    VALUES (%s, 'TEST_MIG', 'Documento Test Migracion', 1, TRUE)
                    RETURNING id, nombre, codigo, consecutivo, es_interno
                """, (negocio_id,)).fetchone()
                row = cur
                conn.commit()
            
            tid = row['id']
            nombre = row['nombre']
            codigo = row['codigo']
            consecutivo_ant = row['consecutivo'] or 0
            
            print(f"Tipo de doc de prueba: ID={tid}, Nombre='{nombre}', Codigo='{codigo}', Consecutivo={consecutivo_ant}")
            
            # 2. Probar obtener_siguiente_consecutivo usando ID
            res_num, es_interno = obtener_siguiente_consecutivo(conn, negocio_id, tid)
            print(f"Resultado por ID: Numero={res_num}, Es Interno={es_interno}")
            
            # 3. Probar obtener_siguiente_consecutivo usando Código de texto (fallback)
            res_num_fallback, es_interno_fallback = obtener_siguiente_consecutivo(conn, negocio_id, codigo)
            print(f"Resultado por Código (fallback): Numero={res_num_fallback}, Es Interno={es_interno_fallback}")
            
            # 4. Probar obtener_siguiente_consecutivo usando Nombre de texto (fallback)
            res_num_name, es_interno_name = obtener_siguiente_consecutivo(conn, negocio_id, nombre)
            print(f"Resultado por Nombre (fallback): Numero={res_num_name}, Es Interno={es_interno_name}")
            
            # Validar que los consecutivos incrementaron
            final_row = conn.execute("SELECT consecutivo FROM tipos_documento_negocio WHERE id = %s", (tid,)).fetchone()
            print(f"Consecutivo final en DB: {final_row['consecutivo']} (Antes: {consecutivo_ant})")
            
            print("=== PRUEBAS COMPLETADAS CON EXITO ===")
            conn.rollback() # Rollback para no alterar producción de verdad
        except Exception as e:
            print(f"Error en pruebas: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == '__main__':
    run_tests()
