"""
Script MEJORADO para restaurar el backup JSON a PostgreSQL local con tipos correctos

MEJORAS:
- Infiere tipos PostgreSQL correctamente (INTEGER, BOOLEAN, TIMESTAMP, TEXT, etc.)
- Permite reemplazar backup fácilmente (DROP TABLE IF EXISTS)
- Maneja columnas id como PRIMARY KEY
- Detecta timestamps y booleanos automáticamente

REQUISITOS:
1. PostgreSQL instalado localmente
2. Base de datos creada (ej: tuctuc_local)
3. psycopg2 instalado: pip install psycopg2

USO:
    python restaurar_backup_mejorado.py

CONFIGURACIÓN:
    Edita las variables de conexión abajo con tus credenciales locales
"""

import json
import psycopg2
from psycopg2 import sql
import sys
from datetime import datetime
import re

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
# FUNCIONES DE INFERENCIA DE TIPOS
# ============================================

def es_timestamp(valor):
    """Detecta si un string es un timestamp ISO"""
    if not isinstance(valor, str):
        return False

    # Patrones comunes de timestamp
    patrones = [
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # 2025-12-10T18:16:23
        r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',  # 2025-12-10 18:16:23
    ]

    for patron in patrones:
        if re.match(patron, valor):
            return True

    return False


def es_uuid(valor):
    """Detecta si un string es un UUID"""
    if not isinstance(valor, str):
        return False
    # Patrón UUID: 8-4-4-4-12 caracteres hexadecimales
    patron = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(patron, valor, re.IGNORECASE))


def es_telefono(nombre_col, valores_muestra):
    """Detecta si una columna es un teléfono (números largos como strings)"""
    nombre_lower = nombre_col.lower()

    # Nombres comunes de teléfono
    if 'telefono' in nombre_lower or 'whatsapp' in nombre_lower or 'celular' in nombre_lower:
        return True

    # Verificar si los valores son strings numéricos largos (10+ dígitos)
    for valor in valores_muestra[:5]:
        if valor is not None:
            if isinstance(valor, str) and valor.isdigit() and len(valor) >= 10:
                return True

    return False


def inferir_tipo_columna(nombre_col, valores_muestra):
    """
    Infiere el tipo PostgreSQL para una columna basándose en:
    1. Nombre de la columna (id, fecha_*, activo, etc.)
    2. Valores de muestra de las primeras filas

    Retorna: Tipo PostgreSQL como string
    """
    nombre_lower = nombre_col.lower()

    # Regla 1: Columna 'id' es siempre INTEGER PRIMARY KEY
    if nombre_lower == 'id':
        return 'INTEGER PRIMARY KEY'

    # Regla 2: dispositivo_id es especial - puede ser UUID
    if nombre_lower == 'dispositivo_id':
        # Verificar si contiene UUIDs
        valores_no_nulos = [v for v in valores_muestra if v is not None][:5]
        for valor in valores_no_nulos:
            if es_uuid(valor):
                return 'TEXT'  # UUIDs como TEXT
        return 'INTEGER'  # Si no es UUID, es INTEGER

    # Regla 3: Columnas de teléfono - siempre TEXT (pueden ser muy largos)
    if es_telefono(nombre_col, valores_muestra):
        return 'TEXT'

    # Regla 4: Columnas que terminan en '_id' son INTEGER (foreign keys)
    if nombre_lower.endswith('_id'):
        return 'INTEGER'

    # Regla 5: Columnas con 'fecha' o 'timestamp' en el nombre
    if 'fecha' in nombre_lower or 'timestamp' in nombre_lower:
        return 'TIMESTAMP'

    # Regla 6: Columnas 'activo', 'activa', '*_activo', '*_activa'
    # PERO verificar que realmente sean booleanos
    if nombre_lower in ['activo', 'activa'] or nombre_lower.endswith('_activo') or nombre_lower.endswith('_activa') or nombre_lower.endswith('_activas'):
        # Verificar valores para confirmar
        valores_no_nulos = [v for v in valores_muestra if v is not None][:5]
        for valor in valores_no_nulos:
            if isinstance(valor, bool):
                return 'BOOLEAN'
            elif valor in [0, 1, '0', '1', True, False]:
                return 'BOOLEAN'
        # Si no son booleanos, tratar como texto (caso medicamentos_top.componente_activo)
        return 'TEXT'

    # Regla 7: Analizar valores de muestra
    # Tomar hasta 10 valores no nulos para análisis
    valores_no_nulos = [v for v in valores_muestra if v is not None][:10]

    if not valores_no_nulos:
        return 'TEXT'  # Si no hay valores, usar TEXT por seguridad

    # Detectar tipos por valor
    tipo_detectado = None

    for valor in valores_no_nulos:
        if isinstance(valor, bool):
            # Python bool (True/False) -> BOOLEAN
            tipo_detectado = 'BOOLEAN'
            break
        elif isinstance(valor, int):
            # Python int -> INTEGER
            if tipo_detectado is None:
                tipo_detectado = 'INTEGER'
        elif isinstance(valor, float):
            # Python float -> NUMERIC
            tipo_detectado = 'NUMERIC'
            break
        elif isinstance(valor, str):
            # String puede ser TEXT o TIMESTAMP
            if es_timestamp(valor):
                tipo_detectado = 'TIMESTAMP'
                break
            else:
                # Verificar si es un número en string
                try:
                    num = int(valor)
                    # Si es muy grande (>2 mil millones), usar TEXT
                    if num > 2147483647:  # Max INTEGER en PostgreSQL
                        tipo_detectado = 'TEXT'
                        break
                    if tipo_detectado is None:
                        tipo_detectado = 'INTEGER'
                except ValueError:
                    try:
                        float(valor)
                        tipo_detectado = 'NUMERIC'
                    except ValueError:
                        tipo_detectado = 'TEXT'

    return tipo_detectado or 'TEXT'


# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def conectar():
    """Conectar a PostgreSQL local"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"[OK] Conectado a PostgreSQL local: {DB_CONFIG['database']}")
        return conn
    except Exception as e:
        print(f"[ERROR] Error conectando a PostgreSQL: {e}")
        print("\nVerifica:")
        print("  1. PostgreSQL esta corriendo")
        print("  2. La base de datos existe")
        print("  3. Usuario y contrasena son correctos")
        sys.exit(1)


def drop_tabla(conn, nombre_tabla):
    """Eliminar tabla si existe (para permitir reemplazo)"""
    cursor = conn.cursor()
    try:
        cursor.execute(f'DROP TABLE IF EXISTS "{nombre_tabla}" CASCADE')
        conn.commit()
        print(f"  [DROP] Tabla antigua '{nombre_tabla}' eliminada (si existia)")
    except Exception as e:
        print(f"  [WARN] No se pudo eliminar '{nombre_tabla}': {e}")
        conn.rollback()
    finally:
        cursor.close()


def crear_tabla(conn, nombre_tabla, columnas, filas):
    """Crear tabla con tipos correctos inferidos"""
    cursor = conn.cursor()

    try:
        # Inferir tipos para cada columna
        columnas_sql = []

        for col in columnas:
            # Obtener valores de muestra de esta columna
            valores_muestra = [fila.get(col) for fila in filas[:20]]  # Primeras 20 filas

            # Inferir tipo
            tipo = inferir_tipo_columna(col, valores_muestra)

            columnas_sql.append(f'"{col}" {tipo}')

        # Crear tabla
        create_sql = f'CREATE TABLE "{nombre_tabla}" ({", ".join(columnas_sql)})'
        cursor.execute(create_sql)
        conn.commit()

        # Mostrar tipos asignados
        print(f"  [CREATE] Tabla '{nombre_tabla}' creada con {len(columnas)} columnas")

        # Mostrar algunos tipos importantes
        tipos_interesantes = [(col, inferir_tipo_columna(col, [fila.get(col) for fila in filas[:20]]))
                              for col in columnas[:5]]
        for col, tipo in tipos_interesantes:
            print(f"    - {col}: {tipo}")
        if len(columnas) > 5:
            print(f"    ... y {len(columnas) - 5} columnas mas")

    except Exception as e:
        print(f"  [ERROR] Error creando tabla '{nombre_tabla}': {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()


def insertar_datos(conn, nombre_tabla, columnas, filas):
    """Insertar datos en la tabla"""
    if not filas:
        print(f"  [SKIP] Tabla '{nombre_tabla}' sin datos")
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
        print(f"  [INSERT] {len(filas)} registros insertados")

    except Exception as e:
        print(f"  [ERROR] Error insertando datos en '{nombre_tabla}': {e}")
        print(f"    Primera fila que causo error: {filas[0] if filas else 'N/A'}")
        conn.rollback()
        raise
    finally:
        cursor.close()


# ============================================
# PROCESO PRINCIPAL
# ============================================

def restaurar_backup():
    """Proceso principal de restauración"""
    print("=" * 70)
    print("RESTAURACION DE BACKUP A POSTGRESQL LOCAL (VERSION MEJORADA)")
    print("=" * 70)
    print()

    # Cargar backup JSON
    print(f"[LOAD] Cargando backup: {BACKUP_FILE}")
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        print(f"[OK] Backup cargado: {len(backup_data)} tablas encontradas")
    except Exception as e:
        print(f"[ERROR] Error cargando backup: {e}")
        sys.exit(1)

    print()

    # Conectar a PostgreSQL
    conn = conectar()
    print()

    # Restaurar cada tabla
    print("[RESTORE] Restaurando tablas...")
    print()

    total_registros = 0
    tablas_exitosas = 0
    tablas_fallidas = []

    for nombre_tabla, info_tabla in backup_data.items():
        print(f"[TABLA] {nombre_tabla}")

        try:
            columnas = info_tabla['columns']
            filas = info_tabla['rows']

            # 1. Eliminar tabla antigua (permite reemplazo)
            drop_tabla(conn, nombre_tabla)

            # 2. Crear tabla con tipos correctos
            crear_tabla(conn, nombre_tabla, columnas, filas)

            # 3. Insertar datos
            insertar_datos(conn, nombre_tabla, columnas, filas)

            total_registros += len(filas)
            tablas_exitosas += 1
            print()

        except Exception as e:
            print(f"  [FAIL] Fallo al procesar '{nombre_tabla}': {e}")
            tablas_fallidas.append(nombre_tabla)
            print()

    conn.close()

    # Resumen final
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
    print("[INFO] Este script eliminara y recreara las tablas existentes")
    print("[INFO] Esto permite reemplazar el backup facilmente en el futuro")
    print()

    respuesta = input("Continuar? (s/n): ")
    if respuesta.lower() != 's':
        print("[CANCEL] Operacion cancelada por el usuario")
        sys.exit(0)

    print()
    restaurar_backup()
