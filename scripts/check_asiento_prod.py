import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

mc = conn.execute("""
    SELECT comprobante_id, fecha, cuenta, tipo, monto, concepto
    FROM movimientos_contables
    WHERE negocio_id = 59 AND origen_id = '1792240718'
    ORDER BY id ASC
""").fetchall()

print("Asiento contable de produccion 1792240718:")
total_d = 0
total_c = 0
for r in mc:
    m = float(r['monto'])
    if r['tipo'] in ('debito', 'D'):
        total_d += m
    else:
        total_c += m
    print(f"   Cuenta:{r['cuenta']} | Tipo:{r['tipo']} | Monto:{m:12.2f} | Concepto:{r['concepto']}")

print(f"Total Debitos: {total_d:.2f} | Total Creditos: {total_c:.2f} | Cuadrado: {abs(total_d - total_c) < 0.01}")

conn.close()
