"""
Script para migrar todos los datos de SQLite a PostgreSQL
"""
import sqlite3
import psycopg2
import os
import sys
from dotenv import load_dotenv

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# Conectar a SQLite (origen)
sqlite_conn = sqlite3.connect('medicamentos.db')
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# Conectar a PostgreSQL (destino) - Render
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

postgres_conn = psycopg2.connect(database_url)
postgres_cursor = postgres_conn.cursor()

print("OK - Conectado a ambas bases de datos")

# Obtener todas las tablas
sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [row[0] for row in sqlite_cursor.fetchall()]

print(f"[INFO] Encontradas {len(tables)} tablas para migrar")

# Para cada tabla
for table in tables:
    print(f"\n[MIGRANDO] Tabla: {table}")

    # 1. Obtener estructura de la tabla
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    columns_info = sqlite_cursor.fetchall()

    # 2. Crear la tabla en PostgreSQL
    columns_def = []
    for col in columns_info:
        col_name = col[1]
        col_type = col[2].upper()

        # Mapear tipos de SQLite a PostgreSQL
        if 'INT' in col_type:
            pg_type = 'INTEGER'
        elif 'TEXT' in col_type or 'CHAR' in col_type:
            pg_type = 'TEXT'
        elif 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
            pg_type = 'REAL'
        elif 'BLOB' in col_type:
            pg_type = 'BYTEA'
        elif 'TIMESTAMP' in col_type or 'DATETIME' in col_type:
            pg_type = 'TIMESTAMP'
        elif 'DATE' in col_type:
            pg_type = 'DATE'
        else:
            pg_type = 'TEXT'

        # PRIMARY KEY
        if col[5] == 1:  # pk
            columns_def.append(f'"{col_name}" {pg_type} PRIMARY KEY')
        else:
            columns_def.append(f'"{col_name}" {pg_type}')

    create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(columns_def)})'

    try:
        postgres_cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        postgres_cursor.execute(create_table_sql)
        postgres_conn.commit()
        print(f"  [OK] Tabla {table} creada")
    except Exception as e:
        print(f"  [ERROR] Error creando tabla {table}: {e}")
        continue

    # 3. Copiar datos
    sqlite_cursor.execute(f"SELECT * FROM {table}")
    rows = sqlite_cursor.fetchall()

    if len(rows) == 0:
        print(f"  [INFO] Tabla {table} esta vacia")
        continue

    # Obtener nombres de columnas
    columns = [description[0] for description in sqlite_cursor.description]
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join([f'"{col}"' for col in columns])

    insert_sql = f'INSERT INTO "{table}" ({columns_str}) VALUES ({placeholders})'

    try:
        for row in rows:
            postgres_cursor.execute(insert_sql, tuple(row))
        postgres_conn.commit()
        print(f"  [OK] {len(rows)} registros copiados")
    except Exception as e:
        print(f"  [ERROR] Error copiando datos a {table}: {e}")
        postgres_conn.rollback()

# Cerrar conexiones
sqlite_conn.close()
postgres_conn.close()

print("\n[COMPLETADO] Migracion finalizada!")
print("[INFO] Ahora tu base PostgreSQL tiene todos los datos de SQLite")
