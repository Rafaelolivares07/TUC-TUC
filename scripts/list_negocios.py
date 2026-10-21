import app.db
app.db._db_url = 'postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable'
from app.db import get_db_connection
conn = get_db_connection()
print('TIENDAS:')
for r in conn.execute('SELECT id, nombre, slug FROM tiendas').fetchall():
    print(' ', dict(r))
print('RESTAURANTES:')
for r in conn.execute('SELECT id, nombre, slug FROM restaurantes').fetchall():
    print(' ', dict(r))

# También buscar en movimientos_contables cuáles negocio_id existen
print('\nNEGOCIO_IDS EN MOVIMIENTOS_CONTABLES:')
for r in conn.execute('SELECT negocio_id, COUNT(*) as cnt FROM movimientos_contables GROUP BY negocio_id ORDER BY cnt DESC').fetchall():
    print(' ', dict(r))

# También en comprobantes o dónde están los descuadrados:
print('\nCOMPROBANTES DESCUADRADOS POR NEGOCIO_ID:')
descs = conn.execute("""
    WITH doc_groups AS (
        SELECT mc.negocio_id, mc.comprobante_id,
            SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) AS deb,
            SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END) AS cred
        FROM movimientos_contables mc
        GROUP BY mc.negocio_id, mc.comprobante_id
    )
    SELECT negocio_id,
           COUNT(CASE WHEN ABS(deb - cred) > 0.01 THEN 1 END) AS count_descuadrados,
           COUNT(*) as total_comprobantes
    FROM doc_groups
    GROUP BY negocio_id
""").fetchall()
for r in descs:
    print(' ', dict(r))

conn.close()
