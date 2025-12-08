import sqlite3

# SQL de actualización
sql_script = """
-- CREAR TABLA TERCEROS
CREATE TABLE IF NOT EXISTS terceros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    telefono TEXT,
    direccion TEXT,
    latitud REAL,
    longitud REAL,
    id_usuario INTEGER,
    fecha_creacion TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
);

-- CREAR TABLA NAVEGACION_ANONIMA
CREATE TABLE IF NOT EXISTS navegacion_anonima (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispositivo_id TEXT NOT NULL,
    fecha_hora TEXT NOT NULL DEFAULT (datetime('now')),
    url_visitada TEXT NOT NULL,
    UNIQUE(dispositivo_id)
);

-- MODIFICAR TABLA EXISTENCIAS
ALTER TABLE existencias 
ADD COLUMN id_tercero INTEGER NOT NULL DEFAULT 0;
"""

try:
    conn = sqlite3.connect('medicamentos.db')
    conn.executescript(sql_script)
    conn.commit()
    print("✅ Base de datos actualizada exitosamente")
    print("✅ Tabla TERCEROS creada")
    print("✅ Tabla NAVEGACION_ANONIMA creada")
    print("✅ Campo id_tercero agregado a EXISTENCIAS")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")