import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')
from app.db import get_db_connection, init_db

init_db(None)
conn = get_db_connection()
negocio_id = 59

# Let's inspect the 43 dif contable in Sandwich Bondiola (id 249)
from app.blueprints.inventarios import api_reparar_costos_venta
from flask import Flask, request

# Run check on api_reparar_costos_venta logic directly
salidas = conn.execute("""
    SELECT mi.id, mi.documento_numero, mi.producto_id, mi.nombre_producto, mi.valor_total, mi.asiento_inventario_id, mi.asiento_contrapartida_id,
           mc.monto as contab_14_monto, mc.id as mc_id
    FROM movimientos_inventario mi
    LEFT JOIN movimientos_contables mc ON mc.id = mi.asiento_inventario_id
    WHERE mi.negocio_id = 59 AND mi.producto_padre_id = 249
      AND (mc.id IS NULL OR abs(mi.valor_total - mc.monto) > 0.01)
    ORDER BY mi.id DESC
    LIMIT 10;
""").fetchall()

print(f"Salidas de Sandwich Bondiola con asiento 14 no coincidente o nulo: {len(salidas)}")
for s in salidas:
    print(f"  * Mov #{s['id']} (Doc {s['documento_numero']}) {s['nombre_producto']}: Kardex ${s['valor_total']} vs Asiento14 (${s['contab_14_monto']}) [Asiento ID: {s['asiento_inventario_id']}]")
