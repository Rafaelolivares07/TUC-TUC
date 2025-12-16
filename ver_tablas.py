#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para ver todas las tablas en PostgreSQL
"""
import os
import sys
import psycopg2

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL no esta configurada")
        return

    print("Conectando a PostgreSQL...")

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        print("OK Conexion exitosa\n")

        print("="*60)
        print("TABLAS EN PostgreSQL:")
        print("="*60)
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        tablas = cur.fetchall()

        for row in tablas:
            print(f"  - {row[0]}")

        conn.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
