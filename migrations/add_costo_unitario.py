import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("Agregando campo costo_unitario a tabla existencias...")
cur.execute("ALTER TABLE existencias ADD COLUMN IF NOT EXISTS costo_unitario DECIMAL(10,2) DEFAULT 0")

print("Agregando campo costo_unitario a tabla precios...")
cur.execute("ALTER TABLE precios ADD COLUMN IF NOT EXISTS costo_unitario DECIMAL(10,2) DEFAULT 0")

conn.commit()
print("Migración completada exitosamente")
conn.close()
