import app.db
app.db._db_url = "postgresql://postgres:halo23032001@127.0.0.1:5432/tuctuc?sslmode=disable"
from app.db import get_db_connection

conn = get_db_connection()
negocio_id = 59

print("=== VERIFICACIÓN KARDEX VS CONTABILIDAD EN AJUSTE #21 ===")

# 1. Movimientos de inventario del documento 21
movs_inv = conn.execute("""
    SELECT id, producto_id, nombre_producto, tipo, cantidad, valor_unitario, valor_total, costo_und,
           asiento_inventario_id, asiento_contrapartida_id
    FROM movimientos_inventario
    WHERE negocio_id = %s AND documento_numero = '21' AND (tipo_documento ILIKE '%%AJUSTE%%' OR motivo ILIKE '%%ajuste%%')
    ORDER BY id ASC
""", (negocio_id,)).fetchall()

for m in movs_inv:
    print(f"\nKardex MI #{m['id']} | {m['tipo'].upper()} | {m['nombre_producto']} (ID {m['producto_id']}):")
    print(f"   Cantidad: {m['cantidad']} | Costo Und: {m['costo_und']} | Total Kardex: ${float(m['valor_total']):,.2f}")
    
    # Asiento de inventario (140505)
    as_inv = conn.execute("SELECT id, cuenta, tipo, monto, concepto FROM movimientos_contables WHERE id = %s", (m['asiento_inventario_id'],)).fetchone() if m['asiento_inventario_id'] else None
    if as_inv:
        print(f"   -> Asiento Inv  (14*): ID {as_inv['id']} | [{as_inv['tipo']}] {as_inv['cuenta']} | Monto: ${float(as_inv['monto']):,.2f}")
    else:
        # Buscar por comprobante 813 y cuenta 14*
        as_inv_search = conn.execute("""
            SELECT id, cuenta, tipo, monto, concepto FROM movimientos_contables
            WHERE comprobante_id = 813 AND producto_id = %s AND cuenta LIKE '14%%' AND tipo = %s
        """, (m['producto_id'], 'debito' if m['tipo'] == 'entrada' else 'credito')).fetchone()
        if as_inv_search:
            print(f"   -> Asiento Inv  (14*): ID {as_inv_search['id']} | [{as_inv_search['tipo']}] {as_inv_search['cuenta']} | Monto: ${float(as_inv_search['monto']):,.2f}")

    # Asiento de contrapartida (614101 o 414101)
    as_cp = conn.execute("SELECT id, cuenta, tipo, monto, concepto FROM movimientos_contables WHERE id = %s", (m['asiento_contrapartida_id'],)).fetchone() if m['asiento_contrapartida_id'] else None
    if as_cp:
        print(f"   -> Asiento Contrapartida: ID {as_cp['id']} | [{as_cp['tipo']}] {as_cp['cuenta']} | Monto: ${float(as_cp['monto']):,.2f}")
    else:
        as_cp_search = conn.execute("""
            SELECT id, cuenta, tipo, monto, concepto FROM movimientos_contables
            WHERE comprobante_id = 813 AND producto_id = %s AND cuenta NOT LIKE '14%%' AND tipo = %s
        """, (m['producto_id'], 'credito' if m['tipo'] == 'entrada' else 'debito')).fetchone()
        if as_cp_search:
            print(f"   -> Asiento Contrapartida: ID {as_cp_search['id']} | [{as_cp_search['tipo']}] {as_cp_search['cuenta']} | Monto: ${float(as_cp_search['monto']):,.2f}")

conn.close()
