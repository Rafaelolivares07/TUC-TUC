import sys
sys.path.append('/home/ubuntu/tuctucv2')
from app import create_app
from app.db import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE pedido_validaciones_flash ADD COLUMN IF NOT EXISTS motivo VARCHAR(255);")
        conn.commit()
        print("Column motivo added to pedido_validaciones_flash successfully!")
    except Exception as e:
        print("Error adding column:", e)
    finally:
        conn.close()
