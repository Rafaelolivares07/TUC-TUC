import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("SELECT * FROM movimientos_inventario WHERE id = 1896;")
row = cur.fetchone()
print("Movimiento 1896:", row)

cur.close()
conn.close()
