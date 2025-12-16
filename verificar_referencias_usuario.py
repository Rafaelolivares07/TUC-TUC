#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar si hay datos que referencien usuario_id = 1
"""
import os
import sys
import psycopg2

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL no esta configurada")
        return

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    print("Buscando referencias a usuario_id = 1 en otras tablas...\n")

    # Tablas que podrían tener usuario_id
    tablas_posibles = [
        'pedidos',
        'RECETAS',
        'navegacion_anonima',
        'NAVEGACION_MENU',
        'alertas_admin',
        'requerimientos'
    ]

    for tabla in tablas_posibles:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{tabla}" WHERE usuario_id = 1')
            count = cur.fetchone()[0]
            if count > 0:
                print(f"  {tabla}: {count} registros con usuario_id = 1")
        except Exception as e:
            # Tabla no tiene columna usuario_id o no existe
            pass

    conn.close()

if __name__ == '__main__':
    main()
