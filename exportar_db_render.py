# -*- coding: utf-8 -*-
"""
Script para exportar datos de PostgreSQL (Render) a SQLite local
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
import os

print("=" * 80)
print("EXPORTANDO BASE DE DATOS DE RENDER A SQLITE LOCAL")
print("=" * 80)

# Conectar a PostgreSQL (Render)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print("\n1. Conectando a PostgreSQL en Render...")
pg_conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
pg_cursor = pg_conn.cursor()

# Crear/conectar a SQLite local
print("2. Creando base de datos SQLite local...")
sqlite_conn = sqlite3.connect('medicamentos_local.db')
sqlite_cursor = sqlite_conn.cursor()

# Lista de tablas a exportar (en orden de dependencias)
tablas = [
    'USUARIOS',
    'componentes_activos',
    'categorias',
    'subcategorias',
    'medicamentos',
    'precios',
    'sintomas',
    'diagnosticos',
    'medicamento_sintoma',
    'medicamento_diagnostico',
    'sintomas_temp',
    'diagnosticos_temp',
    'PASTILLERO',
    'RECORDATORIOS_TELEGRAM'
]

print(f"\n3. Exportando {len(tablas)} tablas...\n")

for tabla in tablas:
    try:
        # Obtener estructura de la tabla
        pg_cursor.execute(f"""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{tabla.lower()}'
            ORDER BY ordinal_position
        """)
        columnas = pg_cursor.fetchall()

        if not columnas:
            print(f"   ⚠ Tabla '{tabla}' no encontrada, saltando...")
            continue

        # Crear CREATE TABLE statement para SQLite
        columnas_sql = []
        for col in columnas:
            nombre = col['column_name']
            tipo = col['data_type']

            # Mapear tipos PostgreSQL a SQLite
            if tipo in ('integer', 'bigint', 'smallint'):
                tipo_sqlite = 'INTEGER'
            elif tipo in ('numeric', 'decimal', 'real', 'double precision'):
                tipo_sqlite = 'REAL'
            elif tipo in ('boolean'):
                tipo_sqlite = 'TEXT'  # SQLite no tiene boolean nativo
            elif tipo in ('timestamp without time zone', 'timestamp with time zone', 'date', 'time'):
                tipo_sqlite = 'TEXT'
            else:
                tipo_sqlite = 'TEXT'

            # PRIMARY KEY para id
            if nombre == 'id':
                columnas_sql.append(f"{nombre} {tipo_sqlite} PRIMARY KEY")
            else:
                columnas_sql.append(f"{nombre} {tipo_sqlite}")

        # Crear tabla en SQLite
        drop_sql = f"DROP TABLE IF EXISTS {tabla}"
        create_sql = f"CREATE TABLE {tabla} ({', '.join(columnas_sql)})"

        sqlite_cursor.execute(drop_sql)
        sqlite_cursor.execute(create_sql)

        # Obtener datos de PostgreSQL
        pg_cursor.execute(f'SELECT * FROM "{tabla}"')
        rows = pg_cursor.fetchall()

        if rows:
            # Insertar datos en SQLite
            nombres_columnas = [col['column_name'] for col in columnas]
            placeholders = ', '.join(['?' for _ in nombres_columnas])
            insert_sql = f"INSERT INTO {tabla} ({', '.join(nombres_columnas)}) VALUES ({placeholders})"

            for row in rows:
                valores = []
                for col_name in nombres_columnas:
                    val = row[col_name]
                    # Convertir booleanos a texto
                    if isinstance(val, bool):
                        val = 'TRUE' if val else 'FALSE'
                    valores.append(val)

                sqlite_cursor.execute(insert_sql, valores)

            print(f"   ✓ {tabla}: {len(rows)} registros exportados")
        else:
            print(f"   ○ {tabla}: 0 registros (tabla vacía)")

    except Exception as e:
        print(f"   ✗ Error en tabla '{tabla}': {str(e)}")

# Commit y cerrar
sqlite_conn.commit()
pg_conn.close()
sqlite_conn.close()

print("\n" + "=" * 80)
print("EXPORTACIÓN COMPLETA")
print("=" * 80)
print("\nBase de datos SQLite creada: medicamentos_local.db")
print("\nPara usar esta base de datos localmente:")
print("  1. Detén el servidor Flask")
print("  2. Elimina o renombra DATABASE_URL en tus variables de entorno")
print("  3. El código automáticamente usará SQLite si no encuentra DATABASE_URL")
print("\n" + "=" * 80)
