import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.blueprints.inventarios import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()
    
    print("=== 1. AUDITORIA COMPROBANTE 945 ===")
    comp = conn.execute("SELECT * FROM comprobantes WHERE id = 945").fetchone()
    if comp:
        print("COMPROBANTE 945:", dict(comp))
        lines = conn.execute("""
            SELECT id, comprobante_id, cuenta_codigo, cuenta_nombre, tercero_id,
                   debito, credito, concepto, base, created_at, updated_at,
                   referencia_tipo, referencia_id
            FROM movimientos_contables
            WHERE comprobante_id = 945
            ORDER BY id ASC
        """).fetchall()
        tot_deb = 0
        tot_cred = 0
        print(f"\nLineas ({len(lines)}):")
        for l in lines:
            d = float(l['debito'] or 0)
            c = float(l['credito'] or 0)
            tot_deb += d
            tot_cred += c
            print(f"  ID {l['id']}: Cuenta {l['cuenta_codigo']} ({l['cuenta_nombre']}) | Deb: {d:,.2f} | Cred: {c:,.2f} | Tercero: {l['tercero_id']} | Concepto: {l['concepto']} | Created: {l['created_at']} | Updated: {l['updated_at']}")
        print(f"\nTOTAL DEBITO: {tot_deb:,.2f} | TOTAL CREDITO: {tot_cred:,.2f} | DIFERENCIA: {tot_deb - tot_cred:,.2f}")
    else:
        print("Comprobante 945 no encontrado en la tabla comprobantes!")

    print("\n=== 2. COMPROBANTES DESCUADRADOS EN NEGOCIO 59 ===")
    descuadrados = conn.execute("""
        SELECT c.id, c.numero, c.tipo, c.fecha, c.created_at, c.updated_at,
               ROUND(SUM(m.debito)::numeric, 2) AS total_debito,
               ROUND(SUM(m.credito)::numeric, 2) AS total_credito,
               ROUND((SUM(m.debito) - SUM(m.credito))::numeric, 2) AS diferencia,
               COUNT(m.id) AS num_lineas
        FROM comprobantes c
        JOIN movimientos_contables m ON m.comprobante_id = c.id
        WHERE c.negocio_id = 59
        GROUP BY c.id, c.numero, c.tipo, c.fecha, c.created_at, c.updated_at
        HAVING ABS(SUM(m.debito) - SUM(m.credito)) > 0.05
        ORDER BY c.fecha ASC, c.id ASC
    """).fetchall()
    
    print(f"Total comprobantes descuadrados en negocio 59: {len(descuadrados)}")
    for d in descuadrados:
        print(f"  Comp #{d['id']} | Num: {d['numero']} | Tipo: {d['tipo']} | Fecha: {d['fecha']} | Deb: {float(d['total_debito']):,.2f} | Cred: {float(d['total_credito']):,.2f} | Dif: {float(d['diferencia']):,.2f} | Lineas: {d['num_lineas']} | Created: {d['created_at']} | Updated: {d['updated_at']}")

    conn.close()
