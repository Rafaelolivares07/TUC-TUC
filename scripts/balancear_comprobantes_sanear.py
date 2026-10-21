import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print("=== INICIANDO AUDITORIA Y SIMULACIÓN DE SANEAMIENTO ===")

# 1. Comprobante 612 (Duplicado confirmado de la Factura 283014)
cur.execute("SELECT COUNT(*) FROM movimientos_contables WHERE comprobante_id = 612;")
cnt_612 = cur.fetchone()[0]
print(f"Comprobante 612: {cnt_612} lineas a eliminar (duplicado de 611).")

# 2. Obtener todos los comprobantes descuadrados
cur.execute('''
    SELECT mc.comprobante_id,
           MAX(mc.tipo_documento) AS tipo_doc,
           MAX(mc.numero_documento) AS num_doc,
           SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) AS deb,
           SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END) AS cred,
           ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END), 2) AS diff
    FROM movimientos_contables mc
    WHERE mc.negocio_id = 59 AND mc.comprobante_id != 612
    GROUP BY mc.comprobante_id
    HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END)) > 0.01
    ORDER BY mc.comprobante_id ASC;
''')
descuadrados = cur.fetchall()
print(f"Total comprobantes descuadrados a balancear: {len(descuadrados)}")

acciones = []
for comp_id, tipo_doc, num_doc, deb, cred, diff in descuadrados:
    cur.execute('''
        SELECT id, cuenta, concepto, tipo, monto
        FROM movimientos_contables
        WHERE comprobante_id = %s
        ORDER BY id ASC;
    ''', (comp_id,))
    lineas = cur.fetchall()
    
    td_upper = (tipo_doc or '').upper()
    
    # Caso A: Producción (Débito de producto terminado debe igualar la suma de insumos salientes crédito)
    if 'PRODUCC' in td_upper:
        cred_insumos = sum(l[4] for l in lineas if l[3] in ('credito', 'C'))
        deb_terminado = [l for l in lineas if l[3] in ('debito', 'D')]
        if deb_terminado and cred_insumos > 0:
            target_id = deb_terminado[0][0]
            acciones.append({
                'comp_id': comp_id,
                'tipo': 'PRODUCCION',
                'desc': f"Ajustar debito producto terminado ({deb_terminado[0][2]}) de ${deb_terminado[0][4]} a ${cred_insumos}",
                'sql': "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                'params': (cred_insumos, target_id)
            })
        continue

    # Caso B: Factura de Proveedor / Compra
    # El crédito (Caja/Banco/Proveedor) es el valor real de la compra. Los débitos (140505) se ajustan proporcionalmente o en la línea de diferencia.
    if 'PROVEEDOR' in td_upper or 'COMPRA' in td_upper:
        # Si la diferencia es grande o pequeña, ajustar la línea 140505 que causó el descuadre o ajustar la de mayor valor
        lineas_14 = [l for l in lineas if l[3] in ('debito', 'D') and str(l[1]).startswith('14')]
        if lineas_14:
            # En compras, el credito manda (total pagado/facturado)
            # Ajustamos la línea 140505 de mayor monto para absorber la diferencia exactamente
            linea_max = max(lineas_14, key=lambda x: x[4])
            nuevo_monto = round(linea_max[4] - diff, 2)
            if nuevo_monto > 0:
                acciones.append({
                    'comp_id': comp_id,
                    'tipo': 'COMPRA',
                    'desc': f"Ajustar debito 140505 ({linea_max[2]}) de ${linea_max[4]} a ${nuevo_monto} (diff: ${diff})",
                    'sql': "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                    'params': (nuevo_monto, linea_max[0])
                })
        continue

    # Caso C: Ajuste de Inventario
    if 'AJUSTE' in td_upper:
        # En ajustes, la contrapartida de gasto (614101 / 414101 / etc) o la de mayor desbalance se ajusta para igualar
        lineas_cp = [l for l in lineas if str(l[1]).startswith('61') or str(l[1]).startswith('41') or str(l[1]).startswith('53')]
        if not lineas_cp:
            lineas_cp = lineas
        linea_target = max(lineas_cp, key=lambda x: x[4])
        # Si es débito y diff > 0, reducir debito. Si diff < 0, aumentar debito
        if linea_target[3] in ('debito', 'D'):
            nuevo_monto = round(linea_target[4] - diff, 2)
        else:
            nuevo_monto = round(linea_target[4] + diff, 2)
            
        if nuevo_monto >= 0:
            acciones.append({
                'comp_id': comp_id,
                'tipo': 'AJUSTE',
                'desc': f"Ajustar cuenta {linea_target[1]} ({linea_target[2]}) de ${linea_target[4]} a ${nuevo_monto} (diff: ${diff})",
                'sql': "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                'params': (nuevo_monto, linea_target[0])
            })
        continue

    # Caso D: Ventas
    if 'VENTA' in td_upper:
        # En ventas, ajustar la cuenta de Costo de Ventas (614005) para que iguale el inventario
        lineas_61 = [l for l in lineas if l[3] in ('debito', 'D') and str(l[1]).startswith('61')]
        if lineas_61:
            linea_target = max(lineas_61, key=lambda x: x[4])
            nuevo_monto = round(linea_target[4] - diff, 2)
            acciones.append({
                'comp_id': comp_id,
                'tipo': 'VENTA',
                'desc': f"Ajustar costo venta 614005 ({linea_target[2]}) de ${linea_target[4]} a ${nuevo_monto} (diff: ${diff})",
                'sql': "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                'params': (nuevo_monto, linea_target[0])
            })
        continue

    # Caso General / Redondeo
    linea_max = max(lineas, key=lambda x: x[4])
    if linea_max[3] in ('debito', 'D'):
        nuevo_monto = round(linea_max[4] - diff, 2)
    else:
        nuevo_monto = round(linea_max[4] + diff, 2)
    acciones.append({
        'comp_id': comp_id,
        'tipo': 'GENERAL',
        'desc': f"Ajustar {linea_max[1]} ({linea_max[2]}) de ${linea_max[4]} a ${nuevo_monto} (diff: ${diff})",
        'sql': "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
        'params': (nuevo_monto, linea_max[0])
    })

print(f"\nAcciones generadas: {len(acciones)} de {len(descuadrados)}")
for a in acciones[:10]:
    print(f"  Comp {a['comp_id']} [{a['tipo']}]: {a['desc']}")
if len(acciones) > 10:
    print(f"  ... y {len(acciones)-10} mas.")

cur.close()
conn.close()
