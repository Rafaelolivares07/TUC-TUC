import sys, os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
sys.path.insert(0, '/home/ubuntu/tuctucv2')

import app.db as db_mod
db_mod._db_url = os.environ.get('DATABASE_URL')
from app.db import get_db_connection

def migrate():
    conn = get_db_connection()
    try:
        print("1. Agregando max_centros_utilidad a restaurantes...")
        conn.execute("ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS max_centros_utilidad INTEGER DEFAULT 1")
        
        print("2. Agregando max_centros_utilidad a tiendas...")
        conn.execute("ALTER TABLE tiendas ADD COLUMN IF NOT EXISTS max_centros_utilidad INTEGER DEFAULT 1")

        print("3. Asegurando columnas direccion y telefono en centros_utilidad...")
        conn.execute("ALTER TABLE centros_utilidad ADD COLUMN IF NOT EXISTS telefono VARCHAR(50)")
        conn.execute("ALTER TABLE centros_utilidad ADD COLUMN IF NOT EXISTS direccion TEXT")

        conn.commit()
        print("Migración de centros de utilidad completada con éxito.")
    except Exception as e:
        conn.rollback()
        print("Error en migración:", e)
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
