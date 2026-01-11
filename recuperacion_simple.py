#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Recuperación Simple: Solo migra las relaciones MEDICAMENTO_SINTOMA
"""

import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Conectar a SQLite
sqlite_conn = sqlite3.connect('medicamentos.db')
sqlite_cursor = sqlite_conn.cursor()

# Conectar a PostgreSQL
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

pg_conn = psycopg2.connect(database_url)
pg_cursor = pg_conn.cursor()

print("Inicio de recuperacion...")

# Leer relaciones de SQLite
sqlite_cursor.execute("SELECT medicamento_id, sintoma_id FROM MEDICAMENTO_SINTOMA")
registros = sqlite_cursor.fetchall()

print(f"Registros en SQLite: {len(registros)}")

# Migrar cada relacion
insertados = 0
ya_existian = 0

for med_id, sint_id in registros:
    # Verificar si existe
    pg_cursor.execute(
        'SELECT 1 FROM "MEDICAMENTO_SINTOMA" WHERE medicamento_id = %s AND sintoma_id = %s',
        (med_id, sint_id)
    )
    existe = pg_cursor.fetchone()

    if existe:
        ya_existian += 1
    else:
        try:
            pg_cursor.execute(
                'INSERT INTO "MEDICAMENTO_SINTOMA" (medicamento_id, sintoma_id) VALUES (%s, %s)',
                (med_id, sint_id)
            )
            insertados += 1
            if insertados % 100 == 0:
                print(f"Insertados: {insertados}")
        except Exception as e:
            print(f"Error en ({med_id}, {sint_id}): {e}")

pg_conn.commit()

print(f"\nRESULTADO:")
print(f"Insertados: {insertados}")
print(f"Ya existian: {ya_existian}")
print(f"Total: {insertados + ya_existian}")

sqlite_conn.close()
pg_conn.close()
