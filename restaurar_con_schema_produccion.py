"""
Script para restaurar backup usando el SCHEMA REAL de producción

ESTRATEGIA:
1. Conectar a PostgreSQL de PRODUCCIÓN (Render)
2. Extraer el schema completo de cada tabla (CREATE TABLE statements)
3. Conectar a PostgreSQL LOCAL
4. Crear tablas con el schema exacto de producción
5. Insertar datos del backup JSON

VENTAJAS:
- Tipos de datos exactos (no hay que inferir nada)
- Constraints correctos (PRIMARY KEY, FOREIGN KEY, etc.)
- Indices copiados
- 100% compatible con producción

REQUISITOS:
1. PostgreSQL instalado localmente
2. Base de datos creada (ej: tuctuc_local)
3. psycopg2 instalado: pip install psycopg2
4. Archivo .env.local con DATABASE_URL de producción

USO:
    python restaurar_con_schema_produccion.py
"""

import json
import psycopg2
from psycopg2 import sql
import sys
import os
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Cargar variables de entorno
load_dotenv('.env.local')

# ============================================
# CONFIGURACIÓN
# ============================================

# Base de datos LOCAL (donde vamos a restaurar)
DB_LOCAL = {
    'host': 'localhost',
    'port': 5432,
    'database': 'tuctuc_local',
    'user': 'postgres',
    'password': 'grandesventas99'
}

# Base de datos PRODUCCIÓN (de donde sacaremos el schema)
DATABASE_URL_PROD = os.getenv('DATABASE_URL')

BACKUP_FILE = 'backups/backup_tuctuc_20260109_081920.json'

# ============================================
# FUNCIONES
# ============================================

def conectar_produccion():
    """Conectar a PostgreSQL de producción (Render)"""
    try:
        conn = psycopg2.connect(DATABASE_URL_PROD)
        print(f"[OK] Conectado a PostgreSQL PRODUCCION (Render)")
        return conn
    except Exception as e:
        print(f"[ERROR] Error conectando a produccion: {e}")
        sys.exit(1)


def conectar_local():
    """Conectar a PostgreSQL local"""
    try:
        conn = psycopg2.connect(**DB_LOCAL)
        print(f"[OK] Conectado a PostgreSQL LOCAL: {DB_LOCAL['database']}")
        return conn
    except Exception as e:
        print(f"[ERROR] Error conectando a local: {e}")
        print("\nVerifica:")
        print("  1. PostgreSQL esta corriendo")
        print("  2. La base de datos existe")
        print("  3. Usuario y contrasena son correctos")
        sys.exit(1)


def obtener_schema_tabla(conn_prod, nombre_tabla):
    """
    Obtiene el CREATE TABLE statement de una tabla desde producción.

    Estrategia:
    1. Consultar pg_catalog para obtener definición completa de columnas
    2. Incluir tipos, constraints, defaults, etc.
    """
    cursor = conn_prod.cursor()

    try:
        # Obtener información de columnas
        cursor.execute("""
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                column_default,
                is_nullable,
                udt_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (nombre_tabla,))

        columnas = cursor.fetchall()

        if not columnas:
            print(f"  [WARN] Tabla '{nombre_tabla}' no existe en produccion")
            return None

        # Obtener información de constraints (PRIMARY KEY, etc.)
        cursor.execute("""
            SELECT
                kcu.column_name,
                tc.constraint_type
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_name = kcu.table_name
            WHERE tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
        """, (nombre_tabla,))

        primary_keys = {row[0] for row in cursor.fetchall()}

        # Construir CREATE TABLE
        columnas_sql = []
        for col in columnas:
            col_name, data_type, max_length, default, nullable, udt_name = col

            # Tipo de dato
            if data_type == 'character varying':
                tipo = f'VARCHAR({max_length})' if max_length else 'TEXT'
            elif data_type == 'USER-DEFINED':
                tipo = udt_name
            elif data_type == 'timestamp without time zone':
                tipo = 'TIMESTAMP'
            elif data_type == 'integer':
                tipo = 'INTEGER'
            elif data_type == 'boolean':
                tipo = 'BOOLEAN'
            elif data_type == 'numeric':
                tipo = 'NUMERIC'
            elif data_type == 'text':
                tipo = 'TEXT'
            elif data_type == 'bigint':
                tipo = 'BIGINT'
            elif data_type == 'double precision':
                tipo = 'DOUBLE PRECISION'
            else:
                tipo = data_type.upper()

            # Constraint
            constraints = []
            if col_name in primary_keys:
                constraints.append('PRIMARY KEY')
            if nullable == 'NO' and col_name not in primary_keys:
                constraints.append('NOT NULL')
            if default and 'nextval' not in default:
                constraints.append(f'DEFAULT {default}')

            col_def = f'"{col_name}" {tipo}'
            if constraints:
                col_def += ' ' + ' '.join(constraints)

            columnas_sql.append(col_def)

        create_sql = f'CREATE TABLE "{nombre_tabla}" ({", ".join(columnas_sql)})'

        return create_sql

    except Exception as e:
        print(f"  [ERROR] Error obteniendo schema de '{nombre_tabla}': {e}")
        return None
    finally:
        cursor.close()


def drop_tabla(conn_local, nombre_tabla):
    """Eliminar tabla si existe en local"""
    cursor = conn_local.cursor()
    try:
        cursor.execute(f'DROP TABLE IF EXISTS "{nombre_tabla}" CASCADE')
        conn_local.commit()
        print(f"  [DROP] Tabla antigua '{nombre_tabla}' eliminada")
    except Exception as e:
        print(f"  [WARN] No se pudo eliminar '{nombre_tabla}': {e}")
        conn_local.rollback()
    finally:
        cursor.close()


def crear_tabla_desde_schema(conn_local, nombre_tabla, create_sql):
    """Crear tabla en local usando el CREATE TABLE de producción"""
    cursor = conn_local.cursor()
    try:
        cursor.execute(create_sql)
        conn_local.commit()
        print(f"  [CREATE] Tabla '{nombre_tabla}' creada con schema de produccion")
    except Exception as e:
        print(f"  [ERROR] Error creando '{nombre_tabla}': {e}")
        print(f"    SQL: {create_sql}")
        conn_local.rollback()
        raise
    finally:
        cursor.close()


def obtener_tipos_columnas(conn_local, nombre_tabla):
    """Obtiene los tipos de datos de cada columna de la tabla"""
    cursor = conn_local.cursor()
    try:
        cursor.execute("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (nombre_tabla,))

        tipos = {}
        for col_name, data_type, udt_name in cursor.fetchall():
            if data_type == 'boolean':
                tipos[col_name] = 'boolean'
            elif data_type == 'bigint':
                tipos[col_name] = 'bigint'
            else:
                tipos[col_name] = data_type

        return tipos
    finally:
        cursor.close()


def convertir_valor(valor, tipo_columna):
    """Convierte un valor del backup al tipo correcto de PostgreSQL"""
    if valor is None:
        return None

    # BOOLEAN: 1/0 -> True/False
    if tipo_columna == 'boolean':
        if isinstance(valor, bool):
            return valor
        elif valor in [1, '1', 'true', 'True', 't', 'T']:
            return True
        elif valor in [0, '0', 'false', 'False', 'f', 'F']:
            return False
        else:
            return bool(valor)

    # INTEGER: verificar que no exceda el rango, sino convertir a None o string
    elif tipo_columna == 'integer':
        if valor == '':
            return None
        try:
            valor_int = int(valor)
            # Si excede el rango de INTEGER de PostgreSQL, retornar None
            if valor_int > 2147483647 or valor_int < -2147483648:
                return None  # O podrías retornar el string para debuggear
            return valor_int
        except (ValueError, TypeError):
            return None

    # BIGINT: convertir strings numéricos grandes
    elif tipo_columna == 'bigint':
        if valor == '':
            return None
        try:
            return int(valor)
        except (ValueError, TypeError):
            return None

    # Por defecto, retornar el valor sin modificar
    return valor


def insertar_datos(conn_local, nombre_tabla, columnas, filas):
    """Insertar datos del backup JSON con conversión de tipos"""
    if not filas:
        print(f"  [SKIP] Sin datos para insertar")
        return

    cursor = conn_local.cursor()
    try:
        # Obtener tipos de columnas
        tipos = obtener_tipos_columnas(conn_local, nombre_tabla)

        # Preparar INSERT
        cols = ', '.join([f'"{col}"' for col in columnas])
        placeholders = ', '.join(['%s'] * len(columnas))
        insert_sql = f'INSERT INTO "{nombre_tabla}" ({cols}) VALUES ({placeholders})'

        # Insertar filas
        for fila in filas:
            valores = []
            for col in columnas:
                valor_original = fila.get(col)
                tipo_col = tipos.get(col, 'text')
                valor_convertido = convertir_valor(valor_original, tipo_col)
                valores.append(valor_convertido)

            cursor.execute(insert_sql, valores)

        conn_local.commit()
        print(f"  [INSERT] {len(filas)} registros insertados")

    except Exception as e:
        print(f"  [ERROR] Error insertando datos: {e}")
        print(f"    Primera fila: {filas[0] if filas else 'N/A'}")
        conn_local.rollback()
        raise
    finally:
        cursor.close()


# ============================================
# PROCESO PRINCIPAL
# ============================================

def restaurar_con_schema_produccion():
    """Proceso principal de restauración"""
    print("=" * 70)
    print("RESTAURACION CON SCHEMA DE PRODUCCION")
    print("=" * 70)
    print()

    # 1. Cargar backup JSON
    print(f"[STEP 1] Cargando backup: {BACKUP_FILE}")
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        print(f"[OK] {len(backup_data)} tablas en backup")
    except Exception as e:
        print(f"[ERROR] Error cargando backup: {e}")
        sys.exit(1)

    print()

    # 2. Conectar a producción
    print("[STEP 2] Conectando a PRODUCCION para obtener schemas...")
    conn_prod = conectar_produccion()
    print()

    # 3. Conectar a local
    print("[STEP 3] Conectando a LOCAL para restaurar...")
    conn_local = conectar_local()
    print()

    # 4. Procesar cada tabla
    print("[STEP 4] Restaurando tablas...")
    print()

    total_registros = 0
    tablas_exitosas = 0
    tablas_fallidas = []

    for nombre_tabla, info_tabla in backup_data.items():
        print(f"[TABLA] {nombre_tabla}")

        try:
            # 4.1 Obtener schema de producción
            create_sql = obtener_schema_tabla(conn_prod, nombre_tabla)
            if not create_sql:
                print(f"  [SKIP] No se pudo obtener schema, omitiendo...")
                tablas_fallidas.append(nombre_tabla)
                print()
                continue

            # 4.2 Drop tabla local si existe
            drop_tabla(conn_local, nombre_tabla)

            # 4.3 Crear tabla con schema de producción
            crear_tabla_desde_schema(conn_local, nombre_tabla, create_sql)

            # 4.4 Insertar datos del backup
            columnas = info_tabla['columns']
            filas = info_tabla['rows']
            insertar_datos(conn_local, nombre_tabla, columnas, filas)

            total_registros += len(filas)
            tablas_exitosas += 1
            print()

        except Exception as e:
            print(f"  [FAIL] Error procesando '{nombre_tabla}': {e}")
            tablas_fallidas.append(nombre_tabla)
            print()

    # Cerrar conexiones
    conn_prod.close()
    conn_local.close()

    # 5. Resumen
    print("=" * 70)
    print("[RESUMEN] RESTAURACION COMPLETADA")
    print(f"  Tablas exitosas: {tablas_exitosas}/{len(backup_data)}")
    print(f"  Total registros: {total_registros}")

    if tablas_fallidas:
        print(f"  Tablas con errores: {len(tablas_fallidas)}")
        for tabla in tablas_fallidas:
            print(f"    - {tabla}")
    else:
        print("  [OK] Todas las tablas restauradas correctamente!")

    print("=" * 70)


# ============================================
# EJECUCIÓN
# ============================================

if __name__ == '__main__':
    print()
    print("[INFO] Este script:")
    print("  1. Extrae el schema REAL de la BD de produccion (Render)")
    print("  2. Crea las tablas en local con tipos EXACTOS")
    print("  3. Inserta los datos del backup JSON")
    print()
    print("[INFO] Las tablas existentes seran eliminadas y recreadas")
    print()

    respuesta = input("Continuar? (s/n): ")
    if respuesta.lower() != 's':
        print("[CANCEL] Operacion cancelada")
        sys.exit(0)

    print()
    restaurar_con_schema_produccion()
