import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable")
cur = conn.cursor(cursor_factory=RealDictCursor)

original_lines = [
    (3671, 1677000.00, 12, '614302', 'ADECUACIONES LOCAL [Soporte: 14092026] (Transferencia por concepto de Mesanine adelanto del 65%\nMargarita)'),
    (3672, 1000000.00, 12, '614302', 'ADECUACIONES LOCAL [Soporte: 0436] (Compra de mesa con toppineras y lavaplatos en L por valor total de $3.000.000 abonando 33%\nMargarita)'),
    (3731, 7409000.00, 1,  '614211', 'ARRENDO [Soporte: 1177012] (Arrendo Octubre $5.500.000 arrendo 3 dias Sep $550.000 comision con iva $1.309.000 y $50.000 papeleria\n$5000000 David de ahorro\n$2409000 Margarita)'),
    (3732, 20000.00,   1,  '614210', 'ADECUACIONES LOCAL [Soporte: 0884] (Duplicado llave\nMargarita)'),
    (3733, 1000000.00, 12, '614302', 'ADECUACIONES LOCAL [Soporte: 0436] (Se abona $1.000.000 para mesa y lavaplatos\nMARGARITA)'),
    (3734, 879900.00,  6,  '614301', 'EQUIPO DE COMPUTO [Soporte: 10557] (Compra de Tablet\nDAVID PRESTAMO)'),
    (3735, 248000.00,  12, '614302', 'ADECUACIONES LOCAL [Soporte: 8395] (Compra de baldosa para decorar\nDavid prestamo)'),
    (3738, 80000.00,   1,  '614214', 'GASOLINA MOVILIZACION [Soporte: 41055. 9502] (Gasolina\nDavid)'),
    (3956, 108000.00,  1,  '614215', 'DOCUMENTOS LEGALES [Soporte: 26_0503] (Estudio suelo\nDavid)'),
    (3958, 54000.00,   1,  '614215', 'DOCUMENTOS LEGALES (Registro nombre establecimiento\nDavid)'),
    (3959, 40000.00,   1,  '614215', 'DOCUMENTOS LEGALES (Curso manipulacion de alimentos\nDavid)'),
    (3960, 2022722.00, 12, '614303', 'MUEBLES Y ENCERES (Compra sandwichera\nDavid prestamo)'),
    (3961, 45270.00,   1,  '614202', 'ELEMENTOS DE ASEO [Soporte: 664488] (Escoba esponjas multiusos guantes\nDavid)'),
    (3962, 903000.00,  12, '614302', 'ADECUACIONES LOCAL (Se cancela saldo pendiente por mesanine\nMargarita)'),
    (3963, 70000.00,   1,  '614201', 'TRANSPORTE O DOMICILIOS EN ENTREGAS DE PÈDIDOS (Trannsporte lavaplatos\nDavid)'),
    (4214, 253200.00,  12, '614302', 'ADECUACIONES LOCAL [Soporte: 612] (Materiales electricos\nMargarita)'),
    (4215, 144900.00,  12, '614302', 'ADECUACIONES LOCAL [Soporte: 597] (Materiales ducto y desague agua\nMargarita)'),
    (4216, 12800000.00,12, '614303', 'MUEBLES Y ENCERES [Soporte: 31] (Compra de nevera en dos pagos fef $7.700.000 y consig $5.100.000\nMARGARITA)'),
    (4217, 1000000.00, 12, '614302', 'ADECUACIONES LOCAL (Adelanto mueble para atender clientes\nMARGARIT)'),
    (4218, 400000.00,  12, '614303', 'MUEBLES Y ENCERES (Azafates de mesa. Esta dentro del valor total\nMargarita)'),
    (4416, 600000.00,  12, '614303', 'MUEBLES Y ENCERES (Saldo pendiente\nMargarita $500000+100000)'),
    (4476, 224900.00,  12, '614302', 'ADECUACIONES LOCAL [Soporte: 4418100412322] (Pintura verde\nDavid)'),
    (4887, 905138.89,  12, '614306', 'Saldo activo por amortizar - ADECUACIONES LOCAL (Saldo pendiente mueble exhibidor)'),
    (4888, 40493.05,   12, '614306', 'Saldo activo por amortizar - ADECUACIONES LOCAL (Lapiz, nivelador, cinta enmascarar\nDavid)')
]

# We will restore all 24 lines to Document #5 (or open consecutive)
TARGET_DOC = '5'
cur.execute("SELECT nextval('seq_comprobante_id')")
nuevo_comp_id = cur.fetchone()['nextval']

# 1. Delete all test closures generated from doc 3 to 19 (credits, child amortizations, auto amortizations 3-1..19-1)
cur.execute('''
    DELETE FROM movimientos_contables
    WHERE tipo_documento = 'GASTO_DE_ENTREGAS'
      AND (
          tipo IN ('credito', 'C')
          OR movimiento_origen_id IS NOT NULL
          OR numero_documento LIKE '%%-%%'
          OR CAST(REGEXP_REPLACE(numero_documento, '[^0-9]', '', 'g') AS INTEGER) >= 3
      )
      AND id NOT IN %s
''', (tuple(x[0] for x in original_lines),))

# 2. Delete test programaciones created for these lines
cur.execute('''
    DELETE FROM programaciones_contables
    WHERE (variables_h->>'movimiento_origen_id')::bigint IN %s
''', (tuple(x[0] for x in original_lines),))

# 3. Restore all 24 lines to full monto, open status, TARGET_DOC, nuevo_comp_id
for lid, monto, meses, cta, conc in original_lines:
    cur.execute('''
        UPDATE movimientos_contables
        SET numero_documento = %s,
            comprobante_id = %s,
            monto = %s,
            meses_duracion = %s,
            cuenta = %s,
            cuota_numero = 1,
            cuota_total = %s,
            movimiento_origen_id = NULL,
            origen_tipo = 'gasto',
            tipo = 'debito',
            metodo_desembolso = NULL
        WHERE id = %s
    ''', (TARGET_DOC, nuevo_comp_id, monto, meses, cta, meses, lid))

# 4. Set consecutivo in tipos_documento_negocio to 4 so the active document is exactly 5
cur.execute('''
    UPDATE tipos_documento_negocio
    SET consecutivo = 4
    WHERE codigo = 'GASTO_DE_ENTREGAS'
''')

conn.commit()
print(f"Successfully restored all 24 lines into Document #{TARGET_DOC} under comprobante {nuevo_comp_id}!")

# Verification
cur.execute('''
    SELECT count(*) AS cant, SUM(monto) AS total
    FROM movimientos_contables
    WHERE tipo_documento = 'GASTO_DE_ENTREGAS' AND numero_documento = %s AND tipo IN ('debito', 'D')
''', (TARGET_DOC,))
res = cur.fetchone()
print(f"Document #{TARGET_DOC} has {res['cant']} lines totaling ${float(res['total']):,.2f}")
