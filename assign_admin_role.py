import sqlite3
import uuid

# El ID que necesitamos actualizar. ¡Copiado de tu DEBUG!
DISPOSITIVO_ID_ACTUAL = '9450a6a4-b506-421a-9de2-b37ab040747c'
DB_FILE = 'C:/Users/RAFAEL OLIVARES/Documents/MiAppMedicamentos/Medicamentos.db'  # Asegúrate que esta ruta sea la correcta

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def forzar_rol_administrador():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Encontrar el usuario_id asociado a ese dispositivo
        cursor.execute(
            "SELECT usuario_id FROM USUARIO_DISPOSITIVO WHERE dispositivo_id = ?", 
            (DISPOSITIVO_ID_ACTUAL,)
        )
        result = cursor.fetchone()
        
        if not result:
            print(f"🔴 ERROR: No se encontró ningún USUARIO vinculado al dispositivo ID: {DISPOSITIVO_ID_ACTUAL}")
            return

        usuario_id = result['usuario_id']

        # 2. Actualizar el campo 'rol' para ese usuario en la tabla 'USUARIOS'
        cursor.execute(
            "UPDATE USUARIOS SET rol = 'Admin' WHERE id = ?", 
            (usuario_id,)
        )

        conn.commit()
        print(f"✅ ÉXITO: El rol del usuario (ID: {usuario_id}) ha sido actualizado a 'Admin'.")

    except sqlite3.Error as e:
        print(f"❌ Error de base de datos: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    forzar_rol_administrador()
