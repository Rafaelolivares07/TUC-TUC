#!/usr/bin/env python3
"""
Script para ejecutar migraciones manualmente en producción
"""
import os
import psycopg2

def main():
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("❌ ERROR: DATABASE_URL no está configurada")
        return

    print(f"📡 Conectando a base de datos...")

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        print("✅ Conexión exitosa")
        print("\n🔧 Ejecutando migraciones...")

        # Migración 1: costo_unitario en existencias
        print("  1. Agregando costo_unitario a tabla existencias...")
        cur.execute("ALTER TABLE existencias ADD COLUMN IF NOT EXISTS costo_unitario DECIMAL(10,2) DEFAULT 0")
        print("     ✓ Completado")

        # Migración 2: costo_unitario en precios
        print("  2. Agregando costo_unitario a tabla precios...")
        cur.execute("ALTER TABLE precios ADD COLUMN IF NOT EXISTS costo_unitario DECIMAL(10,2) DEFAULT 0")
        print("     ✓ Completado")

        # Migración 3: activo en precios_competencia
        print("  3. Agregando activo a tabla precios_competencia...")
        cur.execute("ALTER TABLE precios_competencia ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE")
        print("     ✓ Completado")

        # Migración 4: inactivo_hasta en precios_competencia
        print("  4. Agregando inactivo_hasta a tabla precios_competencia...")
        cur.execute("ALTER TABLE precios_competencia ADD COLUMN IF NOT EXISTS inactivo_hasta TIMESTAMP")
        print("     ✓ Completado")

        # Commit
        conn.commit()
        print("\n✅ TODAS LAS MIGRACIONES COMPLETADAS EXITOSAMENTE")

        # Verificar columnas
        print("\n🔍 Verificando columnas creadas...")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'existencias' AND column_name = 'costo_unitario'
        """)
        result = cur.fetchone()
        if result:
            print(f"   ✓ existencias.costo_unitario: {result[1]}")
        else:
            print(f"   ✗ existencias.costo_unitario: NO ENCONTRADA")

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'precios' AND column_name = 'costo_unitario'
        """)
        result = cur.fetchone()
        if result:
            print(f"   ✓ precios.costo_unitario: {result[1]}")
        else:
            print(f"   ✗ precios.costo_unitario: NO ENCONTRADA")

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'precios_competencia' AND column_name = 'activo'
        """)
        result = cur.fetchone()
        if result:
            print(f"   ✓ precios_competencia.activo: {result[1]}")
        else:
            print(f"   ✗ precios_competencia.activo: NO ENCONTRADA")

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'precios_competencia' AND column_name = 'inactivo_hasta'
        """)
        result = cur.fetchone()
        if result:
            print(f"   ✓ precios_competencia.inactivo_hasta: {result[1]}")
        else:
            print(f"   ✗ precios_competencia.inactivo_hasta: NO ENCONTRADA")

        conn.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
