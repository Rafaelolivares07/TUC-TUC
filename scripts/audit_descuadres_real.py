import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.blueprints.inventarios import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    
    # 0. Check columns
    cols = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'movimientos_contables'").fetchall()
    col_names = [c[0] for c in cols]
    print("COLUMNAS DE movimientos_contables:", col_names)

    print("\n=== 1. AUDITORIA COMPROBANTE 945 ===")
    lines = conn.execute("""
        SELECT mc.*, cp.codigo AS cuenta_codigo, cp.nombre AS cuenta_nombre,
               t.nombre AS tercero_nombre, td.nombre AS tipo_doc_nombre
        FROM movimientos_contables mc
        LEFT JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
        LEFT JOIN terceros t ON t.id = mc.tercero_id
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.comprobante_id = 945
        ORDER BY mc.id ASC
    """).fetchall()
    
    tot_deb = 0
    tot_cred = 0
    print(f"Total lineas en comprobante_id = 945: {len(lines)}")
    for l in lines:
        m = float(l['monto'] or 0)
        tipo = l['tipo']
        if tipo in ('debito', 'D'):
            tot_deb += m
            d_str = f"DEB: ${m:,.2f}"
            c_str = "CRED: $0.00"
        else:
            tot_cred += m
            d_str = "DEB: $0.00"
            c_str = f"CRED: ${m:,.2f}"
        print(f"  Line #{l['id']} | Cta {l['cuenta_codigo']} ({l['cuenta_nombre']}) | {d_str} | {c_str} | Concepto: {l['concepto']} | Fecha: {l['fecha']} | Doc: {l['tipo_documento']} #{l['numero_documento']} | Origen: {l.get('origen_tipo')} #{l.get('origen_id')} | Prod: {l.get('producto_id')} (Padre: {l.get('producto_padre_id')}) | Created: {l.get('created_at')}")
    
    print(f"\nTOTAL DEBITO: ${tot_deb:,.2f}")
    print(f"TOTAL CREDITO: ${tot_cred:,.2f}")
    print(f"DIFERENCIA (Descuadre): ${abs(tot_deb - tot_cred):,.2f}")

    print("\n=== 1.1 TODAS LAS LINEAS CON Factura de Proveedor 00001 en Negocio 59 ===")
    lines_doc = conn.execute("""
        SELECT mc.id, mc.comprobante_id, mc.tipo, mc.monto, cp.codigo as cuenta, cp.nombre as cta_nom,
               mc.numero_documento, mc.tipo_documento, mc.fecha, mc.created_at
        FROM movimientos_contables mc
        LEFT JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
        WHERE mc.negocio_id = 59
          AND (mc.numero_documento ILIKE %s OR mc.comprobante_id = 945)
        ORDER BY mc.comprobante_id, mc.id
    """, ('%00001%',)).fetchall()
    for ld in lines_doc:
        print(f"  Comp #{ld['comprobante_id']} | Line #{ld['id']} | {ld['cuenta']} ({ld['cta_nom']}) | {ld['tipo']} ${float(ld['monto'] or 0):,.2f} | Doc: {ld['tipo_documento']} #{ld['numero_documento']} | Fecha: {ld['fecha']} | Created: {ld['created_at']}")

    print("\n=== 2. COMPROBANTES DESCUADRADOS EN NEGOCIO 59 (HISTORIAL COMPLETO) ===")
    descuadrados = conn.execute("""
        SELECT 
            mc.comprobante_id,
            COALESCE(MAX(td.nombre), MAX(mc.tipo_documento), 'COMPROBANTE') AS tipo_doc,
            MAX(mc.numero_documento) AS numero_documento,
            MAX(mc.fecha) AS fecha,
            MIN(mc.created_at) AS created_min,
            MAX(mc.created_at) AS created_max,
            SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) AS total_deb,
            SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END) AS total_cred,
            ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) AS diferencia,
            COUNT(*) AS num_lineas
        FROM movimientos_contables mc
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.negocio_id = 59
        GROUP BY mc.comprobante_id
        HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.05
        ORDER BY MAX(mc.fecha) ASC, mc.comprobante_id ASC
    """).fetchall()

    print(f"TOTAL COMPROBANTES DESCUADRADOS EN NEGOCIO 59: {len(descuadrados)}")
    for d in descuadrados:
        print(f"  Comp #{d['comprobante_id']} | Doc: {d['tipo_doc']} #{d['numero_documento']} | Fecha: {d['fecha']} | Deb: ${float(d['total_deb']):,.2f} | Cred: ${float(d['total_cred']):,.2f} | Dif: ${float(d['diferencia']):,.2f} | Lineas: {d['num_lineas']} | Created: {d['created_min']}")

    conn.close()
