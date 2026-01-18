"""
Script para extraer TODOS los puntos de interés (POI) de Cali desde OpenStreetMap
usando Overpass API.

Extrae: comercios, restaurantes, farmacias, bancos, colegios, iglesias, etc.
"""

import requests
import json
import time

# Bounding box de Cali (un poco más amplio para incluir alrededores)
# Sur, Oeste, Norte, Este
CALI_BBOX = "3.30,-76.60,3.55,-76.45"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def extraer_pois():
    """Extrae todos los POIs con nombre en Cali"""

    # Query Overpass para extraer TODOS los nodos y ways con nombre
    # que sean amenities, shops, tourism, leisure, etc.
    query = f"""
    [out:json][timeout:300];
    (
      // Amenities (restaurantes, bancos, farmacias, hospitales, colegios, etc.)
      node["amenity"]["name"](3.30,-76.60,3.55,-76.45);
      way["amenity"]["name"](3.30,-76.60,3.55,-76.45);

      // Shops (tiendas, supermercados, etc.)
      node["shop"]["name"](3.30,-76.60,3.55,-76.45);
      way["shop"]["name"](3.30,-76.60,3.55,-76.45);

      // Tourism (hoteles, museos, etc.)
      node["tourism"]["name"](3.30,-76.60,3.55,-76.45);
      way["tourism"]["name"](3.30,-76.60,3.55,-76.45);

      // Leisure (parques, gimnasios, etc.)
      node["leisure"]["name"](3.30,-76.60,3.55,-76.45);
      way["leisure"]["name"](3.30,-76.60,3.55,-76.45);

      // Offices (oficinas, empresas)
      node["office"]["name"](3.30,-76.60,3.55,-76.45);
      way["office"]["name"](3.30,-76.60,3.55,-76.45);

      // Healthcare (clínicas, consultorios)
      node["healthcare"]["name"](3.30,-76.60,3.55,-76.45);
      way["healthcare"]["name"](3.30,-76.60,3.55,-76.45);

      // Buildings con nombre (centros comerciales, edificios importantes)
      node["building"]["name"](3.30,-76.60,3.55,-76.45);
      way["building"]["name"](3.30,-76.60,3.55,-76.45);

      // Lugares específicos
      node["place"]["name"](3.30,-76.60,3.55,-76.45);
      way["place"]["name"](3.30,-76.60,3.55,-76.45);
    );
    out center;
    """

    print("Enviando consulta a Overpass API...")
    print("Esto puede tomar varios minutos...")

    try:
        response = requests.post(
            OVERPASS_URL,
            data={'data': query},
            timeout=600  # 10 minutos de timeout
        )
        response.raise_for_status()
        data = response.json()

        elementos = data.get('elements', [])
        print(f"Elementos recibidos: {len(elementos)}")

        return elementos

    except requests.exceptions.Timeout:
        print("ERROR: Timeout en la consulta. Intentando con consultas más pequeñas...")
        return extraer_pois_por_partes()
    except Exception as e:
        print(f"ERROR: {e}")
        return []


def extraer_pois_por_partes():
    """Si la consulta completa falla, extraer por categorías"""

    categorias = [
        ('amenity', 'Amenities (restaurantes, bancos, farmacias...)'),
        ('shop', 'Tiendas y comercios'),
        ('tourism', 'Turismo (hoteles, museos...)'),
        ('leisure', 'Ocio (parques, gimnasios...)'),
        ('office', 'Oficinas'),
        ('healthcare', 'Salud'),
    ]

    todos_elementos = []

    for tag, descripcion in categorias:
        print(f"\nExtrayendo: {descripcion}")

        query = f"""
        [out:json][timeout:180];
        (
          node["{tag}"]["name"](3.30,-76.60,3.55,-76.45);
          way["{tag}"]["name"](3.30,-76.60,3.55,-76.45);
        );
        out center;
        """

        try:
            response = requests.post(
                OVERPASS_URL,
                data={'data': query},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()

            elementos = data.get('elements', [])
            print(f"  -> {len(elementos)} elementos")
            todos_elementos.extend(elementos)

            # Esperar entre consultas para no sobrecargar
            time.sleep(2)

        except Exception as e:
            print(f"  -> ERROR: {e}")
            continue

    return todos_elementos


def procesar_elementos(elementos):
    """Procesa los elementos de Overpass y los convierte a formato uniforme"""

    pois = []
    ids_vistos = set()

    for elem in elementos:
        # Obtener coordenadas
        if elem['type'] == 'node':
            lat = elem.get('lat')
            lon = elem.get('lon')
        elif elem['type'] == 'way' and 'center' in elem:
            lat = elem['center'].get('lat')
            lon = elem['center'].get('lon')
        else:
            continue

        if not lat or not lon:
            continue

        tags = elem.get('tags', {})
        nombre = tags.get('name', '').strip()

        if not nombre:
            continue

        # Evitar duplicados
        clave = f"{nombre.lower()}_{round(lat, 5)}_{round(lon, 5)}"
        if clave in ids_vistos:
            continue
        ids_vistos.add(clave)

        # Determinar categoría
        categoria = None
        subcategoria = None

        if 'amenity' in tags:
            categoria = 'amenity'
            subcategoria = tags['amenity']
        elif 'shop' in tags:
            categoria = 'shop'
            subcategoria = tags['shop']
        elif 'tourism' in tags:
            categoria = 'tourism'
            subcategoria = tags['tourism']
        elif 'leisure' in tags:
            categoria = 'leisure'
            subcategoria = tags['leisure']
        elif 'office' in tags:
            categoria = 'office'
            subcategoria = tags['office']
        elif 'healthcare' in tags:
            categoria = 'healthcare'
            subcategoria = tags['healthcare']
        elif 'building' in tags:
            categoria = 'building'
            subcategoria = tags['building']
        elif 'place' in tags:
            categoria = 'place'
            subcategoria = tags['place']

        # Construir dirección
        direccion_parts = []
        if tags.get('addr:street'):
            direccion_parts.append(tags['addr:street'])
        if tags.get('addr:housenumber'):
            direccion_parts.append(tags['addr:housenumber'])

        direccion = ', '.join(direccion_parts) if direccion_parts else ''

        # Construir display_name
        display_parts = [nombre]
        if direccion:
            display_parts.append(direccion)
        if tags.get('addr:city'):
            display_parts.append(tags['addr:city'])
        else:
            display_parts.append('Cali')

        display_name = ', '.join(display_parts)

        poi = {
            'osm_id': elem.get('id'),
            'osm_type': elem.get('type'),
            'nombre': nombre,
            'lat': lat,
            'lon': lon,
            'categoria': categoria,
            'subcategoria': subcategoria,
            'direccion': direccion,
            'display_name': display_name,
            'telefono': tags.get('phone', tags.get('contact:phone', '')),
            'website': tags.get('website', tags.get('contact:website', '')),
            'horario': tags.get('opening_hours', ''),
            'barrio': tags.get('addr:suburb', tags.get('addr:neighbourhood', '')),
        }

        pois.append(poi)

    return pois


def guardar_json(pois, archivo):
    """Guarda los POIs en un archivo JSON"""
    with open(archivo, 'w', encoding='utf-8') as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"Guardado: {archivo}")


def mostrar_estadisticas(pois):
    """Muestra estadísticas de los POIs extraídos"""

    print("\n" + "="*50)
    print("ESTADÍSTICAS DE EXTRACCIÓN")
    print("="*50)
    print(f"Total POIs: {len(pois)}")

    # Por categoría
    categorias = {}
    for poi in pois:
        cat = poi.get('categoria', 'otro')
        categorias[cat] = categorias.get(cat, 0) + 1

    print("\nPor categoría:")
    for cat, count in sorted(categorias.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Por subcategoría (top 20)
    subcategorias = {}
    for poi in pois:
        sub = poi.get('subcategoria', 'otro')
        subcategorias[sub] = subcategorias.get(sub, 0) + 1

    print("\nTop 20 subcategorías:")
    for sub, count in sorted(subcategorias.items(), key=lambda x: -x[1])[:20]:
        print(f"  {sub}: {count}")


if __name__ == '__main__':
    print("="*50)
    print("EXTRACCIÓN DE POIs DE CALI")
    print("="*50)

    # Extraer elementos
    elementos = extraer_pois()

    if not elementos:
        print("No se pudieron extraer elementos")
        exit(1)

    # Procesar
    print("\nProcesando elementos...")
    pois = procesar_elementos(elementos)

    # Estadísticas
    mostrar_estadisticas(pois)

    # Guardar
    archivo_salida = 'scripts/pois_cali.json'
    guardar_json(pois, archivo_salida)

    print("\n" + "="*50)
    print("¡EXTRACCIÓN COMPLETADA!")
    print(f"Archivo: {archivo_salida}")
    print(f"Total POIs: {len(pois)}")
    print("="*50)
