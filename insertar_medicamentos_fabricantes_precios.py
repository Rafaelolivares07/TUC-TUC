import pandas as pd
import sqlite3

# === CONFIGURACIÓN ===
DB_PATH = "medicamentos.db"
ARCHIVO_ODS = "C:/Users/RAFAEL OLIVARES/Documents/medicamentos.ods"

# === LEER ARCHIVO ===
df = pd.read_excel(ARCHIVO_ODS, engine="odf")

# Normalizar nombres de columnas
df.columns = [col.strip().lower() for col in df.columns]
print("Columnas detectadas:", df.columns)

# Si tus columnas se llaman diferente, ajusta aquí:
col_med = "medicamento"
col_fab = "fabricante"

# === CONECTAR A LA BASE DE DATOS ===
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# === ASEGURAR QUE LA TABLA PRECIOS EXISTE ===
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

# === PROCESAR FILAS ===
for _, fila in df.iterrows():
    nombre_med = str(fila[col_med]).strip()
    nombre_fab = str(fila[col_fab]).strip()

    if not nombre_med or not nombre_fab:
        continue  # saltar filas vacías

    # --- Insertar fabricante si no existe ---
    cursor.execute("SELECT id FROM FABRICANTES WHERE nombre = ?", (nombre_fab,))
    fab = cursor.fetchone()
    if fab:
        fab_id = fab[0]
    else:
        cursor.execute("INSERT INTO FABRICANTES (nombre) VALUES (?)", (nombre_fab,))
        fab_id = cursor.lastrowid

    # --- Insertar medicamento si no existe ---
    cursor.execute("SELECT id FROM MEDICAMENTOS WHERE nombre = ?", (nombre_med,))
    med = cursor.fetchone()
    if med:
        med_id = med[0]
    else:
        cursor.execute(
            "INSERT INTO MEDICAMENTOS (nombre, activo, stock_actual) VALUES (?, ?, ?)",
            (nombre_med, 1, 0)
        )
        med_id = cursor.lastrowid

    # --- Crear relación en EXISTENCIAS ---
    cursor.execute("""
        SELECT id FROM EXISTENCIAS
        WHERE medicamento_id = ? AND fabricante_id = ?
    """, (med_id, fab_id))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO EXISTENCIAS
            (medicamento_id, fabricante_id, tipo_movimiento, cantidad, fecha)
            VALUES (?, ?, ?, ?, DATE('now'))
        """, (med_id, fab_id, 'inicial', 0))

    # --- Crear relación en PRECIOS ---
    cursor.execute("""
        SELECT id FROM PRECIOS
        WHERE medicamento_id = ? AND fabricante_id = ?
    """, (med_id, fab_id))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO PRECIOS
            (medicamento_id, fabricante_id, precio)
            VALUES (?, ?, 0)
        """, (med_id, fab_id))

conn.commit()
conn.close()

print("\n✅ Proceso completado:")
print("   - Medicamentos y fabricantes insertados/actualizados.")
print("   - Relaciones creadas en EXISTENCIAS y PRECIOS (precio=0).")
