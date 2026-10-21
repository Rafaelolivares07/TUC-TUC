import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
from app.db import get_db_connection, init_db

init_db(None)
conn = get_db_connection()

# Check auditoria for business 59
from app.blueprints.inventarios import _auditar_producto_recosteo
aud_pan = _auditar_producto_recosteo(conn, 59, 258)
print("Auditoria Pan Perman (258):", aud_pan)

# Check if there are differences between kardex (valor_total) and contabilidad (monto) in real DB
diff_rows = conn.execute("""
    SELECT mi.id, mi.documento_numero, mi.nombre_producto, mi.valor_total, mc.monto as contab_monto,
           abs(mi.valor_total - mc.monto) as diff
    FROM movimientos_inventario mi
    JOIN movimientos_contables mc ON mc.id = mi.asiento_inventario_id
    WHERE mi.negocio_id = 59 AND abs(mi.valor_total - mc.monto) > 0.01
    ORDER BY diff DESC
    LIMIT 10;
""").fetchall()

print(f"\nDiferencias Kardex vs Contabilidad (14*) en Negocio 59: {len(diff_rows)}")
for d in diff_rows:
    print(f"  * Mov #{d['id']} (Doc {d['documento_numero']}) {d['nombre_producto']}: Kardex ${d['valor_total']} vs Contab ${d['contab_monto']} (Dif: ${d['diff']})")
