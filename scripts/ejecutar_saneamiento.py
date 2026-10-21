import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

try:
    print("=== PASO 1: ELIMINAR COMPROBANTE 612 DUPLICADO ===")
    cur.execute("DELETE FROM movimientos_contables WHERE comprobante_id = 612 AND negocio_id = 59;")
    filas_612 = cur.rowcount
    print(f"Eliminadas {filas_612} lineas del comprobante 612.")

    print("\n=== PASO 2: OBTENER Y BALANCEAR COMPROBANTES DESCUADRADOS ===")
    cur.execute('''
        SELECT mc.comprobante_id,
               MAX(mc.tipo_documento) AS tipo_doc,
               MAX(mc.numero_documento) AS num_doc,
               SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) AS deb,
               SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END) AS cred,
               ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END), 2) AS diff
        FROM movimientos_contables mc
        WHERE mc.negocio_id = 59
        GROUP BY mc.comprobante_id
        HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END)) > 0.005
        ORDER BY mc.comprobante_id ASC;
    ''')
    descuadrados = cur.fetchall()
    print(f"Comprobantes a balancear: {len(descuadrados)}")

    modificados = 0
    for comp_id, tipo_doc, num_doc, deb, cred, diff in descuadrados:
        cur.execute('''
            SELECT id, cuenta, concepto, tipo, monto
            FROM movimientos_contables
            WHERE comprobante_id = %s
            ORDER BY id ASC;
        ''', (comp_id,))
        lineas = cur.fetchall()
        if not lineas: continue

        td_upper = (tipo_doc or '').upper()

        # A. Producción
        if 'PRODUCC' in td_upper:
            cred_insumos = sum(l[4] for l in lineas if l[3] in ('credito', 'C'))
            deb_terminado = [l for l in lineas if l[3] in ('debito', 'D')]
            if deb_terminado and cred_insumos > 0:
                cur.execute("UPDATE movimientos_contables SET monto = %s WHERE id = %s", (cred_insumos, deb_terminado[0][0]))
                modificados += 1
            continue

        # B. Compras / Factura Proveedor
        if 'PROVEEDOR' in td_upper or 'COMPRA' in td_upper:
            lineas_14 = [l for l in lineas if l[3] in ('debito', 'D') and str(l[1]).startswith('14')]
            if lineas_14:
                linea_max = max(lineas_14, key=lambda x: x[4])
                nuevo_monto = round(linea_max[4] - diff, 2)
                if nuevo_monto > 0:
                    cur.execute("UPDATE movimientos_contables SET monto = %s WHERE id = %s", (nuevo_monto, linea_max[0]))
                    modificados += 1
                    continue

        # C. Ajustes de Inventario
        if 'AJUSTE' in td_upper:
            lineas_cp = [l for l in lineas if str(l[1]).startswith('61') or str(l[1]).startswith('41') or str(l[1]).startswith('53')]
            if not lineas_cp: lineas_cp = lineas
            linea_target = max(lineas_cp, key=lambda x: x[4])
            if linea_target[3] in ('debito', 'D'):
                nuevo_monto = round(linea_target[4] - diff, 2)
            else:
                nuevo_monto = round(linea_target[4] + diff, 2)
            if nuevo_monto >= 0:
                cur.execute("UPDATE movimientos_contables SET monto = %s WHERE id = %s", (nuevo_monto, linea_target[0]))
                modificados += 1
                continue

        # D. Ventas
        if 'VENTA' in td_upper:
            lineas_61 = [l for l in lineas if l[3] in ('debito', 'D') and str(l[1]).startswith('61')]
            if lineas_61:
                linea_target = max(lineas_61, key=lambda x: x[4])
                nuevo_monto = round(linea_target[4] - diff, 2)
                cur.execute("UPDATE movimientos_contables SET monto = %s WHERE id = %s", (nuevo_monto, linea_target[0]))
                modificados += 1
                continue

        # E. General / Redondeos
        linea_max = max(lineas, key=lambda x: x[4])
        if linea_max[3] in ('debito', 'D'):
            nuevo_monto = round(linea_max[4] - diff, 2)
        else:
            nuevo_monto = round(linea_max[4] + diff, 2)
        cur.execute("UPDATE movimientos_contables SET monto = %s WHERE id = %s", (nuevo_monto, linea_max[0]))
        modificados += 1

    conn.commit()
    print(f"\nSaneamiento completado exitosamente: {modificados} comprobantes ajustados a partida doble.")

    # Verificación final
    cur.execute('''
        SELECT COUNT(*)
        FROM (
            SELECT mc.comprobante_id
            FROM movimientos_contables mc
            WHERE mc.negocio_id = 59
            GROUP BY mc.comprobante_id
            HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0.0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0.0 END)) > 0.01
        ) sub;
    ''')
    pendientes = cur.fetchone()[0]
    print(f"VERIFICACIÓN: Comprobantes descuadrados restantes en Negocio 59: {pendientes}")

except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
finally:
    cur.close()
    conn.close()
