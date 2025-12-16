"""Script para verificar el nombre exacto de la tabla usuarios"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

database_url = os.getenv('DATABASE_URL')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(database_url)
cursor = conn.cursor()

# Buscar variaciones del nombre
for nombre in ['usuarios', 'USUARIOS', 'Usuarios']:
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND LOWER(table_name) = LOWER(%s);
    """, (nombre,))
    result = cursor.fetchone()
    if result:
        print(f"Nombre real de la tabla: {result[0]}")

        # Contar registros
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{result[0]}"')
            count = cursor.fetchone()[0]
            print(f"Registros en la tabla: {count}")
        except Exception as e:
            print(f"Error al contar: {e}")
        break

cursor.close()
conn.close()
