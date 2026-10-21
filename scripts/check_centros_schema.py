import sys, os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
sys.path.insert(0, '/home/ubuntu/tuctucv2')

import app.db as db_mod
db_mod._db_url = os.environ.get('DATABASE_URL')
from app.db import get_db_connection

conn = get_db_connection()
cols = conn.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'centros_utilidad'").fetchall()
print("centros_utilidad columns:")
for c in cols:
    print(" -", c['column_name'], c['data_type'], c['column_default'])

cols2 = conn.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'usuarios_centros_utilidad'").fetchall()
print("usuarios_centros_utilidad columns:")
for c in cols2:
    print(" -", c['column_name'], c['data_type'], c['column_default'])
conn.close()
