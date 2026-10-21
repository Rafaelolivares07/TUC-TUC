import os
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, '/home/ubuntu/tuctucv2')
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/tuctucv2/.env')

from app.db import get_db_connection, init_db

class DummyApp:
    pass

def main():
    init_db(DummyApp())
    conn = get_db_connection()
    print("=== INICIANDO MIGRACIÓN Y POBLADO EN BASE DE DATOS REAL ===")

    # 1. Agregar columnas a movimientos_inventario si no existen
    print("\n1. Agregando columnas 'asiento_inventario_id' y 'asiento_contrapartida_id' a movimientos_inventario...")
    conn.execute("""
        ALTER TABLE movimientos_inventario 
        ADD COLUMN IF NOT EXISTS asiento_inventario_id BIGINT,
        ADD COLUMN IF NOT EXISTS asiento_contrapartida_id BIGINT;
    """)
    conn.commit()
    print("   -> Columnas verificadas y creadas exitosamente.")

    # 2. Mapeo Global por Tipo de Operación para TODOS los negocios
    print("\n2. Ejecutando Mapeo Global en movimientos_inventario...")

    # A1. Ventas 14* (Salidas de insumos por plato/producto elaborado)
    res_v_14_padre = conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_inventario_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'salida'
          AND mi.producto_padre_id IS NOT NULL
          AND mi.asiento_inventario_id IS NULL
          AND mc.cuenta LIKE '14%%' AND mc.tipo = 'credito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND mi.producto_id = mc.producto_id
          AND mc.producto_padre_id = mi.producto_padre_id;
    """)
    conn.commit()

    # A2. Ventas 14* (Salidas de productos simples)
    res_v_14_simple = conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_inventario_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'salida'
          AND mi.producto_padre_id IS NULL
          AND mi.asiento_inventario_id IS NULL
          AND mc.cuenta LIKE '14%%' AND mc.tipo = 'credito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND mi.producto_id = mc.producto_id;
    """)
    conn.commit()

    # A3. Ventas 14* Respaldo por nombre/concepto
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_inventario_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'salida'
          AND mi.asiento_inventario_id IS NULL
          AND mc.cuenta LIKE '14%%' AND mc.tipo = 'credito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND (
              UPPER(mc.concepto) LIKE '%%' || UPPER(mi.nombre_producto) || '%%'
              OR UPPER(mi.nombre_producto) LIKE '%%' || UPPER(REPLACE(mc.concepto, 'BAJA INV: ', '')) || '%%'
          );
    """)
    conn.commit()

    # B1. Ventas 61* Débito / Costo de Venta (Insumos -> Plato Padre)
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_contrapartida_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'salida'
          AND mi.producto_padre_id IS NOT NULL
          AND mi.asiento_contrapartida_id IS NULL
          AND LEFT(mc.cuenta, 2) = '61' AND mc.tipo = 'debito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND (mc.producto_padre_id = mi.producto_padre_id OR mc.producto_id = mi.producto_padre_id);
    """)
    conn.commit()

    # B2. Ventas 61* Débito para productos simples
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_contrapartida_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'salida'
          AND mi.producto_padre_id IS NULL
          AND mi.asiento_contrapartida_id IS NULL
          AND LEFT(mc.cuenta, 2) = '61' AND mc.tipo = 'debito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND mc.producto_id = mi.producto_id;
    """)
    conn.commit()

    # C1. Compras 14* Débito
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_inventario_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'entrada'
          AND (
              mi.referencia_tipo ILIKE '%%compra%%' 
              OR mi.tipo_documento ILIKE '%%compra%%' 
              OR mi.tipo_documento ILIKE '%%proveedor%%' 
              OR mi.referencia_tipo ILIKE '%%proveedor%%'
          )
          AND mi.asiento_inventario_id IS NULL
          AND mc.cuenta LIKE '14%%' AND mc.tipo = 'debito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
              OR mi.referencia_id::text = mc.numero_documento
          )
          AND (
              mi.producto_id = mc.producto_id 
              OR UPPER(mc.concepto) LIKE '%%' || UPPER(mi.nombre_producto) || '%%'
          );
    """)
    conn.commit()

    # C2. Compras Contrapartida (22*, 23*, 11*)
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_contrapartida_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND mi.tipo = 'entrada'
          AND (
              mi.referencia_tipo ILIKE '%%compra%%' 
              OR mi.tipo_documento ILIKE '%%compra%%' 
              OR mi.tipo_documento ILIKE '%%proveedor%%' 
              OR mi.referencia_tipo ILIKE '%%proveedor%%'
          )
          AND mi.asiento_contrapartida_id IS NULL
          AND (LEFT(mc.cuenta, 2) IN ('22', '23', '11')) AND mc.tipo = 'credito'
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
              OR mi.referencia_id::text = mc.numero_documento
          );
    """)
    conn.commit()

    # D1. Producción MP y PT
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_inventario_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND (mi.referencia_tipo ILIKE '%%produc%%' OR mi.tipo_documento ILIKE '%%produc%%' OR mi.tipo_documento ILIKE '%%ensamble%%')
          AND mi.asiento_inventario_id IS NULL
          AND mc.cuenta LIKE '14%%'
          AND (
              (mi.tipo = 'salida' AND mc.tipo = 'credito')
              OR (mi.tipo = 'entrada' AND mc.tipo = 'debito')
          )
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND mi.producto_id = mc.producto_id;
    """)
    conn.commit()

    # E1. Ajustes de Inventario
    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_inventario_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND (mi.referencia_tipo ILIKE '%%ajuste%%' OR mi.tipo_documento ILIKE '%%ajuste%%')
          AND mi.asiento_inventario_id IS NULL
          AND mc.cuenta LIKE '14%%'
          AND (
              (mi.tipo = 'salida' AND mc.tipo = 'credito')
              OR (mi.tipo = 'entrada' AND mc.tipo = 'debito')
          )
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          )
          AND mi.producto_id = mc.producto_id;
    """)
    conn.commit()

    conn.execute("""
        UPDATE movimientos_inventario mi
        SET asiento_contrapartida_id = mc.id
        FROM movimientos_contables mc
        WHERE mi.negocio_id = mc.negocio_id
          AND (mi.referencia_tipo ILIKE '%%ajuste%%' OR mi.tipo_documento ILIKE '%%ajuste%%')
          AND mi.asiento_contrapartida_id IS NULL
          AND (LEFT(mc.cuenta, 2) IN ('53', '42', '61'))
          AND (
              (mi.tipo = 'salida' AND mc.tipo = 'debito')
              OR (mi.tipo = 'entrada' AND mc.tipo = 'credito')
          )
          AND (
              mi.documento_numero = mc.numero_documento 
              OR mi.documento_numero = SPLIT_PART(mc.numero_documento, '-', 2) 
              OR mc.numero_documento = SPLIT_PART(mi.documento_numero, '-', 2)
          );
    """)
    conn.commit()

    # 3. ESTADÍSTICAS REALES EN PRODUCCIÓN
    stats = conn.execute("""
        SELECT 
            count(*) as total_movimientos,
            count(asiento_inventario_id) as con_asiento_inventario,
            count(asiento_contrapartida_id) as con_asiento_contrapartida,
            count(CASE WHEN asiento_inventario_id IS NOT NULL AND asiento_contrapartida_id IS NOT NULL THEN 1 END) as mapeo_completo_ambos
        FROM movimientos_inventario;
    """).fetchone()

    total_movs = stats['total_movimientos']
    print("\n" + "="*70)
    print("      RESULTADO DE LA MIGRACIÓN EN LA BASE DE DATOS DE PRODUCCIÓN")
    print("="*70)
    print(f"• Total Movimientos Inventario: {total_movs}")
    print(f"• Con Asiento Inventario (14*): {stats['con_asiento_inventario']} ({(stats['con_asiento_inventario']/total_movs*100):.1f}%)")
    print(f"• Con Asiento Contrapartida:   {stats['con_asiento_contrapartida']} ({(stats['con_asiento_contrapartida']/total_movs*100):.1f}%)")
    print(f"• Mapeo 100% Completo (Ambos): {stats['mapeo_completo_ambos']} ({(stats['mapeo_completo_ambos']/total_movs*100):.1f}%)")
    print("======================================================================")

if __name__ == '__main__':
    main()
