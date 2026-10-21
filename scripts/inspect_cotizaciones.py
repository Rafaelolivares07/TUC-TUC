import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'cotizaciones_compras'
""")
print('COLUMNS:')
for r in cur.fetchall():
    print(r[0], r[1], r[2])

cur.execute("""
    SELECT c.id, c.negocio_id, c.tercero_id, c.item_id, p.nombre as producto, c.precio, 
           c.promo_dia_semana, c.promo_dias_anticipacion, c.promo_avisos_por_dia, c.fecha_vencimiento
    FROM cotizaciones_compras c
    JOIN productos p ON p.id = c.item_id
    WHERE p.negocio_id = 59
    ORDER BY c.id DESC
    LIMIT 20
""")
print('\nCOTIZACIONES (negocio 59):')
for r in cur.fetchall():
    print(dict(r))

# Check distinct negocio_id in cotizaciones_compras
cur.execute("""
    SELECT negocio_id, count(*) 
    FROM cotizaciones_compras 
    GROUP BY negocio_id
""")
print('\nDISTINCT negocio_id IN cotizaciones_compras:')
for r in cur.fetchall():
    print(dict(r))

# Check inventario_alertas_agotados
cur.execute("""
    SELECT * FROM inventario_alertas_agotados
    WHERE negocio_id = 59
    ORDER BY id DESC LIMIT 10
""")
print('\nALERTAS AGOTADOS (negocio 59):')
for r in cur.fetchall():
    print(dict(r))
