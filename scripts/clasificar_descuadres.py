import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

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
    ORDER BY MAX(mc.fecha) DESC, mc.comprobante_id DESC
""", (negocio_id,)).fetchall()

print(f"Total descuadrados: {len(descuadrados)}")

# Clasificar los 285 descuadrados:
# Causa A: 61* no coincide con suma de 14*
# Causa B: Otra cuenta (caja/banco/ingresos/proveedores/etc.)
count_cogs_diff = 0
count_other = 0
other_samples = []

for d in descuadrados:
    cid = d['comprobante_id']
    sums = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN tipo IN ('debito', 'D') AND LEFT(cuenta, 2) = '61' THEN monto ELSE 0 END), 0) as deb_61,
            COALESCE(SUM(CASE WHEN tipo IN ('credito', 'C') AND LEFT(cuenta, 2) = '14' THEN monto ELSE 0 END), 0) as cred_14,
            COALESCE(SUM(CASE WHEN tipo IN ('debito', 'D') AND LEFT(cuenta, 2) != '61' THEN monto ELSE 0 END), 0) as deb_other,
            COALESCE(SUM(CASE WHEN tipo IN ('credito', 'C') AND LEFT(cuenta, 2) != '14' THEN monto ELSE 0 END), 0) as cred_other
        FROM movimientos_contables
        WHERE comprobante_id = %s
    """, (cid,)).fetchone()
    
    diff_cogs = round(float(sums['deb_61']) - float(sums['cred_14']), 2)
    diff_other = round(float(sums['deb_other']) - float(sums['cred_other']), 2)
    
    if abs(diff_cogs) > 0.01 and abs(diff_other) <= 0.01:
        count_cogs_diff += 1
    else:
        count_other += 1
        if len(other_samples) < 5:
            other_samples.append({
                'comp_id': cid,
                'doc': f"{d['tipo_documento']} #{d['numero_documento']}",
                'diff_total': d['diff'],
                'diff_cogs': diff_cogs,
                'diff_other': diff_other
            })

print(f"Descuadrados SOLO por diferencia entre 61* y 14* (COGS vs Inventario): {count_cogs_diff}")
print(f"Descuadrados por otras razones o mixtos: {count_other}")

if other_samples:
    print("\nEjemplos de otros descuadres:")
    for s in other_samples:
        print(" ", s)

conn.close()
