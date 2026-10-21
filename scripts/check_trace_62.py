import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()

print("Buscando rastros del documento de produccion #62 en auditoria o contabilidad:")
mc = conn.execute("""
    SELECT id, created_at, fecha, numero_documento, tipo_documento, concepto, monto
    FROM movimientos_contables
    WHERE negocio_id = 59 AND (numero_documento = '62' OR concepto ILIKE '%%62%%')
""").fetchall()
for r in mc:
    print("Contabilidad:", dict(r))

# Consecutivos de tipos de documento
td = conn.execute("SELECT id, nombre, consecutivo_actual FROM tipos_documento_negocio WHERE negocio_id = 59 AND id = 5").fetchone()
print("Tipo documento produccion:", dict(td) if td else None)

conn.close()
