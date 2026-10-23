import sys
sys.path.append('/home/ubuntu/tuctucv2')
from app import create_app
from app.db import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pedido_validaciones_flash (
                id SERIAL PRIMARY KEY,
                pedido_id INT,
                numero_documento VARCHAR(100),
                restaurante_id INT,
                tienda_id INT,
                cajero VARCHAR(150),
                resultado VARCHAR(20) NOT NULL,
                items_resumen TEXT,
                total NUMERIC(15,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("Table pedido_validaciones_flash created successfully!")
    except Exception as e:
        print("Error creating table:", e)
    finally:
        conn.close()
