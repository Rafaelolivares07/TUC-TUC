import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

print("=== INICIANDO RESTAURACIÓN QUIRÚRGICA DE DESEMBOLSOS ===")

# Buscar las líneas específicas de desembolsos / gastos que quedaron en 0.00
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

print(f"Total líneas a restaurar: {len(rows)}")

restauradas = 0
for r in rows:
    valor_original = round(float(r['total_cred']) - float(r['otros_deb']), 2)
    if valor_original > 0:
        conn.execute("UPDATE movimientos_contables SET monto = %s WHERE id = %s AND negocio_id = %s", (valor_original, r['id'], negocio_id))
        print(f"✅ Comp #{r['comprobante_id']} ({r['tipo_documento']} #{r['numero_documento']}) | Línea {r['id']} ({r['cuenta']}) restaurada a ${valor_original:,.2f}")
        restauradas += 1
    else:
        print(f"⚠️ Comp #{r['comprobante_id']} cálculo dio {valor_original}, no tocado.")

# Verificar el estado de descuadre general
descuadrados = conn.execute("""
    WITH doc_groups AS (
        SELECT mc.comprobante_id,
            SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) AS deb,
            SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END) AS cred
        FROM movimientos_contables mc
        WHERE mc.negocio_id = %s
        GROUP BY mc.comprobante_id
    )
    SELECT COUNT(CASE WHEN ABS(deb - cred) > 0.01 THEN 1 END) AS count_descuadrados
    FROM doc_groups
""", (negocio_id,)).fetchone()

print(f"\nResultado final tras restauración:")
print(f"Líneas restauradas exitosamente: {restauradas}")
print(f"Comprobantes descuadrados en todo el negocio: {descuadrados['count_descuadrados']}")

conn.commit()
conn.close()
