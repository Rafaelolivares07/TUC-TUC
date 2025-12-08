import sqlite3

# Conexión a tu base de datos existente
conexion = sqlite3.connect("medicamentos.db")
cursor = conexion.cursor()

# Agregar el campo si no existe
try:
    cursor.execute("ALTER TABLE precios ADD COLUMN stock_fabricante INTEGER DEFAULT 0")
    print("✅ Campo 'stock_fabricante' agregado exitosamente a la tabla 'precios'.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("ℹ️ El campo 'stock_fabricante' ya existe en la tabla 'precios'.")
    else:
        raise e

conexion.commit()
conexion.close()
