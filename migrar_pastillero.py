#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para migrar datos del pastillero desde SQLite local a PostgreSQL en producción
Ejecutar UNA SOLA VEZ desde tu máquina local
"""
import os
import sys
import sqlite3
import psycopg2

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL no esta configurada")
        print("Configura la variable de entorno DATABASE_URL con la URL de PostgreSQL")
        return

    sqlite_path = 'medicamentos.db'

    if not os.path.exists(sqlite_path):
        print(f"ERROR: No se encuentra el archivo {sqlite_path}")
        print(f"Asegurate de ejecutar este script desde el directorio del proyecto")
        return

    print(f"Leyendo datos de {sqlite_path}...")

    try:
        # Conectar a SQLite local
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()

        # Leer datos del pastillero
        sqlite_cursor.execute("""
            SELECT usuario_id, medicamento_id, nombre, cantidad, unidad
            FROM pastillero_usuarios
        """)

        pastillero_rows = sqlite_cursor.fetchall()

        if not pastillero_rows:
            print("No hay medicamentos en el pastillero local para migrar")
            sqlite_conn.close()
            return

        print(f"Encontrados {len(pastillero_rows)} medicamentos en pastillero local")
        print("\nConectando a PostgreSQL en produccion...")

        # Conectar a PostgreSQL
        pg_conn = psycopg2.connect(database_url)
        pg_cursor = pg_conn.cursor()

        print("Conexion exitosa a PostgreSQL\n")

        count_nuevos = 0
        count_existentes = 0

        for row in pastillero_rows:
            usuario_id = row['usuario_id']
            medicamento_id = row['medicamento_id']
            nombre = row['nombre']
            cantidad = row['cantidad']
            unidad = row['unidad']

            # Verificar si ya existe para evitar duplicados
            pg_cursor.execute("""
                SELECT id FROM pastillero_usuarios
                WHERE usuario_id = %s
                AND (medicamento_id IS NOT DISTINCT FROM %s)
                AND nombre = %s
            """, (usuario_id, medicamento_id, nombre))

            existe = pg_cursor.fetchone()

            if not existe:
                pg_cursor.execute("""
                    INSERT INTO pastillero_usuarios (usuario_id, medicamento_id, nombre, cantidad, unidad)
                    VALUES (%s, %s, %s, %s, %s)
                """, (usuario_id, medicamento_id, nombre, cantidad, unidad))
                count_nuevos += 1
                print(f"  + Agregado: {nombre} (cantidad: {cantidad} {unidad})")
            else:
                count_existentes += 1
                print(f"  = Ya existe: {nombre}")

        pg_conn.commit()
        pg_cursor.close()
        pg_conn.close()
        sqlite_conn.close()

        print(f"\n{'='*60}")
        print(f"MIGRACION COMPLETADA")
        print(f"{'='*60}")
        print(f"Total medicamentos en SQLite: {len(pastillero_rows)}")
        print(f"Nuevos agregados a PostgreSQL: {count_nuevos}")
        print(f"Ya existian: {count_existentes}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\nERROR durante la migracion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
