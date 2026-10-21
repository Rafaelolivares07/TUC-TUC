import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@localhost:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

cur.execute("""
    SELECT *
    FROM pedido_items
    WHERE pedido_id = 110;
""")
print("PEDIDO ITEMS 110:")
for r in cur.fetchall():
    print(dict(r))

# Y verificar si en caja.html o en algun endpoint se envía la fecha del pedido
conn.close()
