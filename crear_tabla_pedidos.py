import sqlite3

sql_script = """
-- 1) CREAR TABLA PEDIDOS
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_tercero INTEGER NOT NULL,
    fecha TEXT NOT NULL DEFAULT (datetime('now')),
    total REAL NOT NULL,
    metodo_pago TEXT NOT NULL,
    costo_domicilio REAL NOT NULL DEFAULT 0,
    direccion_entrega TEXT NOT NULL,
    latitud_entrega REAL,
    longitud_entrega REAL,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    notas TEXT,
    tiempo_estimado_entrega TEXT DEFAULT '30 minutos',
    FOREIGN KEY (id_tercero) REFERENCES terceros(id)
);

-- 2) RECREAR EXISTENCIAS sin campo estado y con pedido_id
-- (SQLite no soporta DROP COLUMN en versiones antiguas)

-- Crear tabla temporal con nueva estructura
CREATE TABLE existencias_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicamento_id INTEGER NOT NULL,
    fabricante_id INTEGER NOT NULL,
    tipo_movimiento TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    id_tercero INTEGER NOT NULL,
    pedido_id INTEGER,
    FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id),
    FOREIGN KEY (fabricante_id) REFERENCES fabricantes(id),
    FOREIGN KEY (id_tercero) REFERENCES terceros(id),
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
);

-- Copiar datos existentes (si los hay)
INSERT INTO existencias_new (id, medicamento_id, fabricante_id, tipo_movimiento, cantidad, fecha, id_tercero)
SELECT id, medicamento_id, fabricante_id, tipo_movimiento, cantidad, fecha, id_tercero
FROM existencias;

-- Eliminar tabla vieja
DROP TABLE existencias;

-- Renombrar nueva tabla
ALTER TABLE existencias_new RENAME TO existencias;
"""

try:
    conn = sqlite3.connect('medicamentos.db')
    conn.executescript(sql_script)
    conn.commit()
    print("✅ Tabla PEDIDOS creada exitosamente")
    print("✅ Campo 'estado' eliminado de EXISTENCIAS")
    print("✅ Campo 'pedido_id' agregado a EXISTENCIAS")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")