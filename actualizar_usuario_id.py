#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualizar el ID del usuario administrador de 1 a 16
para que coincida con los medicamentos del pastillero
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

    print("="*60)
    print("ACTUALIZANDO USUARIO_ID DE 1 A 16")
    print("="*60)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # Verificar estado actual
    cur.execute('SELECT id, nombre FROM "USUARIOS" WHERE id = 1')
    usuario_1 = cur.fetchone()

    cur.execute('SELECT id, nombre FROM "USUARIOS" WHERE id = 16')
    usuario_16 = cur.fetchone()

    print("\nESTADO ACTUAL:")
    if usuario_1:
        print(f"  Usuario ID 1: {usuario_1[1]}")
    else:
        print("  Usuario ID 1: No existe")

    if usuario_16:
        print(f"  Usuario ID 16: {usuario_16[1]}")
    else:
        print("  Usuario ID 16: No existe")

    if not usuario_1:
        print("\nERROR: No existe usuario con ID 1")
        conn.close()
        return

    if usuario_16:
        print("\nADVERTENCIA: Ya existe un usuario con ID 16")
        print("Necesitamos eliminar o mover ese usuario primero")
        conn.close()
        return

    # Hacer el cambio
    print("\nActualizando usuario_id de 1 a 16...")
    cur.execute('UPDATE "USUARIOS" SET id = 16 WHERE id = 1')
    conn.commit()

    # Verificar
    cur.execute('SELECT id, nombre FROM "USUARIOS" WHERE id = 16')
    resultado = cur.fetchone()

    if resultado:
        print(f"\nOK Usuario actualizado exitosamente")
        print(f"  Nuevo ID: {resultado[0]}")
        print(f"  Nombre: {resultado[1]}")
        print("\nAhora tus medicamentos del pastillero deberan ser visibles!")
    else:
        print("\nERROR: Algo salio mal en la actualizacion")

    conn.close()

if __name__ == '__main__':
    main()
