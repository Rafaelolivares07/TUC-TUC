import sqlite3
import os
from datetime import datetime # Importación movida a la parte superior

# Nombre de la base de datos
DB_NAME = 'medicamentos.db'

# 🚨 CAMBIA ESTE VALOR 🚨
# Debes obtener el 'dispositivo_id' de las cookies de tu navegador.
TU_DISPOSITIVO_ID_ACTUAL = "9450a6a4-b506-421a-9de2-b37ab040747c" 

# El ID del usuario Admin Master que se insertó en data_initializer.py
ADMIN_MASTER_ID = 1

def vincular_dispositivo_a_admin(dispositivo_id):
    """
    Vincula el Dispositivo ID del navegador al usuario 'Admin Master' (ID 1).
    Esto simula que ya se registró como administrador.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        # 🔑 CLAVE: Configurar row_factory para acceder a las columnas por nombre
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # 1. Eliminar cualquier vínculo existente para este dispositivo
        cursor.execute("DELETE FROM USUARIO_DISPOSITIVO WHERE dispositivo_id = ?", (dispositivo_id,))
        
        # 2. Verificar que el usuario Admin Master exista
        cursor.execute("SELECT nombre FROM USUARIOS WHERE id = ?", (ADMIN_MASTER_ID,))
        admin_row = cursor.fetchone()
        
        if not admin_row:
            print(f"🚨 ERROR: No se encontró el usuario 'Admin Master' con ID {ADMIN_MASTER_ID}. Asegúrate de que app.py se haya ejecutado al menos una vez.")
            return

        # 3. Insertar el nuevo vínculo Admin-Dispositivo
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            """
            INSERT INTO USUARIO_DISPOSITIVO (usuario_id, dispositivo_id, fecha_vinculacion)
            VALUES (?, ?, ?)
            """, 
            (ADMIN_MASTER_ID, dispositivo_id, fecha_actual)
        )
        
        conn.commit()
        # El acceso por nombre 'nombre' ahora funciona gracias a row_factory
        print(f"✅ Dispositivo vinculado con éxito al Admin Master ('{admin_row['nombre']}').") 
        print("Ahora, recarga la ruta / en tu navegador para probar la redirección a /admin.")
        
    except sqlite3.Error as e:
        print(f"🚨 ERROR de SQLite: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"🚨 Ocurrió un error inesperado: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    # TU_DISPOSITIVO_ID_ACTUAL ya está actualizado en el código que pegaste
    vincular_dispositivo_a_admin(TU_DISPOSITIVO_ID_ACTUAL)
