#!/usr/bin/env python3
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
import psycopg2.extras

conn = psycopg2.connect(
    'postgresql://postgres:grandesventas99@localhost:5432/tuctuc_local',
    options='-c client_encoding=LATIN1'
)
conn.set_client_encoding('LATIN1')
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print('=== KARDEX - factura 41 salidas ===')
cur.execute("""
    SELECT m.producto_id, m.producto_padre_id, m.nombre_producto,
           m.cantidad, m.costo_und, COALESCE(m.valor_total, m.cantidad*m.costo_und,0) as total
    FROM movimientos_inventario m
    WHERE m.negocio_id = 59
      AND m.documento_numero = '41'
      AND m.tipo = 'salida'
    ORDER BY m.nombre_producto
""")
for r in cur.fetchall():
    print(f"  prod_id={r['producto_id']} | padre_id={r['producto_padre_id']} | {r['nombre_producto']} | cant={r['cantidad']} | c/u={r['costo_und']} | total={r['total']}")

print()
print('=== CONTABILIDAD - factura 41, cuentas 14* ===')
cur.execute("""
    SELECT mc.id, mc.cuenta_id, mc.concepto, mc.tipo, mc.monto,
           mc.producto_id, mc.producto_padre_id
    FROM movimientos_contables mc
    WHERE mc.negocio_id = 59
      AND mc.numero_documento = 'FACTURA_DE_VENTA-41'
      AND CAST(mc.cuenta_id AS VARCHAR) LIKE '14%%'
    ORDER BY mc.concepto
""")
rows_contab = cur.fetchall()
for r in rows_contab:
    print(f"  id={r['id']} | cuenta={r['cuenta_id']} | {r['concepto']} | tipo={r['tipo']} | monto={r['monto']} | prod_id={r['producto_id']} | padre_id={r['producto_padre_id']}")

print()
print(f'Kardex: registros salida')
print(f'Contabilidad 14*: {len(rows_contab)} registros')

conn.close()
