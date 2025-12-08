import sqlite3

try:
    conn = sqlite3.connect('medicamentos.db')
    cursor = conn.cursor()

    # Verificar si el campo usar_precio ya existe
    cursor.execute("PRAGMA table_info(CONFIGURACION_PRECIOS)")
    columnas = [col[1] for col in cursor.fetchall()]

    if 'usar_precio' not in columnas:
        # Agregar nuevo campo usar_precio
        cursor.execute("ALTER TABLE CONFIGURACION_PRECIOS ADD COLUMN usar_precio TEXT DEFAULT 'minimo'")

        # Copiar datos de base_escaso a usar_precio
        cursor.execute("UPDATE CONFIGURACION_PRECIOS SET usar_precio = base_escaso")

        conn.commit()
        print("Campo 'usar_precio' agregado y datos migrados desde 'base_escaso'")
    else:
        print("El campo 'usar_precio' ya existe")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
