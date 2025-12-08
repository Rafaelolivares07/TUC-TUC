import sqlite3

# --- CAMBIA ESTE NOMBRE POR EL DE TU ARCHIVO DE BASE DE DATOS ---
DB_NAME = 'medicamentos.db' 
# ------------------------------------------------------------------

def mostrar_estructura_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Consulta para obtener una lista de todas las tablas y vistas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = cursor.fetchall()
        
        print(f"\n✅ Conectado a la base de datos: {DB_NAME}\n")
        
        if not tablas:
            print("❌ No se encontraron tablas en la base de datos.")
            return

        print("==============================================")
        print("         ESTRUCTURA DE LA BASE DE DATOS       ")
        print("==============================================")
        
        for tabla in tablas:
            nombre_tabla = tabla[0]
            print(f"\n>>> TABLA: {nombre_tabla.upper()} <<<")
            
            # Consulta para obtener los detalles de las columnas de la tabla
            cursor.execute(f"PRAGMA table_info({nombre_tabla});")
            columnas = cursor.fetchall()
            
            # Imprimir encabezados: (cid, name, type, notnull, dflt_value, pk)
            print("  - ID | NOMBRE_COLUMNA | TIPO_DATO | NO_NULO | CLAVE_PRIMARIA")
            print("  ---------------------------------------------------------")
            
            for col in columnas:
                # col[1] es el nombre, col[2] es el tipo, col[5] es pk
                pk = 'Sí' if col[5] else 'No'
                notnull = 'Sí' if col[3] else 'No'
                print(f"  {col[0]:>3} | {col[1]:<14} | {col[2]:<9} | {notnull:<7} | {pk:<14}")
                
        print("\n==============================================")

    except sqlite3.Error as e:
        print(f"❌ Error al conectar o consultar la base de datos: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    mostrar_estructura_db()