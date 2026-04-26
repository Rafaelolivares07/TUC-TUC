import psycopg2
from werkzeug.security import generate_password_hash

DB_URL = "postgresql://tuctuc_user:yG04kXspSIiuHtc6QeW96CFJbm0ICtvt@dpg-d4s28pje5dus7395rd90-a.virginia-postgres.render.com/tuctuc"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Ver estructura USUARIOS
cur.execute('SELECT column_name, data_type FROM information_schema.columns WHERE table_name=\'USUARIOS\' ORDER BY ordinal_position')
print("=== COLUMNAS USUARIOS ===")
for row in cur.fetchall():
    print(row)

# Ver registros
cur.execute('SELECT * FROM "USUARIOS" LIMIT 5')
print("\n=== REGISTROS (max 5) ===")
cols = [desc[0] for desc in cur.description]
print("Columnas:", cols)
for row in cur.fetchall():
    print(row)

conn.close()
