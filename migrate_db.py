# migrate_db.py
import sqlite3
import os

DB = "medicamentos.db"

def backup_exists():
    return os.path.exists(DB)

print("Usando base de datos:", DB)
if not os.path.exists(DB):
    print("No existe la DB, se creará nueva:", DB)

conn = sqlite3.connect(DB)
c = conn.cursor()

# Activar foreign keys (útil)
c.execute("PRAGMA foreign_keys = ON;")

print("\n--- Creando tablas (si no existen) ---\n")

# Tabla medicamentos (no la sobreescribimos)
c.execute("""
CREATE TABLE IF NOT EXISTS medicamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    presentacion TEXT,
    concentracion TEXT,
    fabricante TEXT,
    imagen TEXT
)
""")

# Tabla sintomas
c.execute("""
CREATE TABLE IF NOT EXISTS sintomas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion TEXT NOT NULL
)
""")

# Tabla diagnosticos
c.execute("""
CREATE TABLE IF NOT EXISTS diagnosticos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion TEXT NOT NULL
)
""")

# Tabla diagnostico_medicamento (relación many-to-many)
c.execute("""
CREATE TABLE IF NOT EXISTS diagnostico_medicamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnostico_id INTEGER NOT NULL,
    medicamento_id INTEGER NOT NULL,
    FOREIGN KEY (diagnostico_id) REFERENCES diagnosticos(id) ON DELETE CASCADE,
    FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id) ON DELETE CASCADE
)
""")

# Tabla diagnostico_sintoma (relación many-to-many)
c.execute("""
CREATE TABLE IF NOT EXISTS diagnostico_sintoma (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnostico_id INTEGER NOT NULL,
    sintoma_id INTEGER NOT NULL,
    FOREIGN KEY (diagnostico_id) REFERENCES diagnosticos(id) ON DELETE CASCADE,
    FOREIGN KEY (sintoma_id) REFERENCES sintomas(id) ON DELETE CASCADE
)
""")

conn.commit()

# Mostrar estado (tablas y columnas)
print("Tablas actuales:")
c.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = c.fetchall()
print(tables)

print("\nColumnas por tabla:")
for t in ["medicamentos","sintomas","diagnosticos","diagnostico_medicamento","diagnostico_sintoma"]:
    c.execute(f"PRAGMA table_info({t});")
    cols = c.fetchall()
    print(f"\n{t}:")
    for col in cols:
        print("  ", col)

conn.close()
print("\nMigración finalizada. Si todo está ok, reinicia tu app (python app.py).")
