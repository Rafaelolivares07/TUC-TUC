# -*- coding: utf-8 -*-
import psycopg2
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Conectar a la base de datos PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    # Usar URL de producción directamente
    DATABASE_URL = 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc'
    print("Usando DATABASE_URL de produccion")

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    print("OK - Conectado a PostgreSQL")

    # Crear secuencia para terceros si no existe
    print("\nCreando secuencia terceros_id_seq...")
    cursor.execute('CREATE SEQUENCE IF NOT EXISTS terceros_id_seq')

    # Configurar la columna id para usar la secuencia
    print("Configurando columna id para usar la secuencia...")
    cursor.execute("ALTER TABLE terceros ALTER COLUMN id SET DEFAULT nextval('terceros_id_seq')")

    # Obtener el MAX id actual de la tabla
    cursor.execute('SELECT COALESCE(MAX(id), 0) FROM terceros')
    max_id = cursor.fetchone()[0]
    print(f"MAX ID actual en terceros: {max_id}")

    # Sincronizar la secuencia con el valor actual
    print(f"Sincronizando secuencia al valor {max_id}...")
    cursor.execute(f"SELECT setval('terceros_id_seq', {max_id})")

    # Confirmar cambios
    conn.commit()
    print("\nOK - Secuencia terceros_id_seq creada y sincronizada exitosamente")

    # Verificar
    cursor.execute("SELECT nextval('terceros_id_seq')")
    next_val = cursor.fetchone()[0]
    print(f"OK - Proximo ID que se asignara: {next_val}")

    # Revertir el nextval que acabamos de consumir
    cursor.execute(f"SELECT setval('terceros_id_seq', {max_id})")
    conn.commit()

    cursor.close()
    conn.close()

    print("\nProceso completado! Ahora puedes crear nuevos terceros sin errores.")

except Exception as e:
    print(f"\nError: {e}")
    if 'conn' in locals():
        conn.rollback()
