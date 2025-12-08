import sqlite3
import os

# --- Configuración ---
# Asegúrate de que esta ruta apunte a tu archivo de base de datos
DB_NAME = 'medicamentos.db' 
# Nombre del usuario que quieres limpiar, ej: 'Laura Pérez'
USUARIO_A_ELIMINAR = 'Laura Pérez' 
# ---------------------

def get_db_connection():
    """Establece la conexión a la base de datos."""
    if not os.path.exists(DB_NAME):
        print(f"🚨 ERROR: No se encontró el archivo de base de datos '{DB_NAME}'.")
        return None
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def reset_test_user(user_name):
    """Elimina un usuario de prueba de la tabla USUARIOS."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()
        
        # 1. Ejecutar la eliminación
        cursor.execute("DELETE FROM USUARIOS WHERE nombre = ?", (user_name,))
        
        # 2. Verificar cuántas filas fueron afectadas
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            print(f"\n✅ ÉXITO: Usuario '{user_name}' ({deleted_count} fila(s)) eliminado(s) de USUARIOS.")
        else:
            print(f"\n⚠️ AVISO: No se encontró al usuario '{user_name}' en la tabla USUARIOS para eliminar.")
            
    except sqlite3.Error as e:
        print(f"\n🚨 ERROR de SQLite al eliminar usuario: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("--- UTILIDAD DE LIMPIEZA DE USUARIO DE PRUEBA ---")
    reset_test_user(USUARIO_A_ELIMINAR)
    print("-------------------------------------------------")
