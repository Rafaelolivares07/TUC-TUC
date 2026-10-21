import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

print("="*80)
print("ANÁLISIS PROFUNDO DE LOS 3 COMPROBANTES DESCUADRADOS (SOLO LECTURA)")
print("="*80)

# =========================================================================
# CASO 1: COMPROBANTE #813 (AJUSTE ENTRADA #21 - 2026-10-10)
# =========================================================================
print("\n" + "="*50)
print("CASO 1: Comprobante #813 - AJUSTE ENTRADA #21 (Fecha: 2026-10-10)")
print("="*50)

lines_813 = conn.execute("""
    SELECT id, cuenta, tipo, monto, concepto, producto_id, producto_padre_id, tercero_id, centro_utilidad_id, fecha
    FROM movimientos_contables
    WHERE comprobante_id = 813
    ORDER BY tipo DESC, id ASC
""").fetchall()

tot_deb_813 = sum(float(l['monto']) for l in lines_813 if l['tipo'] in ('debito', 'D'))
tot_cred_813 = sum(float(l['monto']) for l in lines_813 if l['tipo'] in ('credito', 'C'))
print(f"Total Débitos: ${tot_deb_813:,.2f} | Total Créditos: ${tot_cred_813:,.2f} | Diferencia: ${tot_deb_813 - tot_cred_813:,.2f}")

for l in lines_813:
    print(f"  [{l['tipo']:7s}] Cuenta: {l['cuenta']} | Monto: {float(l['monto']):12.2f} | Prod: {l['producto_id']} | {l['concepto']}")

movs_inv_813 = conn.execute("""
    SELECT id, producto_id, nombre_producto, tipo, motivo, cantidad, valor_unitario, valor_total, costo_und, documento_numero, tipo_documento, created_at
    FROM movimientos_inventario
    WHERE negocio_id = %s AND documento_numero = '21' AND (tipo_documento ILIKE '%%AJUSTE%%' OR motivo ILIKE '%%ajuste%%')
    ORDER BY id ASC
""", (negocio_id,)).fetchall()

print("\nMovimientos de Inventario del documento '21':")
for m in movs_inv_813:
    print(f"  MI #{m['id']} | {m['tipo']} | Prod {m['producto_id']}: {m['nombre_producto']} | Cant: {m['cantidad']} | VU: {m['valor_unitario']} | CostUnd: {m['costo_und']} | Tot: {m['valor_total']}")

# =========================================================================
# CASO 2: COMPROBANTE #811 (GASTO_DE_ENTREGAS #30 - 2026-10-05)
# =========================================================================
print("\n" + "="*50)
print("CASO 2: Comprobante #811 - GASTO_DE_ENTREGAS #30 (Fecha: 2026-10-05)")
print("="*50)

lines_811 = conn.execute("""
    SELECT id, cuenta, tipo, monto, concepto, tercero_id, centro_utilidad_id, fecha
    FROM movimientos_contables
    WHERE comprobante_id = 811
    ORDER BY tipo DESC, id ASC
""").fetchall()

tot_deb_811 = sum(float(l['monto']) for l in lines_811 if l['tipo'] in ('debito', 'D'))
tot_cred_811 = sum(float(l['monto']) for l in lines_811 if l['tipo'] in ('credito', 'C'))
print(f"Total Débitos: ${tot_deb_811:,.2f} | Total Créditos: ${tot_cred_811:,.2f} | Diferencia: ${tot_deb_811 - tot_cred_811:,.2f}")

for l in lines_811:
    print(f"  [{l['tipo']:7s}] Cuenta: {l['cuenta']} | Monto: {float(l['monto']):12.2f} | {l['concepto']}")

# Buscar en movimientos de tesoreria o gastos si existen
try:
    cols = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'desembolsos'").fetchall()
    print("Columnas de desembolsos:", [c['column_name'] for c in cols])
    desemb_30 = conn.execute("SELECT * FROM desembolsos WHERE negocio_id = %s ORDER BY id DESC LIMIT 5", (negocio_id,)).fetchall()
    print("Muestra desembolsos:", [dict(d) for d in desemb_30])
except Exception as e:
    conn.rollback()
    print("Error consultando desembolsos:", e)

# =========================================================================
# CASO 3: COMPROBANTE #457 (GASTO_DE_ENTREGAS #2 - 2026-08-31)
# =========================================================================
print("\n" + "="*50)
print("CASO 3: Comprobante #457 - GASTO_DE_ENTREGAS #2 (Fecha: 2026-08-31)")
print("="*50)

lines_457 = conn.execute("""
    SELECT id, cuenta, tipo, monto, concepto, tercero_id, centro_utilidad_id, fecha
    FROM movimientos_contables
    WHERE comprobante_id = 457
    ORDER BY tipo DESC, id ASC
""").fetchall()

tot_deb_457 = sum(float(l['monto']) for l in lines_457 if l['tipo'] in ('debito', 'D'))
tot_cred_457 = sum(float(l['monto']) for l in lines_457 if l['tipo'] in ('credito', 'C'))
print(f"Total Débitos: ${tot_deb_457:,.2f} | Total Créditos: ${tot_cred_457:,.2f} | Diferencia: ${tot_deb_457 - tot_cred_457:,.2f}")

for l in lines_457:
    print(f"  [{l['tipo']:7s}] Cuenta: {l['cuenta']} | Monto: {float(l['monto']):12.2f} | {l['concepto']}")

conn.close()
