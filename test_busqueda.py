"""Test de búsqueda de productos en PostgreSQL"""
import os
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

load_dotenv()

database_url = os.getenv('DATABASE_URL')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Test simple de búsqueda
query = '''
SELECT DISTINCT
    m.id as medicamento_id,
    m.nombre,
    f.nombre as fabricante,
    p.precio
FROM "MEDICAMENTOS" m
INNER JOIN "PRECIOS" p ON m.id = p.medicamento_id
LEFT JOIN "FABRICANTES" f ON p.fabricante_id = f.id
WHERE LOWER(m.nombre) LIKE %s
AND m.activo = 1
AND p.precio > 0
ORDER BY m.nombre
LIMIT 5
'''

try:
    conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cursor = conn.cursor()

    # Buscar medicamentos que contengan "acetaminofen"
    cursor.execute(query, ('%acetaminofen%',))
    resultados = cursor.fetchall()

    print(f"Resultados encontrados: {len(resultados)}")
    for r in resultados:
        print(f"  - {r['nombre']} ({r['fabricante']}) - ${r['precio']}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
