import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@localhost:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

cur.execute("""
    SELECT id, nombre, negocio_id, categoria, precio, costo
    FROM productos
    WHERE nombre ILIKE '%BONDIOLA%' OR nombre ILIKE '%CARNE%CERDO%';
""")
print("PRODUCTOS:")
for p in cur.fetchall():
    print(dict(p))

conn.close()
