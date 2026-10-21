import psycopg2
import psycopg2.extras

conn = psycopg2.connect('postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc')
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

print("=== COLUMNS cotizaciones_compras ===")
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default 
    FROM information_schema.columns 
    WHERE table_name = 'cotizaciones_compras' 
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(r['column_name'], r['data_type'], 'NULLABLE:', r['is_nullable'], 'DEFAULT:', r['column_default'])

print("\n=== CONSTRAINTS cotizaciones_compras ===")
cur.execute("""
    SELECT conname, pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname = 'cotizaciones_compras'
""")
for r in cur.fetchall():
    print(r[0], r[1])

print("\n=== INDEXES cotizaciones_compras ===")
cur.execute("""
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'cotizaciones_compras'
""")
for r in cur.fetchall():
    print(r[0], r[1])

print("\n=== RECENT NGINX / GUNICORN ERRORS ===")
# Let's inspect what cotizaciones were modified recently
cur.execute("""
    SELECT id, negocio_id, tercero_id, item_id, precio, unidades_item, 
           promo_dia_semana, promo_dias_anticipacion, promo_avisos_por_dia, updated_at
    FROM cotizaciones_compras
    ORDER BY updated_at DESC NULLS LAST
    LIMIT 10
""")
for r in cur.fetchall():
    print(dict(r))
