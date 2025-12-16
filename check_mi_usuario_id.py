#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar tu usuario_id
Compara el usuario_id en SQLite local vs PostgreSQL remoto
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
        return

    print("="*60)
    print("VERIFICANDO USUARIO_ID EN AMBAS BASES DE DATOS")
    print("="*60)

    # 1. Verificar usuario_id en SQLite local
    sqlite_path = 'medicamentos.db'

    if os.path.exists(sqlite_path):
        print("\n[SQLite LOCAL]")
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_cursor = sqlite_conn.cursor()

        # Ver que usuario_id tienen los medicamentos del pastillero
        sqlite_cursor.execute("""
            SELECT DISTINCT usuario_id FROM pastillero_usuarios
        """)

        usuario_ids_sqlite = sqlite_cursor.fetchall()
        print(f"Usuario IDs en pastillero local: {[row[0] for row in usuario_ids_sqlite]}")

        # Contar medicamentos por usuario
        sqlite_cursor.execute("""
            SELECT usuario_id, COUNT(*) as cantidad
            FROM pastillero_usuarios
            GROUP BY usuario_id
        """)

        for row in sqlite_cursor.fetchall():
            print(f"  - Usuario ID {row[0]}: {row[1]} medicamentos")

        sqlite_conn.close()
    else:
        print("\n[SQLite LOCAL] No encontrado")

    # 2. Verificar usuario_id en PostgreSQL
    print("\n[PostgreSQL PRODUCCION]")
    pg_conn = psycopg2.connect(database_url)
    pg_cursor = pg_conn.cursor()

    # Ver que usuario_id tienen los medicamentos del pastillero
    pg_cursor.execute("""
        SELECT DISTINCT usuario_id FROM pastillero_usuarios
    """)

    usuario_ids_pg = pg_cursor.fetchall()
    print(f"Usuario IDs en pastillero PostgreSQL: {[row[0] for row in usuario_ids_pg]}")

    # Contar medicamentos por usuario
    pg_cursor.execute("""
        SELECT usuario_id, COUNT(*) as cantidad
        FROM pastillero_usuarios
        GROUP BY usuario_id
    """)

    for row in pg_cursor.fetchall():
        print(f"  - Usuario ID {row[0]}: {row[1]} medicamentos")

    pg_conn.close()

    print("\n" + "="*60)
    print("RECOMENDACION:")
    print("="*60)
    print("Si los IDs son diferentes, necesitamos actualizar PostgreSQL")
    print("para que todos los medicamentos tengan el mismo usuario_id")
    print("que usas en SQLite local.")
    print("="*60)

if __name__ == '__main__':
    main()
