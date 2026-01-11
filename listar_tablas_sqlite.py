#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Lista todas las tablas de cada base de datos SQLite
"""

import sqlite3
import os

bases_datos = ['medicamentos.db', 'farmacia.db', 'tuc_tuc.db', 'medicamentos_backup.db']

for db_name in bases_datos:
    db_path = f'c:\\Users\\RAFAEL OLIVARES\\Documents\\MiAppMedicamentos\\{db_name}'

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tablas = cursor.fetchall()

            print(f"\n{db_name}:")
            print(f"  Tablas ({len(tablas)}):")
            for tabla in tablas:
                # Contar registros
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {tabla[0]}")
                    count = cursor.fetchone()[0]
                    print(f"    - {tabla[0]}: {count} registros")
                except:
                    print(f"    - {tabla[0]}: ERROR al contar")

            conn.close()
        except Exception as e:
            print(f"\n{db_name}: ERROR - {e}")
