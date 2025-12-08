import sqlite3
from datetime import datetime

try:
    conn = sqlite3.connect('medicamentos.db')

    # Agregar campo fecha_actualizacion sin valor por defecto
    conn.execute("ALTER TABLE terceros ADD COLUMN fecha_actualizacion TEXT")

    # Actualizar registros existentes con la fecha actual
    fecha_actual = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("UPDATE terceros SET fecha_actualizacion = ?", (fecha_actual,))

    conn.commit()
    print("Campo fecha_actualizacion agregado a tabla TERCEROS")
    print("Registros existentes actualizados con fecha actual")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
