import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Insert credit for Doc 1
cur.execute('''
    INSERT INTO movimientos_contables
        (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, tercero_id,
         tipo_documento_id, numero_documento, fecha, tipo_documento, descripcion_general, origen_tipo, centro_utilidad_id, metodo_desembolso)
    VALUES (59, 456, 110, '110505', 'Cierre relación desembolsos - Contrapartida efectivo', 'credito',
            144900.00, 58, 71, 7, '1', '2026-08-31', 'GASTO_DE_ENTREGAS', 'Relación de Desembolsos cerrada', 'gasto', 1, 'efectivo')
''')

# Insert credit for Doc 2
cur.execute('''
    INSERT INTO movimientos_contables
        (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, tercero_id,
         tipo_documento_id, numero_documento, fecha, tipo_documento, descripcion_general, origen_tipo, centro_utilidad_id, metodo_desembolso)
    VALUES (59, 457, 110, '110505', 'Cierre relación desembolsos - Contrapartida efectivo', 'credito',
            2150000.00, 58, 61, 7, '2', '2026-08-31', 'GASTO_DE_ENTREGAS', 'Relación de Desembolsos cerrada', 'gasto', 1, 'efectivo')
''')

conn.commit()
print("Added credits for Doc 1 and 2.")
