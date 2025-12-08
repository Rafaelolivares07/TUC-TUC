import sqlite3

try:
    conn = sqlite3.connect('medicamentos.db')

    # Agregar campo url a la tabla precios_competencia
    conn.execute("ALTER TABLE precios_competencia ADD COLUMN url TEXT")

    conn.commit()
    print("Campo 'url' agregado exitosamente a la tabla precios_competencia")
    conn.close()
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("El campo 'url' ya existe en la tabla precios_competencia")
    else:
        print(f"Error: {e}")
except Exception as e:
    print(f"Error inesperado: {e}")
