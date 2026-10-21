import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

print('=== PRODUCTOS DE POLLO / PECHUGA ===')
prods = conn.execute("""
    SELECT id, nombre, categoria, costo
    FROM productos
    WHERE negocio_id = %s AND (nombre ILIKE %s OR nombre ILIKE %s)
    ORDER BY id
""", (59, '%pechuga%', '%pollo%')).fetchall()
for p in prods:
    print(dict(p))

p_ids = [p['id'] for p in prods]

print('\n=== SALDOS ACTUALES ===')
saldos = conn.execute("""
    SELECT s.producto_id, p.nombre, s.bodega, s.stock, s.costo_und
    FROM saldos_inventario s
    JOIN productos p ON p.id = s.producto_id
    WHERE s.negocio_id = 59 AND s.producto_id = ANY(%s)
""", (p_ids,)).fetchall()
for s in saldos:
    print(dict(s))

print('\n=== ULTIMOS 40 MOVIMIENTOS DE ESTOS PRODUCTOS (KARDEX) ===')
movs = conn.execute("""
    SELECT m.id, m.created_at, m.documento_fecha, m.tipo, m.cantidad, m.valor_unitario, m.valor_total,
           m.referencia_tipo, m.referencia_id, m.producto_id, p.nombre as producto_nombre
    FROM movimientos_inventario m
    JOIN productos p ON p.id = m.producto_id
    WHERE m.negocio_id = 59 AND m.producto_id = ANY(%s)
    ORDER BY m.id DESC
    LIMIT 40
""", (p_ids,)).fetchall()
for m in movs:
    print(dict(m))

print('\n=== ULTIMAS PRODUCCIONES REGISTRADAS EN ESTE NEGOCIO ===')
prods_mov = conn.execute("""
    SELECT DISTINCT m.referencia_id, m.created_at, m.documento_fecha, m.producto_padre_id, m.tipo_documento, m.documento_numero
    FROM movimientos_inventario m
    WHERE m.negocio_id = 59 AND m.referencia_tipo = 'produccion'
    ORDER BY m.referencia_id DESC
    LIMIT 10
""").fetchall()
for pm in prods_mov:
    print(dict(pm))

conn.close()
