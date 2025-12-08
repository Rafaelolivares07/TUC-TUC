import sqlite3

DB_PATH = "medicamentos.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Crear la tabla PRECIOS si no existe
cursor.execute("""
CREATE TABLE IF NOT EXISTS PRECIOS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicamento_id INTEGER NOT NULL,
    fabricante_id INTEGER NOT NULL,
    precio REAL NOT NULL DEFAULT 0,
    fecha_actualizacion TEXT NOT NULL DEFAULT (DATE('now')),
    FOREIGN KEY (medicamento_id) REFERENCES MEDICAMENTOS(id),
    FOREIGN KEY (fabricante_id) REFERENCES FABRICANTES(id)
)
""")

conn.commit()
conn.close()
print("✅ Tabla 'PRECIOS' creada correctamente (si no existía).")
