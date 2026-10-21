import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.blueprints.inventarios import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()

    print("=" * 80)
    print("1. DETALLE DE TODAS LAS FACTURAS DE PROVEEDOR DESCUADRADAS (JUL, AGO, SEP, OCT)")
    print("=" * 80)
    fac_prov = conn.execute("""
        SELECT 
            mc.comprobante_id,
            TO_CHAR(mc.fecha, 'YYYY-MM') AS mes,
            COALESCE(td.nombre, mc.tipo_documento) AS tipo_doc,
            mc.numero_documento,
            mc.fecha,
            MIN(mc.created_at) AS created_at,
            ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END)::numeric, 2) AS deb,
            ROUND(SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)::numeric, 2) AS cred,
            ROUND(ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END))::numeric, 2) AS diferencia,
            COUNT(*) AS lineas
        FROM movimientos_contables mc
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.negocio_id = 59
          AND (COALESCE(td.nombre, mc.tipo_documento) ILIKE %s OR COALESCE(td.nombre, mc.tipo_documento) ILIKE %s)
        GROUP BY mc.comprobante_id, TO_CHAR(mc.fecha, 'YYYY-MM'), COALESCE(td.nombre, mc.tipo_documento), mc.numero_documento, mc.fecha
        HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.05
        ORDER BY mc.fecha ASC, mc.comprobante_id ASC
    """, ('%PROVEEDOR%', '%ENTRADA%')).fetchall()

    print(f"Total Facturas de Proveedor descuadradas: {len(fac_prov)}")
    for fp in fac_prov:
        print(f"\n---> Comprobante #{fp['comprobante_id']} | Doc: {fp['tipo_doc']} #{fp['numero_documento']} | Fecha: {fp['fecha']} | Deb: ${float(fp['deb']):,.2f} | Cred: ${float(fp['cred']):,.2f} | Dif: ${float(fp['diferencia']):,.2f} | Lineas: {fp['lineas']} | Creado: {fp['created_at']}")
        c_lines = conn.execute("""
            SELECT mc.id, cp.codigo AS cta, cp.nombre AS cta_nom, mc.tipo, mc.monto, mc.concepto, t.nombre AS tercero, mc.created_at
            FROM movimientos_contables mc
            LEFT JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
            LEFT JOIN terceros t ON t.id = mc.tercero_id
            WHERE mc.comprobante_id = %s
            ORDER BY mc.id ASC
        """, (fp['comprobante_id'],)).fetchall()
        for cl in c_lines:
            t_str = "DEB" if cl['tipo'] in ('debito', 'D') else "CRED"
            print(f"       Line #{cl['id']}: Cta {cl['cta']} ({cl['cta_nom']}) | {t_str} ${float(cl['monto']):,.2f} | Tercero: {cl['tercero']} | Concepto: {cl['concepto']} | Creado: {cl['created_at']}")

    print("\n" + "=" * 80)
    print("2. MUESTRA DE FACTURAS DE VENTA DESCUADRADAS")
    print("=" * 80)
    fac_venta = conn.execute("""
        SELECT 
            mc.comprobante_id,
            TO_CHAR(mc.fecha, 'YYYY-MM') AS mes,
            COALESCE(td.nombre, mc.tipo_documento) AS tipo_doc,
            mc.numero_documento,
            mc.fecha,
            MIN(mc.created_at) AS created_at,
            ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END)::numeric, 2) AS deb,
            ROUND(SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)::numeric, 2) AS cred,
            ROUND(ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END))::numeric, 2) AS diferencia,
            COUNT(*) AS lineas
        FROM movimientos_contables mc
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.negocio_id = 59
          AND COALESCE(td.nombre, mc.tipo_documento) ILIKE %s
        GROUP BY mc.comprobante_id, TO_CHAR(mc.fecha, 'YYYY-MM'), COALESCE(td.nombre, mc.tipo_documento), mc.numero_documento, mc.fecha
        HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.05
        ORDER BY mc.fecha ASC, mc.comprobante_id ASC
        LIMIT 5
    """, ('%VENTA%',)).fetchall()

    for fv in fac_venta:
        print(f"\n---> Comprobante #{fv['comprobante_id']} | Doc: {fv['tipo_doc']} #{fv['numero_documento']} | Fecha: {fv['fecha']} | Deb: ${float(fv['deb']):,.2f} | Cred: ${float(fv['cred']):,.2f} | Dif: ${float(fv['diferencia']):,.2f} | Lineas: {fv['lineas']} | Creado: {fv['created_at']}")
        v_lines = conn.execute("""
            SELECT mc.id, cp.codigo AS cta, cp.nombre AS cta_nom, mc.tipo, mc.monto, mc.concepto, t.nombre AS tercero, mc.created_at
            FROM movimientos_contables mc
            LEFT JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
            LEFT JOIN terceros t ON t.id = mc.tercero_id
            WHERE mc.comprobante_id = %s
            ORDER BY mc.id ASC
        """, (fv['comprobante_id'],)).fetchall()
        for vl in v_lines:
            t_str = "DEB" if vl['tipo'] in ('debito', 'D') else "CRED"
            print(f"       Line #{vl['id']}: Cta {vl['cta']} ({vl['cta_nom']}) | {t_str} ${float(vl['monto']):,.2f} | Tercero: {vl['tercero']} | Concepto: {vl['concepto']} | Creado: {vl['created_at']}")

    print("\n" + "=" * 80)
    print("3. MUESTRA DE REPORTES DE PRODUCCION DESCUADRADOS")
    print("=" * 80)
    prod_des = conn.execute("""
        SELECT 
            mc.comprobante_id,
            TO_CHAR(mc.fecha, 'YYYY-MM') AS mes,
            COALESCE(td.nombre, mc.tipo_documento) AS tipo_doc,
            mc.numero_documento,
            mc.fecha,
            MIN(mc.created_at) AS created_at,
            ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END)::numeric, 2) AS deb,
            ROUND(SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)::numeric, 2) AS cred,
            ROUND(ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END))::numeric, 2) AS diferencia,
            COUNT(*) AS lineas
        FROM movimientos_contables mc
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.negocio_id = 59
          AND COALESCE(td.nombre, mc.tipo_documento) ILIKE %s
        GROUP BY mc.comprobante_id, TO_CHAR(mc.fecha, 'YYYY-MM'), COALESCE(td.nombre, mc.tipo_documento), mc.numero_documento, mc.fecha
        HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.05
        ORDER BY mc.fecha ASC, mc.comprobante_id ASC
        LIMIT 5
    """, ('%PRODUCCION%',)).fetchall()

    for pd in prod_des:
        print(f"\n---> Comprobante #{pd['comprobante_id']} | Doc: {pd['tipo_doc']} #{pd['numero_documento']} | Fecha: {pd['fecha']} | Deb: ${float(pd['deb']):,.2f} | Cred: ${float(pd['cred']):,.2f} | Dif: ${float(pd['diferencia']):,.2f} | Lineas: {pd['lineas']} | Creado: {pd['created_at']}")
        p_lines = conn.execute("""
            SELECT mc.id, cp.codigo AS cta, cp.nombre AS cta_nom, mc.tipo, mc.monto, mc.concepto, t.nombre AS tercero, mc.created_at
            FROM movimientos_contables mc
            LEFT JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
            LEFT JOIN terceros t ON t.id = mc.tercero_id
            WHERE mc.comprobante_id = %s
            ORDER BY mc.id ASC
        """, (pd['comprobante_id'],)).fetchall()
        for pl in p_lines:
            t_str = "DEB" if pl['tipo'] in ('debito', 'D') else "CRED"
            print(f"       Line #{pl['id']}: Cta {pl['cta']} ({pl['cta_nom']}) | {t_str} ${float(pl['monto']):,.2f} | Tercero: {pl['tercero']} | Concepto: {pl['concepto']} | Creado: {pl['created_at']}")

    conn.close()
