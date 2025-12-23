#!/usr/bin/env python3
"""
Script para ejecutar la migración de recordatorios en PostgreSQL
"""
import psycopg2
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def ejecutar_migracion():
    """Ejecuta la migración SQL para recordatorios"""

    # Obtener URL de base de datos
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("[ERROR] DATABASE_URL no encontrada en .env")
        return False

    # Render usa postgres://, pero psycopg2 necesita postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    try:
        # Conectar a PostgreSQL
        print("[*] Conectando a PostgreSQL...")
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cursor = conn.cursor()

        # Leer archivo de migración
        print("[*] Leyendo migracion_recordatorios.sql...")
        with open('migracion_recordatorios.sql', 'r', encoding='utf-8') as f:
            sql = f.read()

        # Ejecutar migración
        print("[*] Ejecutando migracion...")
        cursor.execute(sql)

        # Commit
        conn.commit()
        print("[OK] Migracion ejecutada exitosamente")

        # Verificar columnas agregadas
        print("\n[*] Verificando columnas agregadas...")

        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'terceros' AND column_name = 'telegram_chat_id'
        """)
        result = cursor.fetchone()
        if result:
            print(f"  [OK] terceros.telegram_chat_id: {result[1]} (nullable: {result[2]})")

        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'pastillero_usuarios'
            AND column_name IN ('horas_entre_tomas', 'proxima_toma', 'recordatorio_activo')
            ORDER BY column_name
        """)
        results = cursor.fetchall()
        for row in results:
            print(f"  [OK] pastillero_usuarios.{row[0]}: {row[1]} (nullable: {row[2]})")

        cursor.close()
        conn.close()

        print("\n[SUCCESS] Migracion completada con exito!")
        return True

    except Exception as e:
        print(f"[ERROR] Error al ejecutar migracion: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRACION: Sistema de Recordatorios de Medicamentos")
    print("=" * 60)
    print()

    exito = ejecutar_migracion()

    if exito:
        print("\n[OK] Todo listo para implementar recordatorios")
    else:
        print("\n[ERROR] La migracion fallo. Revisa los errores arriba.")
