import os
import subprocess
import psycopg2
import psycopg2.extras

# 1. Configurar timezone del sistema
print("1. Configurando timezone en Linux...")
os.system("sudo timedatectl set-timezone America/Bogota")

# 2. Configurar timezone en Postgres
print("2. Configurando timezone en Postgres...")
conn = psycopg2.connect('postgresql://postgres:halo23032001@localhost:5432/tuctuc')
conn.autocommit = True
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

cur.execute("ALTER SYSTEM SET timezone TO 'America/Bogota';")
cur.execute("SELECT pg_reload_conf();")
cur.execute("SHOW timezone;")
print("Postgres timezone:", cur.fetchone()[0])
cur.execute("SELECT NOW(), CURRENT_DATE;")
now_pg = cur.fetchone()
print(f"Postgres NOW: {now_pg[0]} | CURRENT_DATE: {now_pg[1]}")

# 3. Corregir fecha de Factura 80 (Pedido 110)
print("\n3. Corrigiendo fecha de Factura 80 en movimientos_inventario y pedidos...")
cur.execute("""
    UPDATE movimientos_inventario
    SET documento_fecha = '2026-09-25'
    WHERE documento_numero = '80' AND (documento_fecha = '2026-09-24' OR documento_fecha IS NULL);
""")
print(f"Movimientos actualizados para Factura 80: {cur.rowcount}")

cur.execute("""
    UPDATE pedidos
    SET created_at = '2026-09-25 18:54:48'
    WHERE numero_documento = 'FACTURA_DE_VENTA-80' OR id = 110;
""")
print(f"Pedidos actualizados para Factura 80: {cur.rowcount}")

# 4. Verificar movimientos del PAN TIPO ARABE PERMAN UNID (ID 258)
print("\n4. Verificando movimientos ordenados del producto 258...")
cur.execute("""
    SELECT id, documento_numero, tipo_documento, documento_fecha, created_at, tipo, cantidad, stock_anterior, stock_nuevo
    FROM movimientos_inventario
    WHERE producto_id = 258
    ORDER BY COALESCE(documento_fecha, created_at::date) ASC, created_at ASC, id ASC;
""")
for m in cur.fetchall()[-10:]:
    print(f"ID:{m['id']} | Doc:{m['tipo_documento']} #{m['documento_numero']} | Fecha:{m['documento_fecha']} | CreatedAt:{m['created_at']} | Cant:{m['cantidad']} | {m['stock_anterior']} -> {m['stock_nuevo']}")

conn.close()
print("\n¡Ajuste en base de datos completado con éxito!")
