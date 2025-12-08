import sqlite3

# Asegúrate de que esta ruta sea correcta
DB_FILE = "medicamentos.db"

def print_db_schema(db_file):
    print(f"--- ESQUEMA DE LA BASE DE DATOS: {db_file} ---")
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Consulta para obtener los nombres de todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            print(f"\n[TABLA: {table_name}]")
            
            # Consulta para obtener el esquema (CREATE TABLE statement)
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            create_statement = cursor.fetchone()[0]
            print(create_statement)
            
        conn.close()
    except sqlite3.Error as e:
        print(f"Error al conectar o consultar la base de datos: {e}")

if __name__ == "__main__":
    print_db_schema(DB_FILE)