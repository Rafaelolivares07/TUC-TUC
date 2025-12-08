import sqlite3

def crear_tabla():
    conn = sqlite3.connect("medicamentos.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS precios_competencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicamento_id INTEGER NOT NULL,
            competidor TEXT NOT NULL,
            precio REAL NOT NULL,
            fecha_actualizacion TEXT NOT NULL,
            fuente_url TEXT,
            observaciones TEXT,
            imagen TEXT,
            FOREIGN KEY(medicamento_id) REFERENCES medicamentos(id)
        );
    """)

    conn.commit()
    conn.close()
    print("✅ Tabla 'precios_competencia' creada correctamente o ya existía.")

if __name__ == "__main__":
    crear_tabla()
