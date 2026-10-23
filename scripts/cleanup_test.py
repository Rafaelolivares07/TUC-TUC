import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.db import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    conn.execute("DELETE FROM pedido_validaciones_flash WHERE pedido_id = 999999")
    conn.commit()
    conn.close()
    print("DELETED OK")
