import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from app.db import init_db, get_db_connection

init_db(None)
conn = get_db_connection()

cur = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='USUARIOS';")
print('Columns of USUARIOS:', [r['column_name'] for r in cur.fetchall()])

cur2 = conn.execute('SELECT * FROM "USUARIOS" LIMIT 10;')
print('Rows of USUARIOS:')
for r in cur2.fetchall():
    print(r._data)

cur3 = conn.execute("SELECT id, nombre, telefono, email, es_empleado FROM terceros WHERE nombre ILIKE %s;", ('%margarita%',))
print('Terceros matching margarita:')
for r in cur3.fetchall():
    print(r._data)

conn.close()
