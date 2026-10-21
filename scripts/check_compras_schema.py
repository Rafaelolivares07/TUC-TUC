import sys, os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
sys.path.insert(0, '/home/ubuntu/tuctucv2')

import app.db as db_mod
db_mod._db_url = os.environ.get('DATABASE_URL')
from app.db import get_db_connection

conn = get_db_connection()
try:
    rows = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE '%%compra%%' OR table_name LIKE '%%orden%%' OR table_name LIKE '%%tercero%%')").fetchall()
    print('Tables:', [r['table_name'] for r in rows])
    
    rows = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='terceros'").fetchall()
    print('Terceros cols:', [(r['column_name'], r['data_type']) for r in rows])

    rows = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='productos' AND (column_name LIKE '%%peso%%' OR column_name LIKE '%%tolerancia%%' OR column_name LIKE '%%stock%%')").fetchall()
    print('Productos cols:', [(r['column_name'], r['data_type']) for r in rows])
finally:
    conn.close()
