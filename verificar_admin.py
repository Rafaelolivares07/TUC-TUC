# Script TEMPORAL para verificar la tabla USUARIOS
import sqlite3

# Asegúrate de que este path sea correcto si no estás en el mismo directorio
conn = sqlite3.connect('medicamentos.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n--- CONTENIDO DE USUARIOS TRAS INICIALIZACIÓN ---")
usuarios = cursor.execute("SELECT id, dispositivo_id, nombre, rol, fecha_registro FROM USUARIOS").fetchall()

for u in usuarios:
    print(f"ID: {u['id']} | DISP_ID: {u['dispositivo_id']} | Nombre: {u['nombre']} | Rol: {u['rol']}")

conn.close()
print("--------------------------------------------------\n")