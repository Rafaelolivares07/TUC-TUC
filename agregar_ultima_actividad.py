#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migración: Agregar columna ultima_actividad a sesiones_colaboradores
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_pg_conn():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(database_url)

def agregar_columna():
    print("=" * 80)
    print("MIGRACION: Agregar ultima_actividad a sesiones_colaboradores")
    print("=" * 80)

    conn = get_pg_conn()
    cursor = conn.cursor()

    try:
        # Verificar si columna existe
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sesiones_colaboradores'
            AND column_name = 'ultima_actividad'
        """)

        existe = cursor.fetchone()

        if existe:
            print("\nColumna ultima_actividad ya existe. No hay cambios necesarios.")
        else:
            print("\nAgregando columna ultima_actividad...")
            cursor.execute("""
                ALTER TABLE sesiones_colaboradores
                ADD COLUMN ultima_actividad TIMESTAMP NOT NULL DEFAULT NOW()
            """)

            # Actualizar registros existentes
            cursor.execute("""
                UPDATE sesiones_colaboradores
                SET ultima_actividad = login_timestamp
                WHERE ultima_actividad IS NULL
            """)

            conn.commit()
            print("   OK Columna agregada y registros actualizados")

            # Recrear índice
            print("\nActualizando índice...")
            cursor.execute("DROP INDEX IF EXISTS idx_sesiones_activas")
            cursor.execute("""
                CREATE INDEX idx_sesiones_activas
                ON sesiones_colaboradores(estado, logout_timestamp, ultima_actividad)
                WHERE estado = 'activo' AND logout_timestamp IS NULL
            """)
            print("   OK Indice actualizado")
            conn.commit()

        print("\n" + "=" * 80)
        print("MIGRACION COMPLETA")
        print("=" * 80)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    agregar_columna()
