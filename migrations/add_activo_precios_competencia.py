import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("Agregando campos activo e inactivo_hasta a tabla precios_competencia...")

# Agregar campo activo (por defecto TRUE - cotización activa)
cur.execute("ALTER TABLE precios_competencia ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE")

# Agregar campo inactivo_hasta (NULL = no está inactiva, o fecha hasta cuando está inactiva)
cur.execute("ALTER TABLE precios_competencia ADD COLUMN IF NOT EXISTS inactivo_hasta TIMESTAMP")

conn.commit()
print("Migración completada exitosamente")
conn.close()
