import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://', 1)

conn = psycopg2.connect(database_url)
cursor = conn.cursor()

# Verificar si existe una secuencia para MEDICAMENTOS.id
cursor.execute("""
    SELECT column_default 
    FROM information_schema.columns 
    WHERE table_name = 'MEDICAMENTOS' 
    AND column_name = 'id'
""")
result = cursor.fetchone()
print(f"Default actual para MEDICAMENTOS.id: {result}")

# Crear secuencia si no existe
cursor.execute("""
    CREATE SEQUENCE IF NOT EXISTS medicamentos_id_seq;
""")

# Asignar la secuencia como default
cursor.execute("""
    ALTER TABLE "MEDICAMENTOS" 
    ALTER COLUMN id SET DEFAULT nextval('medicamentos_id_seq');
""")

# Actualizar la secuencia al valor máximo actual
cursor.execute("""
    SELECT setval('medicamentos_id_seq', COALESCE((SELECT MAX(id) FROM "MEDICAMENTOS"), 1));
""")

conn.commit()
print("✓ Secuencia creada y configurada correctamente")

# Verificar nuevamente
cursor.execute("""
    SELECT column_default 
    FROM information_schema.columns 
    WHERE table_name = 'MEDICAMENTOS' 
    AND column_name = 'id'
""")
result = cursor.fetchone()
print(f"Default después del fix: {result}")

cursor.close()
conn.close()
