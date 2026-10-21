import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute('''
    SELECT mc.comprobante_id,
           MAX(mc.tipo_documento) AS tipo_doc,
           MAX(mc.numero_documento) AS num_doc,
           MAX(mc.fecha) AS fecha,
           MAX(mc.origen_tipo) AS origen_tipo,
           COUNT(*) AS num_lineas,
           SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) AS deb,
           SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END) AS cred,
           ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END), 2) AS diff
    FROM movimientos_contables mc
    WHERE mc.negocio_id = 59
    GROUP BY mc.comprobante_id
    HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END)) > 0.05
    ORDER BY ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END)) DESC;
''')

descuadrados = cur.fetchall()
print(f"Total comprobantes a corregir: {len(descuadrados)}")

# Group by category
cats = {'COMPRAS': [], 'PRODUCCION': [], 'AJUSTES': [], 'VENTAS': [], 'OTROS': []}
for d in descuadrados:
    td = (d[1] or '').upper()
    orig = (d[4] or '').lower()
    if 'PROVEEDOR' in td or 'COMPRA' in td or 'inventario_entrada' in orig:
        cats['COMPRAS'].append(d)
    elif 'PRODUCC' in td or 'produccion' in orig:
        cats['PRODUCCION'].append(d)
    elif 'AJUSTE' in td or 'ajuste' in orig or 'auditoria' in orig:
        cats['AJUSTES'].append(d)
    elif 'VENTA' in td or 'pedido' in orig:
        cats['VENTAS'].append(d)
    else:
        cats['OTROS'].append(d)

for c_name, c_list in cats.items():
    print(f"\n--- {c_name} ({len(c_list)}) ---")
    tot_abs_diff = sum(abs(x[8]) for x in c_list)
    print(f"Suma absoluta descuadres: ${tot_abs_diff:,.2f}")
    for x in c_list[:5]:
        print(f"  Comp {x[0]}: {x[1]} #{x[2]} ({x[3]}) | Deb: {x[6]} | Cred: {x[7]} | Diff: {x[8]}")
    if len(c_list) > 5:
        print(f"  ... y {len(c_list)-5} mas.")

cur.close()
conn.close()
