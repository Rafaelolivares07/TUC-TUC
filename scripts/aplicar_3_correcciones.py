import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

print("=== APLICANDO LAS 3 CORRECCIONES PUNTUALES ===")

# 1. Comprobante #811: Línea 6122 (Implementos eléctricos) -> $35,400.00
conn.execute("""
    UPDATE movimientos_contables
    SET monto = 35400.00
    WHERE id = 6122 AND comprobante_id = 811 AND negocio_id = %s
""", (negocio_id,))
print("✅ Comprobante #811 corregido: Línea 6122 actualizada a +$35,400.00")

# 2. Comprobante #457: Línea 2906 (Pasajes para entregas) -> $50,000.00
conn.execute("""
    UPDATE movimientos_contables
    SET monto = 50000.00
    WHERE id = 2906 AND comprobante_id = 457 AND negocio_id = %s
""", (negocio_id,))
print("✅ Comprobante #457 corregido: Línea 2906 actualizada a +$50,000.00")

# 3. Comprobante #813: Línea de contrapartida 414101 del Azúcar -> $1,698.30
# Buscar la línea específica de cuenta 414101 en comp 813
l41 = conn.execute("""
    SELECT id, monto, concepto FROM movimientos_contables
    WHERE comprobante_id = 813 AND cuenta = '414101' AND negocio_id = %s
""", (negocio_id,)).fetchone()

if l41:
    conn.execute("""
        UPDATE movimientos_contables
        SET monto = 1698.30
        WHERE id = %s AND negocio_id = %s
    """, (l41['id'], negocio_id))
    print(f"✅ Comprobante #813 corregido: Línea {l41['id']} (414101) actualizada de ${float(l41['monto']):,.2f} a $1,698.30")

# 4. Enlazar asiento_contrapartida_id del MI #4008 con esa línea 414101 para que queden vinculados
if l41:
    conn.execute("""
        UPDATE movimientos_inventario
        SET asiento_contrapartida_id = %s
        WHERE id = 4008 AND negocio_id = %s
    """, (l41['id'], negocio_id))
    print("✅ Movimiento de Kardex #4008 vinculado con su asiento de contrapartida")

# 5. VERIFICACIÓN FINAL: Contar descuadrados en todo el negocio
post = conn.execute("""
    WITH doc_groups AS (
        SELECT mc.comprobante_id,
            ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END)::numeric, 2) AS deb,
            ROUND(SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END)::numeric, 2) AS cred
        FROM movimientos_contables mc
        WHERE mc.negocio_id = %s
        GROUP BY mc.comprobante_id
    )
    SELECT COUNT(CASE WHEN ABS(deb - cred) > 0.01 THEN 1 END) AS descuadrados,
           COUNT(*) as total_comprobantes
    FROM doc_groups
""", (negocio_id,)).fetchone()

print(f"\n==========================================")
print(f"TOTAL COMPROBANTES DESCUADRADOS: {post['descuadrados']} de {post['total_comprobantes']}")
print(f"==========================================")

if post['descuadrados'] == 0:
    conn.commit()
    print("¡COMMIT EXITOSO! Todo el sistema contable está 100% cuadrado.")
else:
    conn.rollback()
    print("⚠️ Algo no cuadró, ROLLBACK ejecutado.")

conn.close()
