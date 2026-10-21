import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
from app.db import get_db_connection, init_db

init_db(None)
conn = get_db_connection()
tables = [r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;").fetchall()]
print("TODAS LAS TABLAS:", tables)
