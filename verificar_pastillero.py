#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar datos del pastillero en PostgreSQL
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

        # Ver medicamentos del pastillero y sus usuarios
        print("\n" + "="*60)
        print("MEDICAMENTOS EN PASTILLERO (agrupados por usuario_id):")
        print("="*60)
        cur.execute("""
            SELECT usuario_id, COUNT(*) as cantidad
            FROM pastillero_usuarios
            GROUP BY usuario_id
            ORDER BY usuario_id
        """)

        grupos = cur.fetchall()
        for row in grupos:
            usuario_id = row[0]
            cantidad = row[1]
            print(f"\nUsuario ID {usuario_id}: {cantidad} medicamentos")

            # Mostrar primeros 5 medicamentos de este usuario
            cur.execute("""
                SELECT id, nombre, cantidad, unidad, medicamento_id
                FROM pastillero_usuarios
                WHERE usuario_id = %s
                LIMIT 5
            """, (usuario_id,))

            meds = cur.fetchall()
            for med in meds:
                print(f"  - [{med[0]}] {med[1]} ({med[2]} {med[3]}) [med_id: {med[4]}]")

            if cantidad > 5:
                print(f"  ... y {cantidad - 5} mas")

        conn.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
