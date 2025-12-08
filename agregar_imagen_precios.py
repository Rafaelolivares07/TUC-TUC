import sqlite3

sql_script = """
-- Agregar campo imagen a tabla PRECIOS
ALTER TABLE precios 
ADD COLUMN imagen TEXT;
"""

try:
    conn = sqlite3.connect('medicamentos.db')
    conn.executescript(sql_script)
    conn.commit()
    print("✅ Campo 'imagen' agregado a tabla PRECIOS")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")