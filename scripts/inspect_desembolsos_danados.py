import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

print("=== INSPECCIÓN DE COMPROBANTES AFECTADOS (SOLO LECTURA) ===")

# Buscar los comprobantes donde debito quedó en 0 o descuadrado
descuadrados = conn.execute("""
    SELECT mc.comprobante_id,
           MAX(mc.tipo_documento) as tipo_documento,
           MAX(mc.numero_documento) as numero_documento,
           MAX(mc.fecha) as fecha,
           ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END)::numeric, 2) AS deb,
           ROUND(SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)::numeric, 2) AS cred,
           ROUND((SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END))::numeric, 2) AS diff
    FROM movimientos_contables mc
    WHERE mc.negocio_id = %s
    GROUP BY mc.comprobante_id
    HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.01
    ORDER BY mc.comprobante_id DESC
""", (negocio_id,)).fetchall()

print(f"Total descuadrados encontrados: {len(descuadrados)}")

for d in descuadrados:
    cid = d['comprobante_id']
    lines = conn.execute("""
        SELECT id, cuenta, tipo, monto, concepto, tercero_id
        FROM movimientos_contables
        WHERE comprobante_id = %s
        ORDER BY tipo DESC, id ASC
    """, (cid,)).fetchall()
    print(f"\n--- Comprobante #{cid} | {d['tipo_documento']} #{d['numero_documento']} | Fecha: {d['fecha']} | Deb: {d['deb']} | Cred: {d['cred']} | Diff: {d['diff']}")
    for l in lines:
        print(f"   ID {l['id']} | [{l['tipo']}] Cuenta: {l['cuenta']} | Monto: {l['monto']} | {l['concepto']}")

conn.close()
