"""
Script para crear la tabla de intersecciones y cargar los datos desde el JSON
"""

import json
import os
import sys

# Agregar el directorio padre al path para importar get_db_connection
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Para conexión directa a PostgreSQL
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Conexión directa a PostgreSQL"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL no configurada")

    conn = psycopg2.connect(database_url)
    return conn


def crear_tabla_intersecciones(conn):
    """Crea la tabla de intersecciones si no existe"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intersecciones_cali (
            id SERIAL PRIMARY KEY,
            nodo_osm_id BIGINT,
            lat DECIMAL(10, 7) NOT NULL,
            lon DECIMAL(10, 7) NOT NULL,
            via_1 VARCHAR(100) NOT NULL,
            via_2 VARCHAR(100) NOT NULL,
            direccion_completa VARCHAR(250),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Crear índice espacial para búsquedas rápidas por coordenadas
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_intersecciones_coords
        ON intersecciones_cali (lat, lon)
    """)

    # Crear índice para búsquedas por nombre de vía
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_intersecciones_via1
        ON intersecciones_cali (via_1)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_intersecciones_via2
        ON intersecciones_cali (via_2)
    """)

    conn.commit()
    print("Tabla intersecciones_cali creada correctamente")


def cargar_intersecciones(conn, archivo_json):
    """Carga las intersecciones desde el archivo JSON"""
    cursor = conn.cursor()

    # Limpiar tabla existente
    cursor.execute("DELETE FROM intersecciones_cali")

    # Cargar datos del JSON
    with open(archivo_json, 'r', encoding='utf-8') as f:
        intersecciones = json.load(f)

    print(f"Cargando {len(intersecciones)} intersecciones...")

    # Preparar datos para inserción masiva
    datos = []
    for inter in intersecciones:
        direccion_completa = f"{inter['via_1']} con {inter['via_2']}"
        datos.append((
            inter.get('nodo_id'),
            inter['lat'],
            inter['lon'],
            inter['via_1'],
            inter['via_2'],
            direccion_completa
        ))

    # Inserción masiva
    execute_values(
        cursor,
        """
        INSERT INTO intersecciones_cali
        (nodo_osm_id, lat, lon, via_1, via_2, direccion_completa)
        VALUES %s
        """,
        datos,
        page_size=1000
    )

    conn.commit()
    print(f"Se cargaron {len(datos)} intersecciones correctamente")


def verificar_datos(conn):
    """Verifica que los datos se cargaron correctamente"""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM intersecciones_cali")
    total = cursor.fetchone()[0]
    print(f"\nTotal de intersecciones en la BD: {total}")

    cursor.execute("""
        SELECT via_1, via_2, lat, lon, direccion_completa
        FROM intersecciones_cali
        LIMIT 10
    """)

    print("\nEjemplos de intersecciones:")
    for row in cursor.fetchall():
        print(f"  - {row[4]}: ({row[2]}, {row[3]})")


if __name__ == "__main__":
    # Ruta al archivo JSON
    script_dir = os.path.dirname(os.path.abspath(__file__))
    archivo_json = os.path.join(script_dir, "intersecciones_cali.json")

    if not os.path.exists(archivo_json):
        print(f"Error: No se encontró el archivo {archivo_json}")
        sys.exit(1)

    print("=== Cargador de Intersecciones de Cali ===\n")

    conn = get_db_connection()

    try:
        crear_tabla_intersecciones(conn)
        cargar_intersecciones(conn, archivo_json)
        verificar_datos(conn)
    finally:
        conn.close()

    print("\n¡Proceso completado!")
