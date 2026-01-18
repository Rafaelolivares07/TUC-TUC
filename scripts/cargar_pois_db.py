"""
Script para cargar POIs extraídos de OpenStreetMap a la base de datos PostgreSQL.
Crea la tabla pois_cali y carga los datos del archivo JSON.
"""

import json
import os
import sys

# Agregar el directorio padre al path para importar get_db_connection
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def procesar_elementos(elementos):
    """Procesa los elementos raw de Overpass y los convierte a formato uniforme"""

    pois = []
    ids_vistos = set()

    for elem in elementos:
        # Obtener coordenadas
        if elem.get('type') == 'node':
            lat = elem.get('lat')
            lon = elem.get('lon')
        elif elem.get('type') == 'way' and 'center' in elem:
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

        # Evitar duplicados por nombre + ubicación aproximada
        clave = f"{nombre.lower()}_{round(lat, 4)}_{round(lon, 4)}"
        if clave in ids_vistos:
            continue
        ids_vistos.add(clave)

        # Determinar categoría y subcategoría
        categoria = None
        subcategoria = None

        for cat_key in ['amenity', 'shop', 'tourism', 'leisure', 'office', 'healthcare', 'building', 'place']:
            if cat_key in tags:
                categoria = cat_key
                subcategoria = tags[cat_key]
                break

        # Construir dirección
        direccion_parts = []
        if tags.get('addr:street'):
            direccion_parts.append(tags['addr:street'])
        if tags.get('addr:housenumber'):
            direccion_parts.append('#' + tags['addr:housenumber'])

        direccion = ' '.join(direccion_parts) if direccion_parts else ''

        # Construir display_name
        display_parts = [nombre]
        if direccion:
            display_parts.append(direccion)
        barrio = tags.get('addr:suburb', tags.get('addr:neighbourhood', ''))
        if barrio:
            display_parts.append(barrio)
        display_parts.append('Cali')

        display_name = ', '.join(display_parts)

        poi = {
            'osm_id': elem.get('id'),
            'nombre': nombre,
            'lat': lat,
            'lon': lon,
            'categoria': categoria,
            'subcategoria': subcategoria,
            'direccion': direccion,
            'display_name': display_name,
            'barrio': barrio,
        }

        pois.append(poi)

    return pois


def main():
    # Importar conexión a BD
    from main_medicamentos import get_db_connection

    # Cargar JSON
    archivo_json = 'scripts/pois_cali_raw.json'
    print(f"Cargando {archivo_json}...")

    with open(archivo_json, 'r', encoding='utf-8') as f:
        elementos = json.load(f)

    print(f"Elementos raw: {len(elementos)}")

    # Procesar
    print("Procesando elementos...")
    pois = procesar_elementos(elementos)
    print(f"POIs procesados (sin duplicados): {len(pois)}")

    # Conectar a BD
    print("Conectando a la base de datos...")
    conn = get_db_connection()

    # Crear tabla
    print("Creando tabla pois_cali...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pois_cali (
            id SERIAL PRIMARY KEY,
            osm_id BIGINT,
            nombre VARCHAR(255) NOT NULL,
            lat DECIMAL(10, 8) NOT NULL,
            lon DECIMAL(11, 8) NOT NULL,
            categoria VARCHAR(50),
            subcategoria VARCHAR(100),
            direccion VARCHAR(255),
            display_name TEXT,
            barrio VARCHAR(100),
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Crear índices
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pois_nombre ON pois_cali(LOWER(nombre));")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pois_categoria ON pois_cali(categoria);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pois_coords ON pois_cali(lat, lon);")

    # Limpiar datos anteriores
    print("Limpiando datos anteriores...")
    conn.execute("DELETE FROM pois_cali;")

    # Insertar POIs
    print(f"Insertando {len(pois)} POIs...")
    insertados = 0

    for poi in pois:
        try:
            conn.execute("""
                INSERT INTO pois_cali (osm_id, nombre, lat, lon, categoria, subcategoria, direccion, display_name, barrio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                poi['osm_id'],
                poi['nombre'],
                poi['lat'],
                poi['lon'],
                poi['categoria'],
                poi['subcategoria'],
                poi['direccion'],
                poi['display_name'],
                poi['barrio']
            ))
            insertados += 1

            if insertados % 500 == 0:
                print(f"  {insertados} insertados...")

        except Exception as e:
            print(f"Error insertando {poi['nombre']}: {e}")

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"¡CARGA COMPLETADA!")
    print(f"POIs insertados: {insertados}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
