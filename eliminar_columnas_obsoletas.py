"""
Script para eliminar columnas obsoletas de CONFIGURACION_PRECIOS
Ejecutar una sola vez para limpiar la base de datos
"""

import sqlite3

DB_NAME = 'medicamentos.db'

def eliminar_columnas_obsoletas():
    """
    SQLite no soporta DROP COLUMN directamente en versiones antiguas.
    Debemos recrear la tabla sin las columnas obsoletas.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print("="*80)
    print("ELIMINACION DE COLUMNAS OBSOLETAS - CONFIGURACION_PRECIOS")
    print("="*80)

    try:
        # 1. Leer los datos actuales
        print("\n[1] Leyendo datos actuales...")
        cursor.execute("SELECT * FROM CONFIGURACION_PRECIOS")
        datos_actuales = cursor.fetchone()

        if not datos_actuales:
            print("    [!] No hay datos en la tabla CONFIGURACION_PRECIOS")
            return

        # Obtener nombres de columnas
        columnas = [description[0] for description in cursor.description]
        print(f"    Columnas actuales: {len(columnas)}")
        print(f"    {columnas}")

        # 2. Crear respaldo temporal
        print("\n[2] Creando respaldo temporal...")
        cursor.execute("""
            CREATE TABLE CONFIGURACION_PRECIOS_BACKUP AS
            SELECT * FROM CONFIGURACION_PRECIOS
        """)
        print("    [OK] Respaldo creado: CONFIGURACION_PRECIOS_BACKUP")

        # 3. Eliminar tabla original
        print("\n[3] Eliminando tabla original...")
        cursor.execute("DROP TABLE CONFIGURACION_PRECIOS")
        print("    [OK] Tabla eliminada")

        # 4. Crear nueva tabla SIN las columnas obsoletas
        print("\n[4] Creando nueva tabla sin columnas obsoletas...")
        cursor.execute("""
            CREATE TABLE CONFIGURACION_PRECIOS (
                id INTEGER PRIMARY KEY,
                descuento_competencia INTEGER NOT NULL DEFAULT 200,
                recargo_escaso INTEGER NOT NULL DEFAULT 30,
                redondeo_superior INTEGER NOT NULL DEFAULT 100,
                ganancia_min_escaso INTEGER NOT NULL DEFAULT 2000,
                ganancia_max_escaso INTEGER NOT NULL DEFAULT 10000,
                base_escaso TEXT NOT NULL DEFAULT 'minimo',
                usar_precio TEXT DEFAULT 'minimo',
                permitir_publicar_sin_cotizaciones INTEGER NOT NULL DEFAULT 0,
                recargo_1_cotizacion INTEGER NOT NULL DEFAULT 30,
                pedido_min_domicilio_gratis INTEGER NOT NULL DEFAULT 50000,
                umbral_brecha_2cot_baja INTEGER NOT NULL DEFAULT 2000,
                umbral_brecha_2cot_alta INTEGER NOT NULL DEFAULT 5000,
                costo_operario_domicilio INTEGER DEFAULT 3333,
                precio_domicilio INTEGER DEFAULT 5000
            )
        """)
        print("    [OK] Nueva tabla creada")
        print("    Columnas eliminadas: umbral_brecha_3cot, umbral_brecha_4cot")

        # 5. Copiar datos (excluyendo columnas obsoletas)
        print("\n[5] Copiando datos a la nueva tabla...")
        cursor.execute("""
            INSERT INTO CONFIGURACION_PRECIOS (
                id, descuento_competencia, recargo_escaso, redondeo_superior,
                ganancia_min_escaso, ganancia_max_escaso, base_escaso, usar_precio,
                permitir_publicar_sin_cotizaciones, recargo_1_cotizacion,
                pedido_min_domicilio_gratis, umbral_brecha_2cot_baja,
                umbral_brecha_2cot_alta, costo_operario_domicilio, precio_domicilio
            )
            SELECT
                id, descuento_competencia, recargo_escaso, redondeo_superior,
                ganancia_min_escaso, ganancia_max_escaso, base_escaso, usar_precio,
                permitir_publicar_sin_cotizaciones, recargo_1_cotizacion,
                pedido_min_domicilio_gratis, umbral_brecha_2cot_baja,
                umbral_brecha_2cot_alta, costo_operario_domicilio, precio_domicilio
            FROM CONFIGURACION_PRECIOS_BACKUP
        """)
        print("    [OK] Datos copiados exitosamente")

        # 6. Verificar nueva estructura
        print("\n[6] Verificando nueva estructura...")
        cursor.execute("PRAGMA table_info(CONFIGURACION_PRECIOS)")
        nuevas_columnas = cursor.fetchall()
        print(f"    Columnas en la nueva tabla: {len(nuevas_columnas)}")
        for col in nuevas_columnas:
            print(f"      - {col[1]} ({col[2]})")

        # 7. Commit
        conn.commit()
        print("\n[OK] Cambios guardados exitosamente")

        # 8. Preguntar si eliminar respaldo
        print("\n[?] Respaldo 'CONFIGURACION_PRECIOS_BACKUP' disponible")
        print("    Para eliminarlo, ejecuta: DROP TABLE CONFIGURACION_PRECIOS_BACKUP")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        conn.rollback()
        print("[!] Cambios revertidos. La tabla original se mantiene intacta.")

        # Intentar restaurar desde backup si existe
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='CONFIGURACION_PRECIOS_BACKUP'")
            if cursor.fetchone():
                print("[!] Intentando restaurar desde respaldo...")
                cursor.execute("DROP TABLE IF EXISTS CONFIGURACION_PRECIOS")
                cursor.execute("ALTER TABLE CONFIGURACION_PRECIOS_BACKUP RENAME TO CONFIGURACION_PRECIOS")
                conn.commit()
                print("[OK] Tabla restaurada desde respaldo")
        except:
            pass

    finally:
        conn.close()

    print("\n" + "="*80)
    print("[OK] PROCESO COMPLETADO")
    print("="*80)

if __name__ == '__main__':
    eliminar_columnas_obsoletas()
