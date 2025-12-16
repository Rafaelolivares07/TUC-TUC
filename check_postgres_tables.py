"""Script para verificar las tablas en PostgreSQL"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

database_url = os.getenv('DATABASE_URL')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(database_url)
cursor = conn.cursor()

# Listar todas las tablas
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")

tables = cursor.fetchall()

print(f"Tablas en PostgreSQL: {len(tables)}")
for table in tables:
    print(f"  - {table[0]}")

# Verificar específicamente la tabla USUARIOS
print("\n--- Verificando tabla USUARIOS ---")
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'usuarios';
""")
usuarios_exists = cursor.fetchone()

if usuarios_exists:
    print("✓ Tabla USUARIOS existe")
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    count = cursor.fetchone()[0]
    print(f"  Registros: {count}")
else:
    print("✗ Tabla USUARIOS NO existe")

cursor.close()
conn.close()
