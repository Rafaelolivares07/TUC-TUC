#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para ver usuarios en PostgreSQL
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
        print("USUARIOS EN PostgreSQL:")
        print("="*60)
        cur.execute("""
            SELECT id, nombre, usuario, rol, dispositivo_id
            FROM "USUARIOS"
            ORDER BY id
        """)

        usuarios = cur.fetchall()

        if usuarios:
            for row in usuarios:
                print(f"\nID: {row[0]}")
                print(f"  Nombre: {row[1]}")
                print(f"  Usuario: {row[2]}")
                print(f"  Rol: {row[3]}")
                print(f"  Dispositivo ID: {row[4]}")
                print("-" * 40)
        else:
            print("No hay usuarios en la base de datos")

        conn.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
