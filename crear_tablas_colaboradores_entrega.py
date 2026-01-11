#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para crear tablas de colaboradores de entrega
- colaboradores_entrega: Repartidores vinculados a terceros
- sesiones_colaboradores: Tracking de sesiones activas para calcular rutas
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

def crear_tablas():
    print("=" * 80)
    print("CREACIÓN DE TABLAS PARA SISTEMA DE ENTREGAS")
    print("=" * 80)

    conn = get_pg_conn()
    cursor = conn.cursor()

    try:
        # Tabla: colaboradores_entrega
        print("\n1. Creando tabla colaboradores_entrega...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS colaboradores_entrega (
                id SERIAL PRIMARY KEY,
                tercero_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                fecha_creacion TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(tercero_id)
            )
        """)
        print("   OK Tabla colaboradores_entrega creada")

        # Tabla: sesiones_colaboradores
        print("\n2. Creando tabla sesiones_colaboradores...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sesiones_colaboradores (
                id SERIAL PRIMARY KEY,
                colaborador_id INTEGER NOT NULL REFERENCES colaboradores_entrega(id) ON DELETE CASCADE,
                login_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                logout_timestamp TIMESTAMP,
                ultima_actividad TIMESTAMP NOT NULL DEFAULT NOW(),
                estado VARCHAR(20) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo'))
            )
        """)
        print("   OK Tabla sesiones_colaboradores creada")

        # Índices para optimizar consultas
        print("\n3. Creando índices...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_colaboradores_activos
            ON colaboradores_entrega(activo) WHERE activo = TRUE
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sesiones_activas
            ON sesiones_colaboradores(estado, logout_timestamp, ultima_actividad)
            WHERE estado = 'activo' AND logout_timestamp IS NULL
        """)
        print("   OK Indices creados")

        conn.commit()

        print("\n" + "=" * 80)
        print("TABLAS CREADAS EXITOSAMENTE")
        print("=" * 80)
        print("\nTablas creadas:")
        print("  - colaboradores_entrega: Gestión de repartidores")
        print("  - sesiones_colaboradores: Tracking de sesiones activas")
        print("\nPróximos pasos:")
        print("  1. Agregar colaboradores desde admin/parametros")
        print("  2. Sistema registrará automáticamente sesiones al login")
        print("  3. Número de rutas = colaboradores con sesión activa")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    crear_tablas()
