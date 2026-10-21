import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

print("=== REVISANDO LAS LÍNEAS AFECTADAS EN DESEMBOLSOS ===")

# Buscar comprobantes que NO son facturas de venta y tienen líneas en 0.00 en cuentas 61*
rows = conn.execute("""
    SELECT mc.id, mc.comprobante_id, mc.tipo_documento, mc.numero_documento, mc.cuenta, mc.concepto, mc.monto,
           (SELECT SUM(CASE WHEN tipo IN ('credito', 'C') THEN monto ELSE 0 END) FROM movimientos_contables WHERE comprobante_id = mc.comprobante_id) as total_cred,
           (SELECT SUM(CASE WHEN tipo IN ('debito', 'D') AND id != mc.id THEN monto ELSE 0 END) FROM movimientos_contables WHERE comprobante_id = mc.comprobante_id) as otros_deb
    FROM movimientos_contables mc
    WHERE mc.negocio_id = %s
      AND mc.tipo IN ('debito', 'D')
      AND LEFT(mc.cuenta, 2) = '61'
      AND mc.monto = 0.00
      AND (mc.tipo_documento NOT ILIKE '%%VENTA%%' AND mc.tipo_documento NOT ILIKE '%%FACTURA%%')
    ORDER BY mc.comprobante_id DESC
""", (negocio_id,)).fetchall()

print(f"Total líneas encontradas en 0.00 en desembolsos: {len(rows)}")
for r in rows:
    valor_original = round(float(r['total_cred']) - float(r['otros_deb']), 2)
    print(f"Comp #{r['comprobante_id']} ({r['tipo_documento']} #{r['numero_documento']}) | Línea ID {r['id']} | Cuenta {r['cuenta']} | Monto actual: {r['monto']} -> Valor original exacto: {valor_original} | {r['concepto']}")

conn.close()
