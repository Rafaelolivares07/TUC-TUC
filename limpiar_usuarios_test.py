import sqlite3

# Nombre de la base de datos que usa tu aplicación
DB_NAME = 'project.db' 

def get_db_connection():
    """Conexión simple a SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def clear_users_table():
    """Vacía completamente la tabla de usuarios."""
    try:
        with get_db_connection() as conn:
            # Comando SQL para eliminar todos los registros
            conn.execute("DELETE FROM usuarios;") 
            conn.commit()
            print("\n=============================================")
            print("✅ TABLA 'USUARIOS' VACIADA EXITOSAMENTE PARA PRUEBAS.")
            print("=============================================\n")
    except Exception as e:
        print(f"\n❌ ERROR al vaciar la tabla: {e}")
        print("Asegúrate de que '1_medicamentos.py' no esté en ejecución.")

if __name__ == '__main__':
    clear_users_table()