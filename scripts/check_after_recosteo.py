import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
from app.db import get_db_connection, init_db

init_db(None)
conn = get_db_connection()
negocio_id = 59

# Let's inspect the differences on Sandwich Bondiola, Sandwich Pollo, etc.
diffs = conn.execute("""
    SELECT 
        p.nombre as plato,
        count(DISTINCT mi.documento_numero) as docs_count,
        SUM(mi.valor_total) as kardex_total,
        SUM(mc.monto) as contab_total,
        abs(SUM(mi.valor_total) - SUM(mc.monto)) as dif_contab
    FROM movimientos_inventario mi
    JOIN productos p ON p.id = mi.producto_padre_id
    LEFT JOIN movimientos_contables mc ON mc.id = mi.asiento_inventario_id
    WHERE mi.negocio_id = 59 AND mi.producto_padre_id IS NOT NULL AND mi.tipo = 'salida'
      AND COALESCE(mi.documento_fecha, mi.created_at::date) >= '2026-08-01'
      AND COALESCE(mi.documento_fecha, mi.created_at::date) <= '2026-10-09'
    GROUP BY p.nombre
    ORDER BY dif_contab DESC;
""").fetchall()

print("Diferencias Kardex vs Contabilidad (14*) por Ensamble:")
for d in diffs[:10]:
    print(f"  * {d['plato']}: Kardex ${d['kardex_total']:,.2f} vs Contab ${d['contab_total']:,.2f} -> Dif: ${d['dif_contab']:,.2f}")

# Check pedido_items difference
ped_diffs = conn.execute("""
    SELECT 
        p_prod.nombre as plato,
        SUM(pi.cantidad * pi.costo_unitario) as pedidos_cogs,
        SUM(mi_tot.total_kardex) as kardex_cogs,
        abs(SUM(pi.cantidad * pi.costo_unitario) - SUM(mi_tot.total_kardex)) as dif_pedidos
    FROM pedidos p
    JOIN pedido_items pi ON pi.pedido_id = p.id
    JOIN productos p_prod ON p_prod.id = pi.producto_id
    LEFT JOIN (
        SELECT negocio_id, producto_padre_id, documento_numero, SUM(valor_total) as total_kardex
        FROM movimientos_inventario
        WHERE tipo = 'salida' AND producto_padre_id IS NOT NULL
        GROUP BY negocio_id, producto_padre_id, documento_numero
    ) mi_tot ON mi_tot.negocio_id = p.negocio_id 
            AND mi_tot.producto_padre_id = pi.producto_id 
            AND (mi_tot.documento_numero = p.numero_documento OR mi_tot.documento_numero = p.id::text)
    WHERE p.negocio_id = 59
      AND p.fecha >= '2026-08-01' AND p.fecha <= '2026-10-09'
      AND mi_tot.total_kardex IS NOT NULL
    GROUP BY p_prod.nombre
    ORDER BY dif_pedidos DESC;
""").fetchall()

print("\nDiferencias Pedidos vs Kardex por Ensamble:")
for pd in ped_diffs[:10]:
    print(f"  * {pd['plato']}: Pedidos ${pd['pedidos_cogs']:,.2f} vs Kardex ${pd['kardex_cogs']:,.2f} -> Dif: ${pd['dif_pedidos']:,.2f}")
