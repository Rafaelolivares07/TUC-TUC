#!/usr/bin/env python3
"""
Script para ejecutar la migración de categorías en PostgreSQL.
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def ejecutar_migracion():
    """Ejecuta la migración SQL para categorías"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("[ERROR] DATABASE_URL no configurada")
        return False

    # Convertir postgres:// a postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("=" * 60)
    print("MIGRACION: Sistema de Categorías Parametrizables")
    print("=" * 60)
    print()

    try:
        print("[*] Conectando a PostgreSQL...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("[OK] Conexion establecida")
        print()

        # Leer archivo SQL
        print("[*] Leyendo migracion_categorias.sql...")
        with open('migracion_categorias.sql', 'r', encoding='utf-8') as f:
            sql = f.read()
        print("[OK] Archivo leido")
        print()

        # Ejecutar migración
        print("[*] Ejecutando migracion...")
        cursor.execute(sql)
        conn.commit()
        print("[OK] Migracion ejecutada exitosamente")
        print()

        # Verificar que las tablas se crearon
        print("[*] Verificando tablas creadas...")

        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'categorias'
            ORDER BY ordinal_position
        """)
        print("\n  Tabla: categorias")
        columnas = cursor.fetchall()
        for col in columnas:
            nullable = "nullable: YES" if col[2] == 'YES' else "nullable: NO"
            print(f"    [OK] {col[0]}: {col[1]} ({nullable})")

        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'medicamento_categoria'
            ORDER BY ordinal_position
        """)
        print("\n  Tabla: medicamento_categoria")
        columnas = cursor.fetchall()
        for col in columnas:
            nullable = "nullable: YES" if col[2] == 'YES' else "nullable: NO"
            print(f"    [OK] {col[0]}: {col[1]} ({nullable})")

        print()
        print("[SUCCESS] Migracion completada con exito!")
        print()
        print("[OK] Sistema de categorias listo")
        print()

        conn.close()
        return True

    except Exception as e:
        print(f"[ERROR] Error en migracion: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    ejecutar_migracion()
