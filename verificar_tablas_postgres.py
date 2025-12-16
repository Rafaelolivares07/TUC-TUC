import psycopg2
import os

# URL de la base de datos
DATABASE_URL = 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc'

print("Conectando a PostgreSQL...\n")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Obtener todas las tablas
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

tablas = cursor.fetchall()

print(f"Total de tablas: {len(tablas)}\n")
print("Tablas en la base de datos:")
print("=" * 50)

for tabla in tablas:
    nombre_tabla = tabla[0]

    # Verificar si está en mayúsculas o minúsculas
    if nombre_tabla.isupper():
        print(f"[MAYUSCULAS] {nombre_tabla}")
    elif nombre_tabla.islower():
        print(f"[minusculas] {nombre_tabla}")
    else:
        print(f"[MixedCase]  {nombre_tabla}")

cursor.close()
conn.close()

print("\n" + "=" * 50)
print("Verificacion completada!")
