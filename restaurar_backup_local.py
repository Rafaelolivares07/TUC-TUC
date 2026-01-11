"""
Script para restaurar el backup JSON a PostgreSQL local

REQUISITOS:
1. PostgreSQL instalado localmente
2. Base de datos creada (ej: tuctuc_local)
3. psycopg2 instalado: pip install psycopg2

USO:
    python restaurar_backup_local.py

CONFIGURACIÓN:
    Edita las variables de conexión abajo con tus credenciales locales
"""

import json
import psycopg2
from psycopg2 import sql
import sys
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================
# CONFIGURACIÓN DE CONEXIÓN LOCAL
# ============================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'tuctuc_local',  # Cambia este nombre si usas otro
    'user': 'postgres',           # Usuario por defecto de PostgreSQL
    'password': 'grandesventas99' # La contraseña que pusiste en la instalación
}

BACKUP_FILE = 'backups/backup_tuctuc_20260109_081920.json'

# ============================================
# FUNCIONES
# ============================================

def conectar():
    """Conectar a PostgreSQL local"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"✅ Conectado a PostgreSQL local: {DB_CONFIG['database']}")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        print("\nVerifica:")
        print("  1. PostgreSQL está corriendo")
        print("  2. La base de datos existe")
        print("  3. Usuario y contraseña son correctos")
        sys.exit(1)


def crear_tabla(conn, nombre_tabla, columnas):
    """Crear tabla con las columnas del backup"""
    cursor = conn.cursor()

    # Mapeo de tipos de Python a PostgreSQL
    def inferir_tipo(valores):
        """Inferir tipo PostgreSQL basado en valores de ejemplo"""
        for valor in valores:
            if valor is not None:
                if isinstance(valor, bool):
                    return 'BOOLEAN'
                elif isinstance(valor, int):
                    return 'INTEGER'
                elif isinstance(valor, float):
                    return 'NUMERIC'
                elif isinstance(valor, str):
                    # Detectar timestamps
                    if 'fecha' in nombre_tabla.lower() or 'timestamp' in nombre_tabla.lower():
                        try:
                            datetime.fromisoformat(valor.replace('Z', '+00:00'))
                            return 'TIMESTAMP'
                        except:
                            pass
                    return 'TEXT'
        return 'TEXT'  # Default

    try:
        # Crear definición de columnas
        columnas_sql = []
        for col in columnas:
            tipo = 'TEXT'  # Por simplicidad, usamos TEXT para todo
            columnas_sql.append(f'"{col}" {tipo}')

        # Crear tabla
        create_sql = f'CREATE TABLE IF NOT EXISTS "{nombre_tabla}" ({", ".join(columnas_sql)})'
        cursor.execute(create_sql)
        conn.commit()
        print(f"  ✅ Tabla '{nombre_tabla}' creada")

    except Exception as e:
        print(f"  ❌ Error creando tabla '{nombre_tabla}': {e}")
        conn.rollback()
    finally:
        cursor.close()


def insertar_datos(conn, nombre_tabla, columnas, filas):
    """Insertar datos en la tabla"""
    if not filas:
        print(f"  ⚠️ Tabla '{nombre_tabla}' sin datos, omitiendo...")
        return

    cursor = conn.cursor()

    try:
        # Preparar INSERT
        cols = ', '.join([f'"{col}"' for col in columnas])
        placeholders = ', '.join(['%s'] * len(columnas))
        insert_sql = f'INSERT INTO "{nombre_tabla}" ({cols}) VALUES ({placeholders})'

        # Insertar filas
        for fila in filas:
            valores = [fila.get(col) for col in columnas]
            cursor.execute(insert_sql, valores)

        conn.commit()
        print(f"  ✅ {len(filas)} registros insertados en '{nombre_tabla}'")

    except Exception as e:
        print(f"  ❌ Error insertando datos en '{nombre_tabla}': {e}")
        conn.rollback()
    finally:
        cursor.close()


def restaurar_backup():
    """Proceso principal de restauración"""
    print("=" * 60)
    print("RESTAURACIÓN DE BACKUP A POSTGRESQL LOCAL")
    print("=" * 60)
    print()

    # Cargar backup JSON
    print(f"📂 Cargando backup: {BACKUP_FILE}")
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        print(f"✅ Backup cargado: {len(backup_data)} tablas encontradas")
    except Exception as e:
        print(f"❌ Error cargando backup: {e}")
        sys.exit(1)

    print()

    # Conectar a PostgreSQL
    conn = conectar()
    print()

    # Restaurar cada tabla
    print("🔄 Restaurando tablas...")
    print()

    total_registros = 0
    for nombre_tabla, info_tabla in backup_data.items():
        print(f"📋 Procesando tabla: {nombre_tabla}")

        columnas = info_tabla['columns']
        filas = info_tabla['rows']

        # Crear tabla
        crear_tabla(conn, nombre_tabla, columnas)

        # Insertar datos
        insertar_datos(conn, nombre_tabla, columnas, filas)

        total_registros += len(filas)
        print()

    conn.close()

    print("=" * 60)
    print(f"✅ RESTAURACIÓN COMPLETADA")
    print(f"   Total tablas: {len(backup_data)}")
    print(f"   Total registros: {total_registros}")
    print("=" * 60)


# ============================================
# EJECUCIÓN
# ============================================

if __name__ == '__main__':
    print()
    print("⚠️  IMPORTANTE: Antes de ejecutar, verifica que:")
    print("   1. PostgreSQL está instalado y corriendo")
    print("   2. Has creado la base de datos 'tuctuc_local'")
    print("   3. Has configurado las credenciales en este script")
    print()
    print("▶️  Iniciando restauración...")
    print()
    restaurar_backup()
