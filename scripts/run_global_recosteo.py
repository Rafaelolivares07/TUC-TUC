import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
from app.db import get_db_connection, init_db
from app.blueprints.inventarios import _recostear_producto

init_db(None)
conn = get_db_connection()
negocio_id = 59

print("=== EJECUTANDO RECOSTEO GLOBAL COMPLETO EN PRODUCCIÓN (NEGOCIO 59) ===")

# Obtener todos los productos del negocio con movimientos
prod_rows = conn.execute("""
    SELECT DISTINCT producto_id
    FROM movimientos_inventario
    WHERE negocio_id = %s
    ORDER BY producto_id;
""", (negocio_id,)).fetchall()

producto_ids = [r['producto_id'] for r in prod_rows]
print(f"-> Recosteando {len(producto_ids)} productos...")

for pid in producto_ids:
    _recostear_producto(conn, negocio_id, pid)

conn.commit()
print("-> Recosteo global finalizado y confirmado con commit.")

# Verificar diferencias en auditoría de ensambles
from app.blueprints.inventarios import _auditar_producto_recosteo
aud_pan = _auditar_producto_recosteo(conn, negocio_id, 258)
print("\nAuditoría Pan Perman (258):")
print("  * Stock Final:", aud_pan['stock_final'])
print("  * Costo Reconstruido:", aud_pan['costo_reconstruido'])
print("  * Diferencia Valor:", aud_pan['diferencia_valor'])
print("  * Problemas:", aud_pan['problemas'])
