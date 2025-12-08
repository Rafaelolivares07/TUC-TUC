import sqlite3

sql_script = """
-- Agregar campo estado a tabla EXISTENCIAS
ALTER TABLE existencias 
ADD COLUMN estado TEXT NOT NULL DEFAULT 'pendiente';
"""

try:
    conn = sqlite3.connect('medicamentos.db')
    conn.executescript(sql_script)
    conn.commit()
    print("✅ Campo 'estado' agregado a tabla EXISTENCIAS")
    print("   Valor por defecto: 'pendiente'")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")