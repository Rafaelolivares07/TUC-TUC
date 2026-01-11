#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verifica cuántos datos de medicamento_sintoma hay en SQLite vs PostgreSQL
"""

import sqlite3
import os

# Buscar la base de datos con más datos
bases_datos = [
    'medicamentos.db',
    'farmacia.db',
    'tuc_tuc.db',
    'medicamentos_backup.db'
]

print("Verificando bases de datos SQLite...\n")

for db_name in bases_datos:
    db_path = f'c:\\Users\\RAFAEL OLIVARES\\Documents\\MiAppMedicamentos\\{db_name}'

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Verificar si existe la tabla
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medicamento_sintoma'")
            tabla_existe = cursor.fetchone()

            if tabla_existe:
                # Contar registros
                cursor.execute("SELECT COUNT(*) FROM medicamento_sintoma")
                count = cursor.fetchone()[0]

                print(f"{db_name}:")
                print(f"  - Tabla medicamento_sintoma: EXISTE")
                print(f"  - Registros: {count}")

                if count > 0:
                    # Mostrar algunos ejemplos
                    cursor.execute("""
                        SELECT m.nombre, s.nombre
                        FROM medicamento_sintoma ms
                        JOIN medicamentos m ON m.id = ms.medicamento_id
                        JOIN sintomas s ON s.id = ms.sintoma_id
                        LIMIT 5
                    """)
                    ejemplos = cursor.fetchall()
                    print("  - Ejemplos:")
                    for med, sint in ejemplos:
                        print(f"    * {med} -> {sint}")

                print()
            else:
                print(f"{db_name}: Tabla medicamento_sintoma NO EXISTE\n")

            conn.close()

        except Exception as e:
            print(f"{db_name}: ERROR - {e}\n")
    else:
        print(f"{db_name}: Archivo no encontrado\n")

print("\n" + "="*60)
print("Ahora verifica en PostgreSQL cuantos registros hay")
print("="*60)
