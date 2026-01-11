#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Recuperación Completa de Datos
Migra datos perdidos durante migración SQLite -> PostgreSQL

CRITICAL: Respeta datos existentes en PostgreSQL, solo agrega lo que falta
"""

import sqlite3
import psycopg2
import os
import re
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

SQLITE_DB = 'c:\\Users\\RAFAEL OLIVARES\\Documents\\MiAppMedicamentos\\medicamentos.db'
ARCHIVO_ORIGINAL = 'sugerir_sintomas_flask.py'
ARCHIVO_ACTUAL = 'sugerir_sintomas_helpers.py'

# Conectar a bases de datos
def get_sqlite_conn():
    return sqlite3.connect(SQLITE_DB)

def get_pg_conn():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(database_url)

# =============================================================================
# PHASE 1: MERGE DE REGLAS
# =============================================================================

def extraer_reglas_de_archivo(archivo):
    """Extrae el diccionario REGLAS_DIAGNOSTICOS de un archivo Python"""
    with open(archivo, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar el diccionario completo
    match = re.search(r'REGLAS_DIAGNOSTICOS\s*=\s*\{(.*?)\n\}', contenido, re.DOTALL)

    if not match:
        return {}

    reglas_texto = match.group(1)

    # Parsear las reglas
    reglas = {}
    patron = r"'([^']+)'\s*:\s*\[(.*?)\]"

    for match in re.finditer(patron, reglas_texto, re.DOTALL):
        clave = match.group(1)
        valores_texto = match.group(2)

        # Extraer los valores (sinónimos)
        valores = re.findall(r"'([^']+)'", valores_texto)
        reglas[clave] = valores

    return reglas

def merge_reglas():
    """Combina reglas originales con nuevas agregadas"""
    print("\n" + "="*80)
    print("PHASE 1: MERGE DE REGLAS")
    print("="*80)

    # Extraer reglas de ambos archivos
    print("\nExtrayendo reglas del archivo original...")
    reglas_originales = extraer_reglas_de_archivo(ARCHIVO_ORIGINAL)
    print(f"  Reglas originales encontradas: {len(reglas_originales)}")

    print("\nExtrayendo reglas del archivo actual...")
    reglas_actuales = extraer_reglas_de_archivo(ARCHIVO_ACTUAL)
    print(f"  Reglas actuales encontradas: {len(reglas_actuales)}")

    # Merge inteligente
    reglas_merged = {}

    # Agregar todas las reglas originales
    for clave, valores in reglas_originales.items():
        reglas_merged[clave] = set(valores)

    # Agregar reglas nuevas
    nuevas_agregadas = 0
    for clave, valores in reglas_actuales.items():
        if clave not in reglas_merged:
            # Regla completamente nueva
            reglas_merged[clave] = set(valores)
            nuevas_agregadas += 1
        else:
            # Regla existente - combinar sinónimos
            before = len(reglas_merged[clave])
            reglas_merged[clave].update(valores)
            after = len(reglas_merged[clave])
            if after > before:
                print(f"  + Expandida '{clave}': {before} -> {after} sinónimos")

    print(f"\nReglas totales después del merge: {len(reglas_merged)}")
    print(f"Reglas nuevas agregadas: {nuevas_agregadas}")

    # Generar nuevo archivo
    print("\nGenerando nuevo sugerir_sintomas_helpers.py...")

    # Leer archivo actual para preservar todo excepto REGLAS_DIAGNOSTICOS
    with open(ARCHIVO_ACTUAL, 'r', encoding='utf-8') as f:
        contenido_actual = f.read()

    # Reemplazar solo el diccionario REGLAS_DIAGNOSTICOS
    nuevo_dict = "REGLAS_DIAGNOSTICOS = {\n"

    # Ordenar por categoría (si hay comentarios de sección, preservarlos)
    for clave in sorted(reglas_merged.keys()):
        valores = sorted(list(reglas_merged[clave]))
        valores_str = ", ".join([f"'{v}'" for v in valores])
        nuevo_dict += f"    '{clave}': [{valores_str}],\n"

    nuevo_dict += "}\n"

    # Reemplazar en el contenido
    contenido_nuevo = re.sub(
        r'REGLAS_DIAGNOSTICOS\s*=\s*\{.*?\n\}',
        nuevo_dict.rstrip(),
        contenido_actual,
        flags=re.DOTALL
    )

    # Guardar backup
    with open(ARCHIVO_ACTUAL + '.backup', 'w', encoding='utf-8') as f:
        f.write(contenido_actual)
    print(f"  Backup guardado en {ARCHIVO_ACTUAL}.backup")

    # Guardar nuevo archivo
    with open(ARCHIVO_ACTUAL, 'w', encoding='utf-8') as f:
        f.write(contenido_nuevo)
    print(f"  Nuevo archivo guardado con {len(reglas_merged)} reglas")

    return len(reglas_merged)

# =============================================================================
# PHASE 2: MIGRACIÓN DE TABLAS BASE (SINTOMAS Y DIAGNOSTICOS)
# =============================================================================

def obtener_nombre_real_tabla_pg(tabla_esperada):
    """Obtiene el nombre REAL de una tabla en PostgreSQL (case-sensitive)"""
    pg_conn = get_pg_conn()
    pg_cursor = pg_conn.cursor()

    # Buscar tabla ignorando case
    pg_cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND LOWER(table_name) = LOWER(%s)
    """, (tabla_esperada,))

    resultado = pg_cursor.fetchone()
    pg_conn.close()

    if resultado:
        return resultado[0]
    else:
        return None

def migrar_tabla_base(tabla_sqlite, tabla_pg_esperada, descripcion):
    """Migra tabla base completa (SINTOMAS o DIAGNOSTICOS) con todas sus columnas"""
    print(f"\n{descripcion}:")

    # Obtener nombre REAL de tabla en PostgreSQL
    tabla_pg = obtener_nombre_real_tabla_pg(tabla_pg_esperada)

    if not tabla_pg:
        print(f"  ERROR: Tabla {tabla_pg_esperada} no existe en PostgreSQL")
        return 0, 0, 0, 0

    print(f"  Nombre real tabla PostgreSQL: {tabla_pg}")

    sqlite_conn = get_sqlite_conn()
    pg_conn = get_pg_conn()
    pg_cursor = pg_conn.cursor()

    # Obtener estructura de la tabla SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(f"PRAGMA table_info({tabla_sqlite})")
    columnas_info = sqlite_cursor.fetchall()
    columnas = [col[1] for col in columnas_info]  # col[1] es el nombre de columna

    print(f"  Columnas detectadas: {', '.join(columnas)}")

    # Leer todos los registros de SQLite
    columnas_str = ", ".join(columnas)
    sqlite_cursor.execute(f"SELECT {columnas_str} FROM {tabla_sqlite}")
    registros = sqlite_cursor.fetchall()

    print(f"  Registros en SQLite: {len(registros)}")

    # Migrar cada registro verificando por ID
    insertados = 0
    actualizados = 0
    ya_existian = 0
    errores = 0

    for registro in registros:
        try:
            # Verificar si existe por ID
            id_value = registro[0]  # Asumiendo que primera columna es ID
            pg_cursor.execute(f'SELECT * FROM "{tabla_pg}" WHERE id = %s', (id_value,))
            existe = pg_cursor.fetchone()

            if existe:
                # Comparar si son iguales
                if existe == registro:
                    ya_existian += 1
                else:
                    # Actualizar con datos de SQLite
                    set_parts = []
                    valores = []
                    for i, col in enumerate(columnas[1:], 1):  # Skip ID
                        set_parts.append(f"{col} = %s")
                        valores.append(registro[i])
                    valores.append(id_value)  # Para WHERE

                    query_update = f'UPDATE "{tabla_pg}" SET {", ".join(set_parts)} WHERE id = %s'
                    pg_cursor.execute(query_update, valores)
                    actualizados += 1
            else:
                # Insertar nuevo registro
                placeholders = ", ".join(["%s"] * len(columnas))
                query_insert = f'INSERT INTO "{tabla_pg}" ({columnas_str}) VALUES ({placeholders})'
                pg_cursor.execute(query_insert, registro)
                insertados += 1

        except Exception as e:
            errores += 1
            print(f"  ERROR en registro ID {registro[0]}: {e}")

    # Commit
    pg_conn.commit()

    print(f"  Ya existian (sin cambios): {ya_existian}")
    print(f"  Actualizados: {actualizados}")
    print(f"  Insertados: {insertados}")
    print(f"  Errores: {errores}")

    sqlite_conn.close()
    pg_conn.close()

    return insertados, actualizados, ya_existian, errores

# =============================================================================
# PHASE 3-5: MIGRACIÓN DE RELACIONES
# =============================================================================

def migrar_relaciones(tabla_sqlite, tabla_pg_esperada, columnas, descripcion):
    """Migra relaciones de SQLite a PostgreSQL verificando existencia"""
    print(f"\n{descripcion}:")

    # Obtener nombre REAL de tabla en PostgreSQL
    tabla_pg = obtener_nombre_real_tabla_pg(tabla_pg_esperada)

    if not tabla_pg:
        print(f"  ERROR: Tabla {tabla_pg_esperada} no existe en PostgreSQL")
        return 0, 0, 0

    print(f"  Nombre real tabla PostgreSQL: {tabla_pg}")

    sqlite_conn = get_sqlite_conn()
    pg_conn = get_pg_conn()
    pg_cursor = pg_conn.cursor()

    # Leer registros de SQLite
    sqlite_cursor = sqlite_conn.cursor()
    columnas_str = ", ".join(columnas)
    sqlite_cursor.execute(f"SELECT {columnas_str} FROM {tabla_sqlite}")
    registros = sqlite_cursor.fetchall()

    print(f"  Registros en SQLite: {len(registros)}")

    # Verificar cuántos ya existen en PostgreSQL
    insertados = 0
    ya_existian = 0
    errores = 0

    for registro in registros:
        try:
            # Construir WHERE clause para verificar existencia
            where_parts = []
            for i, col in enumerate(columnas):
                where_parts.append(f"{col} = %s")
            where_clause = " AND ".join(where_parts)

            # Verificar si existe
            query_check = f'SELECT 1 FROM "{tabla_pg}" WHERE {where_clause}'
            pg_cursor.execute(query_check, registro)
            existe = pg_cursor.fetchone()

            if existe:
                ya_existian += 1
            else:
                # Insertar
                placeholders = ", ".join(["%s"] * len(columnas))
                query_insert = f'INSERT INTO "{tabla_pg}" ({columnas_str}) VALUES ({placeholders})'
                pg_cursor.execute(query_insert, registro)
                insertados += 1

        except Exception as e:
            errores += 1
            print(f"  ERROR en registro {registro}: {e}")

    # Commit
    pg_conn.commit()

    print(f"  Ya existian: {ya_existian}")
    print(f"  Insertados: {insertados}")
    print(f"  Errores: {errores}")

    sqlite_conn.close()
    pg_conn.close()

    return insertados, ya_existian, errores

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "#"*80)
    print("# RECUPERACION COMPLETA DE DATOS")
    print("# SQLite -> PostgreSQL")
    print("#"*80)

    try:
        # PHASE 1: Merge de reglas
        total_reglas = merge_reglas()

        # PHASE 2: Migrar tablas base SINTOMAS y DIAGNOSTICOS
        print("\n" + "="*80)
        print("PHASE 2: MIGRACION DE TABLAS BASE")
        print("="*80)

        # Migrar SINTOMAS
        print("\n--- Tabla SINTOMAS ---")
        ins_sint, upd_sint, exist_sint, err_sint = migrar_tabla_base(
            'SINTOMAS',
            'sintomas',
            "Sintomas (569 registros esperados)"
        )

        # Migrar DIAGNOSTICOS
        print("\n--- Tabla DIAGNOSTICOS ---")
        ins_diag, upd_diag, exist_diag, err_diag = migrar_tabla_base(
            'DIAGNOSTICOS',
            'diagnosticos',
            "Diagnosticos (165 registros esperados)"
        )

        # PHASE 3: Migrar MEDICAMENTO_SINTOMA
        print("\n" + "="*80)
        print("PHASE 3: MIGRACION DE RELACIONES MEDICAMENTO-SINTOMA")
        print("="*80)
        ins3, exist3, err3 = migrar_relaciones(
            'MEDICAMENTO_SINTOMA',
            'medicamento_sintoma',
            ['medicamento_id', 'sintoma_id'],
            "Relaciones medicamento-sintoma (3,543 registros esperados)"
        )

        # PHASE 4: Migrar DIAGNOSTICO_MEDICAMENTO
        print("\n" + "="*80)
        print("PHASE 4: MIGRACION DE RELACIONES DIAGNOSTICO-MEDICAMENTO")
        print("="*80)
        ins4, exist4, err4 = migrar_relaciones(
            'DIAGNOSTICO_MEDICAMENTO',
            'diagnostico_medicamento',
            ['diagnostico_id', 'medicamento_id'],
            "Relaciones diagnostico-medicamento (878 registros esperados)"
        )

        # PHASE 5: Migrar DIAGNOSTICO_SINTOMA
        print("\n" + "="*80)
        print("PHASE 5: MIGRACION DE RELACIONES DIAGNOSTICO-SINTOMA")
        print("="*80)
        ins5, exist5, err5 = migrar_relaciones(
            'DIAGNOSTICO_SINTOMA',
            'diagnostico_sintoma',
            ['diagnostico_id', 'sintoma_id'],
            "Relaciones diagnostico-sintoma (688 registros esperados)"
        )

        # RESUMEN FINAL
        print("\n" + "#"*80)
        print("# RESUMEN DE RECUPERACION")
        print("#"*80)
        print(f"\nREGLAS:")
        print(f"  Total de reglas combinadas: {total_reglas}")
        print(f"\nTABLAS BASE MIGRADAS:")
        print(f"  SINTOMAS (569 esperados):")
        print(f"    - Ya existian (sin cambios): {exist_sint}")
        print(f"    - Actualizados: {upd_sint}")
        print(f"    - Insertados: {ins_sint}")
        print(f"    - Errores: {err_sint}")
        print(f"  DIAGNOSTICOS (165 esperados):")
        print(f"    - Ya existian (sin cambios): {exist_diag}")
        print(f"    - Actualizados: {upd_diag}")
        print(f"    - Insertados: {ins_diag}")
        print(f"    - Errores: {err_diag}")
        print(f"\nRELACIONES MIGRADAS:")
        print(f"  MEDICAMENTO_SINTOMA (3,543 esperados):")
        print(f"    - Ya existian: {exist3}")
        print(f"    - Insertados: {ins3}")
        print(f"    - Errores: {err3}")
        print(f"  DIAGNOSTICO_MEDICAMENTO (878 esperados):")
        print(f"    - Ya existian: {exist4}")
        print(f"    - Insertados: {ins4}")
        print(f"    - Errores: {err4}")
        print(f"  DIAGNOSTICO_SINTOMA (688 esperados):")
        print(f"    - Ya existian: {exist5}")
        print(f"    - Insertados: {ins5}")
        print(f"    - Errores: {err5}")
        print(f"\nTOTAL REGISTROS INSERTADOS: {ins_sint + ins_diag + ins3 + ins4 + ins5}")
        print(f"TOTAL REGISTROS ACTUALIZADOS: {upd_sint + upd_diag}")
        print(f"TOTAL REGISTROS YA EXISTENTES: {exist_sint + exist_diag + exist3 + exist4 + exist5}")

        print("\n" + "#"*80)
        print("# RECUPERACION COMPLETA")
        print("#"*80)

    except Exception as e:
        print(f"\nERROR FATAL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
