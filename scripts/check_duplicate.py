import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@localhost:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

cur.execute("""
    SELECT id, nombre, negocio_id, categoria, precio, costo
    FROM productos
    WHERE nombre ILIKE '%PECHUGA%POLLO%50%' OR id = 320;
""")
print("PRODUCTOS ENCONTRADOS:")
prods = cur.fetchall()
pids = []
for p in prods:
    print(dict(p))
    pids.append(p['id'])

if pids:
    cur.execute("SELECT * FROM precios WHERE producto_id IN %s;", (tuple(pids),))
    print("\nREGISTROS EN 'precios':")
    for pr in cur.fetchall():
        print(dict(pr))

    cur.execute("SELECT producto_id, COUNT(*) as mov_count FROM movimientos_inventario WHERE producto_id IN %s GROUP BY producto_id;", (tuple(pids),))
    print("\nMOVIMIENTOS EN INVENTARIO:")
    for m in cur.fetchall():
        print(dict(m))

    cur.execute("SELECT * FROM tarjeta_estandar WHERE producto_id IN %s OR componente_id IN %s;", (tuple(pids), tuple(pids)))
    print("\nEN TARJETA ESTANDAR:")
    for t in cur.fetchall():
        print(dict(t))

conn.close()
