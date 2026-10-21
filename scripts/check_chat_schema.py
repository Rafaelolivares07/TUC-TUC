import sys, os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
sys.path.insert(0, '/home/ubuntu/tuctucv2')

import app.db as db_mod
db_mod._db_url = os.environ.get('DATABASE_URL')
from app.db import get_db_connection

conn = get_db_connection()
try:
    cols_cu = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='centros_utilidad'").fetchall()
    print('centros_utilidad cols:', [(c['column_name'], c['data_type']) for c in cols_cu])
    
    cols_rest = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='restaurantes'").fetchall()
    print('restaurantes cols:', [c['column_name'] for c in cols_rest if 'centro' in c['column_name'] or 'limite' in c['column_name'] or 'cupo' in c['column_name']])

    cols_tienda = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='tiendas'").fetchall()
    print('tiendas cols:', [c['column_name'] for c in cols_tienda if 'centro' in c['column_name'] or 'limite' in c['column_name'] or 'cupo' in c['column_name']])
finally:
    conn.close()
