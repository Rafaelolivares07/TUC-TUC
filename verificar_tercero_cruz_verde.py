#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar si existe el tercero CRUZ VERDE
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

    print("Conectando a base de datos...")

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        print("OK Conexion exitosa\n")

        # Buscar terceros que contengan "CRUZ" o "VERDE"
        print("Buscando terceros con 'CRUZ' o 'VERDE'...\n")

        cur.execute("""
            SELECT id, nombre, telefono, direccion, fecha_creacion, fecha_actualizacion
            FROM terceros
            WHERE nombre ILIKE '%CRUZ%' OR nombre ILIKE '%VERDE%'
            ORDER BY nombre
        """)

        resultados = cur.fetchall()

        if resultados:
            print(f"OK Encontrados {len(resultados)} tercero(s):\n")
            for row in resultados:
                id_tercero, nombre, telefono, direccion, fecha_creacion, fecha_actualizacion = row
                print(f"  ID: {id_tercero}")
                print(f"  Nombre: {nombre}")
                print(f"  Telefono: {telefono or 'N/A'}")
                print(f"  Direccion: {direccion or 'N/A'}")
                print(f"  Creado: {fecha_creacion}")
                print(f"  Actualizado: {fecha_actualizacion}")
                print("-" * 50)
        else:
            print("ERROR No se encontro ningun tercero con 'CRUZ' o 'VERDE'")

        # Listar los últimos 10 terceros por orden alfabético
        print("\n\nUltimos 10 terceros (orden alfabetico):\n")
        cur.execute("""
            SELECT id, nombre
            FROM terceros
            ORDER BY nombre
            LIMIT 10
        """)

        for row in cur.fetchall():
            print(f"  [{row[0]}] {row[1]}")

        # Listar los últimos 10 terceros por fecha de actualización (como el endpoint actual)
        print("\n\nUltimos 10 terceros (por fecha actualizacion):\n")
        cur.execute("""
            SELECT id, nombre, fecha_actualizacion
            FROM terceros
            ORDER BY fecha_actualizacion DESC
            LIMIT 10
        """)

        for row in cur.fetchall():
            print(f"  [{row[0]}] {row[1]} - {row[2]}")

        conn.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
