import sys
sys.path.append('/home/ubuntu/tuctucv2')
from app import create_app
from app.db import get_db_connection

app = create_app()

with app.app_context():
    conn = get_db_connection()
    try:
        rs = conn.execute("SELECT id, nombre, slug FROM restaurantes WHERE id = 3").fetchall()
        print("RESTAURANTE:", [dict(r) for r in rs])
            
        # Search pedidos of today (2026-10-22) for restaurant 3
        pedidos = conn.execute("""
            SELECT p.id, p.numero_documento, p.total, p.created_at, p.fecha,
                   p.nombre_cajero, p.nombre_cliente, p.metodo_pago, p.estado
            FROM pedidos p
            WHERE (p.restaurante_id = 3 OR p.negocio_id = 3)
              AND DATE(COALESCE(p.fecha, p.created_at)) = CURRENT_DATE
              AND COALESCE(p.estado, '') != 'cancelado'
            ORDER BY p.id ASC
        """).fetchall()
        
        print(f"\n=======================================================")
        print(f"TOTAL PEDIDOS HOY EN LOS SANDWICHES DEL PITT: {len(pedidos)}")
        print(f"=======================================================")
        
        total_unidades = 0
        gran_total_dinero = 0
        productos_totales = {}
        metodos_totales = {}
        
        for idx, p in enumerate(pedidos, 1):
            p_dict = dict(p)
            p_id = p_dict['id']
            tot = float(p_dict.get('total') or 0)
            gran_total_dinero += tot
            
            met = p_dict.get('metodo_pago') or 'efectivo'
            metodos_totales[met] = metodos_totales.get(met, 0) + tot
            
            # Consultar items
            items = conn.execute("SELECT id, producto_id, nombre_producto, cantidad, precio_unitario FROM pedido_items WHERE pedido_id = %s", (p_id,)).fetchall()
            items_list = [dict(it) for it in items]
            
            p_unidades = sum(it['cantidad'] for it in items_list)
            total_unidades += p_unidades
            
            for it in items_list:
                nom = it['nombre_producto']
                productos_totales[nom] = productos_totales.get(nom, 0) + it['cantidad']
            
            hora = str(p_dict.get('created_at') or p_dict.get('fecha'))
            desc_items = ", ".join([f"{it['cantidad']}x {it['nombre_producto']}" for it in items_list])
            doc = p_dict.get('numero_documento') or f"#{p_id}"
            print(f"{idx:02d}. Doc: {doc:<8} | Hora: {hora} | Total: ${tot:>10,.0f} | Metodo: {met:<12} | Items: {desc_items}")
            
        print("\n================ RESUMEN AUDITADO ================")
        print(f"Total Dinero Recaudado: ${gran_total_dinero:,.0f}")
        print(f"Total Facturas / Pedidos: {len(pedidos)}")
        print(f"Total Unidades (Sandwiches) Vendidos: {total_unidades}")
        print("\nDesglose por Producto:")
        for k, v in productos_totales.items():
            print(f"  * {k}: {v} unidades")
        print("\nDesglose por Metodo de Pago:")
        for k, v in metodos_totales.items():
            print(f"  * {k}: ${v:,.0f}")
        print("==================================================\n")

    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
