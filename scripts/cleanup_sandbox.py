import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
from app.db import get_db_connection, init_db

init_db(None)
conn = get_db_connection()
conn.execute("DROP TABLE IF EXISTS movimientos_inventario_test CASCADE;")
conn.execute("DROP TABLE IF EXISTS movimientos_contables_test CASCADE;")
conn.commit()
print("Sandbox tables successfully dropped.")
