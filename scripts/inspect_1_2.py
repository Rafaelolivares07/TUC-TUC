import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute('''
    SELECT * FROM movimientos_contables WHERE numero_documento IN ('1', '2') AND tipo_documento = 'GASTO_DE_ENTREGAS'
''')
for r in cur.fetchall():
    print(r)
