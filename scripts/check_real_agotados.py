import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# Check all products in negocio 59 and their stock vs stock_minimo
cur.execute("""
    SELECT p.id, p.nombre, p.stock_minimo, COALESCE(s.stock, 0) as stock, s.bodega
    FROM productos p
    LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.negocio_id = p.negocio_id
    WHERE p.negocio_id = 59 AND p.disponible = TRUE
    ORDER BY p.nombre
""")
prods = cur.fetchall()

print(f"Total productos en negocio 59: {len(prods)}")
agotados_reales = []
for p in prods:
    st = float(p['stock'] or 0)
    st_min = float(p['stock_minimo'] or 0)
    if st <= st_min and st_min > 0:
        agotados_reales.append(p)

print(f"Productos con stock <= stock_minimo (>0): {len(agotados_reales)}")
for p in agotados_reales:
    # Check if in inventario_alertas_agotados
    cur.execute("""
        SELECT id, estado FROM inventario_alertas_agotados
        WHERE negocio_id = 59 AND producto_id = %s
        ORDER BY id DESC LIMIT 1
    """, (p['id'],))
    al = cur.fetchone()
    print(f"  Prod {p['id']}: {p['nombre']} (Stock: {p['stock']}, Min: {p['stock_minimo']}) -> Alerta: {dict(al) if al else 'NO ALERTA'}")
