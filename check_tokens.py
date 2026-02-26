import os, psycopg2, psycopg2.extras
try:
    with open('.env','r') as f:
        for l in f:
            l=l.strip()
            if l and not l.startswith('#') and '=' in l:
                k,v=l.split('=',1)
                os.environ[k.strip()]=v.strip()
except: pass
url=os.getenv('DATABASE_URL','').replace('postgres://','postgresql://',1)
conn=psycopg2.connect(url)
cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Crear columna push_token en USUARIOS si no existe
try:
    cur.execute('ALTER TABLE "USUARIOS" ADD COLUMN IF NOT EXISTS push_token TEXT')
    conn.commit()
    print("Columna push_token creada en USUARIOS")
except Exception as e:
    conn.rollback()
    print(f"Error creando columna: {e}")

# Verificar terceros
print("\n=== TERCEROS ===")
cur.execute("SELECT id, nombre, push_token FROM terceros WHERE id IN (43, 16, 3) ORDER BY id")
for r in cur.fetchall():
    token = r['push_token']
    print(f"  ID {r['id']} | {r['nombre']} | {('SI: ' + token[:40] + '...') if token else 'NO'}")

# Verificar USUARIOS
print('\n=== USUARIOS con push_token ===')
cur.execute('SELECT id, nombre, push_token FROM "USUARIOS" WHERE push_token IS NOT NULL ORDER BY id')
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  ID {r['id']} | {r['nombre']} | token: {r['push_token'][:40]}...")
else:
    print("  Ninguno tiene push_token (columna existe pero vacía)")

conn.close()
