import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

cur.execute("""
    SELECT c.id, c.item_id, p.nombre, c.precio, c.promo_dia_semana, c.promo_dias_anticipacion, c.promo_avisos_por_dia
    FROM cotizaciones_compras c
    JOIN productos p ON p.id = c.item_id
    WHERE c.item_id IN (302, 261, 299, 265, 274)
""")
for r in cur.fetchall():
    print(dict(r))

# Also check ANY cotizacion in whole table with promo_dia_semana IS NOT NULL
cur.execute("""
    SELECT c.id, c.negocio_id, c.item_id, p.nombre, c.precio, c.promo_dia_semana, c.promo_dias_anticipacion, c.promo_avisos_por_dia
    FROM cotizaciones_compras c
    JOIN productos p ON p.id = c.item_id
    WHERE c.promo_dia_semana IS NOT NULL
""")
rows = cur.fetchall()
print("\nANY COTIZACIONES WITH PROMO:")
for r in rows:
    print(dict(r))
if not rows:
    print("NONE!")
