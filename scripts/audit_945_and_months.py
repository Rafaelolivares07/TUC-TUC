import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.blueprints.inventarios import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    
    print("=" * 60)
    print("AUDITORIA ESPECIFICA COMPROBANTE 945")
    print("=" * 60)
    lines = conn.execute("""
        SELECT mc.id, mc.comprobante_id, mc.negocio_id, cp.codigo AS cuenta_codigo, cp.nombre AS cuenta_nombre,
               mc.tipo, mc.monto, mc.concepto, t.nombre AS tercero_nombre,
               mc.tipo_documento, mc.numero_documento, mc.tipo_documento_id, td.nombre as tipo_doc_nombre,
               mc.fecha, mc.created_at, mc.origen_tipo, mc.origen_id,
               mc.producto_id, mc.producto_padre_id
        FROM movimientos_contables mc
        LEFT JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
        LEFT JOIN terceros t ON t.id = mc.tercero_id
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.comprobante_id = 945
        ORDER BY mc.id ASC
    """).fetchall()
    
    print(f"Total lineas encontradas en comprobante_id = 945: {len(lines)}")
    tot_deb = 0
    tot_cred = 0
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
        print(f"  Linea #{l['id']} | Cta {l['cuenta_codigo']} ({l['cuenta_nombre']}) | {d_str} | {c_str} | Tercero: {l['tercero_nombre']} | Concepto: {l['concepto']} | Fecha: {l['fecha']} | Doc: {l['tipo_documento']} #{l['numero_documento']} | Origen: {l['origen_tipo']} #{l['origen_id']} | Creado: {l['created_at']}")
    
    print(f"\nTOTAL DEBITO:  ${tot_deb:,.2f}")
    print(f"TOTAL CREDITO: ${tot_cred:,.2f}")
    print(f"DIFERENCIA:    ${abs(tot_deb - tot_cred):,.2f}")

    # Let's check month breakdown of all descuadrados in Negocio 59
    print("\n" + "=" * 60)
    print("DESGLOSE DE COMPROBANTES DESCUADRADOS POR MES (NEGOCIO 59)")
    print("=" * 60)
    meses_descuadre = conn.execute("""
        WITH comp_sums AS (
            SELECT 
                mc.comprobante_id,
                TO_CHAR(mc.fecha, 'YYYY-MM') AS mes,
                COALESCE(MAX(td.nombre), MAX(mc.tipo_documento), 'COMPROBANTE') AS tipo_doc,
                MAX(mc.numero_documento) AS num_doc,
                MAX(mc.fecha) AS fecha,
                MIN(mc.created_at) AS created_at,
                SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) AS total_deb,
                SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END) AS total_cred,
                ROUND(ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END))::numeric, 2) AS diferencia
            FROM movimientos_contables mc
            LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
            WHERE mc.negocio_id = 59
            GROUP BY mc.comprobante_id, TO_CHAR(mc.fecha, 'YYYY-MM')
            HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.05
        )
        SELECT mes, tipo_doc, COUNT(*) AS cantidad_descuadrados,
               SUM(diferencia) AS suma_diferencias,
               MIN(fecha) as fecha_min, MAX(fecha) as fecha_max,
               MIN(created_at) as created_min, MAX(created_at) as created_max
        FROM comp_sums
        GROUP BY mes, tipo_doc
        ORDER BY mes ASC, tipo_doc ASC
    """).fetchall()

    for m in meses_descuadre:
        print(f"  Mes: {m['mes']} | Tipo: {m['tipo_doc']} | Cantidad: {m['cantidad_descuadrados']} | Suma Dif: ${float(m['suma_diferencias']):,.2f} | Fechas Doc: {m['fecha_min']} a {m['fecha_max']} | Creados: {m['created_min']} a {m['created_max']}")

    # Let's inspect the specific descuadrados in July, August, September
    print("\n" + "=" * 60)
    print("DETALLE COMPROBANTES DESCUADRADOS EN JULIO, AGOSTO, SEPTIEMBRE (NEGOCIO 59)")
    print("=" * 60)
    detalles_jul_ago_sep = conn.execute("""
        SELECT 
            mc.comprobante_id,
            TO_CHAR(mc.fecha, 'YYYY-MM') AS mes,
            COALESCE(MAX(td.nombre), MAX(mc.tipo_documento), 'COMPROBANTE') AS tipo_doc,
            MAX(mc.numero_documento) AS num_doc,
            MAX(mc.fecha) AS fecha,
            MIN(mc.created_at) AS created_at,
            ROUND(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END)::numeric, 2) AS deb,
            ROUND(SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)::numeric, 2) AS cred,
            ROUND(ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END))::numeric, 2) AS diferencia,
            COUNT(*) AS lineas
        FROM movimientos_contables mc
        LEFT JOIN tipos_documento_negocio td ON td.id = mc.tipo_documento_id
        WHERE mc.negocio_id = 59
          AND mc.fecha >= '2026-07-01' AND mc.fecha < '2026-10-01'
        GROUP BY mc.comprobante_id, TO_CHAR(mc.fecha, 'YYYY-MM')
        HAVING ABS(SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE 0 END) - SUM(CASE WHEN mc.tipo IN ('credito', 'C') THEN mc.monto ELSE 0 END)) > 0.05
        ORDER BY mc.fecha ASC, mc.comprobante_id ASC
    """).fetchall()

    print(f"Total comprobantes descuadrados en Jul-Ago-Sep 2026: {len(detalles_jul_ago_sep)}")
    for d in detalles_jul_ago_sep:
        print(f"  Comp #{d['comprobante_id']} | Mes: {d['mes']} | {d['tipo_doc']} #{d['num_doc']} | Fecha: {d['fecha']} | Deb: ${float(d['deb']):,.2f} | Cred: ${float(d['cred']):,.2f} | Dif: ${float(d['diferencia']):,.2f} | Lineas: {d['lineas']} | Created: {d['created_at']}")

    conn.close()
