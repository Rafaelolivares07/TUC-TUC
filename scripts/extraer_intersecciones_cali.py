"""
Script para extraer intersecciones de calles/carreras de Cali desde OpenStreetMap
usando Overpass API
"""

import requests
import json
import time

# ID de Cali en OSM: 8811628
# Para usar en area(): 3600000000 + 8811628 = 3608811628

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def obtener_vias_con_nodos():
    """
    Obtiene todas las vías de Cali con sus nodos (para calcular intersecciones)
    """
    query = """
    [timeout:300][out:json];
    area(3608811628)->.cali;
    way["highway"]["name"~"Calle|Carrera|Avenida|Diagonal|Transversal",i](area.cali);
    out body;
    >;
    out skel qt;
    """

    print("Consultando Overpass API (esto puede tardar 2-5 minutos)...")
    response = requests.post(OVERPASS_URL, data={"data": query})

    if response.status_code == 200:
        data = response.json()
        return data.get("elements", [])
    else:
        print(f"Error: {response.status_code}")
        return []


def procesar_intersecciones(elementos):
    """
    Procesa los elementos de OSM y encuentra todas las intersecciones
    """
    # Separar nodos y ways
    nodos = {}
    ways = []

    for elem in elementos:
        if elem["type"] == "node":
            nodos[elem["id"]] = {
                "lat": elem["lat"],
                "lon": elem["lon"]
            }
        elif elem["type"] == "way":
            ways.append(elem)

    print(f"  Nodos: {len(nodos)}, Vías: {len(ways)}")

    # Crear índice de nodos -> ways
    nodo_a_ways = {}
    for way in ways:
        nombre = way.get("tags", {}).get("name", "")
        if not nombre:
            continue

        for nodo_id in way.get("nodes", []):
            if nodo_id not in nodo_a_ways:
                nodo_a_ways[nodo_id] = []
            nodo_a_ways[nodo_id].append(nombre)

    # Encontrar intersecciones (nodos que pertenecen a 2+ vías diferentes)
    intersecciones = []
    for nodo_id, vias in nodo_a_ways.items():
        vias_unicas = list(set(vias))
        if len(vias_unicas) >= 2 and nodo_id in nodos:
            coord = nodos[nodo_id]
            intersecciones.append({
                "nodo_id": nodo_id,
                "lat": coord["lat"],
                "lon": coord["lon"],
                "via_1": vias_unicas[0],
                "via_2": vias_unicas[1],
                "todas_las_vias": vias_unicas
            })

    return intersecciones


if __name__ == "__main__":
    print("=== Extractor de Intersecciones de Cali ===\n")

    print("Obteniendo vías con nodos desde OpenStreetMap...")
    elementos = obtener_vias_con_nodos()
    print(f"Elementos obtenidos: {len(elementos)}")

    if len(elementos) > 0:
        print("\nProcesando intersecciones...")
        intersecciones = procesar_intersecciones(elementos)
        print(f"Intersecciones encontradas: {len(intersecciones)}")

        # Guardar en archivo JSON
        archivo_salida = "scripts/intersecciones_cali.json"
        with open(archivo_salida, "w", encoding="utf-8") as f:
            json.dump(intersecciones, f, ensure_ascii=False, indent=2)

        print(f"\nDatos guardados en {archivo_salida}")

        # Mostrar algunas intersecciones de ejemplo
        print("\nEjemplos de intersecciones:")
        for inter in intersecciones[:15]:
            print(f"  - {inter['via_1']} con {inter['via_2']}: ({inter['lat']:.6f}, {inter['lon']:.6f})")
    else:
        print("No se obtuvieron datos. Verifique la conexión.")
