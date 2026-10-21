import os
import sys
from dotenv import load_dotenv

load_dotenv('/home/ubuntu/tuctucv2/.env')
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app import create_app
from app.db import get_db_connection

app = create_app()
with app.app_context():
    conn = get_db_connection()

    print("=== 1. PROMOS ACTIVAS EN COTIZACIONES (promo_dia_semana IS NOT NULL) ===")
    promos = conn.execute("""
        SELECT c.id, c.item_id, p.nombre as producto_nombre, c.tercero_id, t.nombre as proveedor_nombre,
               c.precio, c.unidades_item, c.promo_dia_semana, c.promo_dias_anticipacion, c.promo_avisos_por_dia,
               c.fecha_vencimiento
        FROM cotizaciones_compras c
        JOIN productos p ON p.id = c.item_id
        LEFT JOIN terceros t ON t.id = c.tercero_id
        WHERE c.promo_dia_semana IS NOT NULL
    """).fetchall()
    print(f"Total cotizaciones con promo configurada: {len(promos)}")
    for p in promos:
        print(dict(p))

    print("\n=== 2. TOTAL DE COTIZACIONES EN NEGOCIO 59 ===")
    tot_cotz = conn.execute("SELECT COUNT(*) FROM cotizaciones_compras WHERE negocio_id = 59 OR negocio_id IS NULL").fetchone()[0]
    print(f"Total cotizaciones existentes: {tot_cotz}")

    print("\n=== 3. REGISTROS EN inventario_alertas_agotados (negocio 59) ===")
    agotados = conn.execute("""
        SELECT a.id, a.producto_id, p.nombre as producto_nombre, a.bodega, a.avisos_promo_hoy, a.fecha_ultimo_aviso_promo
        FROM inventario_alertas_agotados a
        JOIN productos p ON p.id = a.producto_id
        WHERE a.negocio_id = 59
    """).fetchall()
    print(f"Total productos en alertas agotados: {len(agotados)}")
    for a in agotados:
        print(dict(a))

    conn.close()
