"""
Script para probar la búsqueda de intersección más cercana a unas coordenadas
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Conexión directa a PostgreSQL"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL no configurada")
    return psycopg2.connect(database_url)


def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia en metros entre dos puntos usando la fórmula de Haversine
    """
    R = 6371000  # Radio de la Tierra en metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def buscar_interseccion_cercana(lat, lon, radio_metros=100):
    """
    Busca la intersección más cercana a las coordenadas dadas.

    Args:
        lat: Latitud del punto
        lon: Longitud del punto
        radio_metros: Radio máximo de búsqueda en metros (default 100m)

    Returns:
        dict con la intersección encontrada o None
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Convertir radio a grados aproximados (1 grado ≈ 111km en el ecuador)
    radio_grados = radio_metros / 111000

    # Buscar intersecciones dentro de un cuadrado de búsqueda
    cursor.execute("""
        SELECT id, lat, lon, via_1, via_2, direccion_completa
        FROM intersecciones_cali
        WHERE lat BETWEEN %s AND %s
          AND lon BETWEEN %s AND %s
    """, (
        lat - radio_grados, lat + radio_grados,
        lon - radio_grados, lon + radio_grados
    ))

    resultados = cursor.fetchall()
    conn.close()

    if not resultados:
        return None

    # Calcular distancia real a cada intersección y encontrar la más cercana
    mejor = None
    menor_distancia = float('inf')

    for row in resultados:
        id_, lat_inter, lon_inter, via_1, via_2, direccion = row
        distancia = calcular_distancia_metros(lat, lon, float(lat_inter), float(lon_inter))

        if distancia < menor_distancia:
            menor_distancia = distancia
            mejor = {
                'id': id_,
                'lat': float(lat_inter),
                'lon': float(lon_inter),
                'via_1': via_1,
                'via_2': via_2,
                'direccion': direccion,
                'distancia_metros': round(distancia, 1)
            }

    # Solo retornar si está dentro del radio
    if mejor and mejor['distancia_metros'] <= radio_metros:
        return mejor
    return None


def probar_coordenadas():
    """Prueba con varias coordenadas de ejemplo"""

    # Coordenadas de prueba en Cali
    pruebas = [
        # Centro de Cali (cerca de Carrera 4 con Calle 11)
        (3.4516, -76.5320, "Centro de Cali"),
        # Sur de Cali (cerca de Carrera 48 con Calle 42)
        (3.4034, -76.5174, "Sur - Carrera 48"),
        # Norte de Cali
        (3.4750, -76.5000, "Norte de Cali"),
        # Coordenada aleatoria
        (3.4188, -76.5393, "Prueba aleatoria"),
    ]

    print("=== Pruebas de búsqueda de intersección cercana ===\n")

    for lat, lon, descripcion in pruebas:
        print(f"Buscando cerca de: {descripcion} ({lat}, {lon})")

        # Probar con diferentes radios
        for radio in [50, 100, 200]:
            resultado = buscar_interseccion_cercana(lat, lon, radio_metros=radio)

            if resultado:
                print(f"  Radio {radio}m: SI - {resultado['direccion']} (a {resultado['distancia_metros']}m)")
                break
            else:
                print(f"  Radio {radio}m: NO - No encontrada")

        print()


def buscar_interactivo():
    """Permite buscar intersecciones de forma interactiva"""
    print("\n=== Búsqueda interactiva ===")
    print("Ingrese coordenadas para buscar la intersección más cercana")
    print("Formato: latitud,longitud (ej: 3.4034,-76.5174)")
    print("Escriba 'salir' para terminar\n")

    while True:
        entrada = input("Coordenadas: ").strip()

        if entrada.lower() == 'salir':
            break

        try:
            lat, lon = map(float, entrada.split(','))

            resultado = buscar_interseccion_cercana(lat, lon, radio_metros=150)

            if resultado:
                print(f"\n  ✓ Intersección encontrada:")
                print(f"    {resultado['direccion']}")
                print(f"    Coordenadas: ({resultado['lat']}, {resultado['lon']})")
                print(f"    Distancia: {resultado['distancia_metros']} metros\n")
            else:
                print(f"\n  ✗ No se encontró intersección en un radio de 150m\n")

        except ValueError:
            print("  Error: Formato inválido. Use: latitud,longitud\n")


if __name__ == "__main__":
    probar_coordenadas()

    # Descomentar para modo interactivo
    # buscar_interactivo()
