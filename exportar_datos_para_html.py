import sqlite3
import json

conn = sqlite3.connect('medicamentos.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Obtener todos los productos como registros únicos desde PRECIOS
cur.execute("""
    SELECT
        p.id AS producto_id,
        m.nombre AS nombre_medicamento,
        f.nombre AS fabricante,
        p.precio,
        p.imagen
    FROM precios p
    JOIN medicamentos m ON p.medicamento_id = m.id
    JOIN fabricantes f ON p.fabricante_id = f.id
    WHERE m.activo = 1
""")
productos = []
for row in cur.fetchall():
    productos.append({
        'id': row['producto_id'],
        'nombre': row['nombre_medicamento'],
        'fabricante': row['fabricante'],
        'precio': row['precio'],
        'imagen': row['imagen'] or ''
    })

# Obtener síntomas por medicamento (usamos medicamento_id, no producto_id)
cur.execute("""
    SELECT ms.medicamento_id, s.nombre
    FROM medicamento_sintoma ms
    JOIN sintomas s ON ms.sintoma_id = s.id
""")
sintomas_por_medicamento = {}
for row in cur.fetchall():
    mid = row[0]
    if mid not in sintomas_por_medicamento:
        sintomas_por_medicamento[mid] = []
    sintomas_por_medicamento[mid].append(row[1])

# Asociar síntomas a cada producto (usando medicamento_id desde la tabla precios)
cur.execute("SELECT id, medicamento_id FROM precios")
relacion_producto_medicamento = {r[0]: r[1] for r in cur.fetchall()}

# Añadir síntomas a cada producto
for prod in productos:
    med_id = relacion_producto_medicamento.get(prod['id'])
    prod['sintomas'] = sintomas_por_medicamento.get(med_id, [])

# Construir índice inverso: síntoma → lista de productos
sintoma_a_productos = {}
for prod in productos:
    nombre_completo = f"{prod['nombre']} ({prod['fabricante']})"
    for s in prod['sintomas']:
        if s not in sintoma_a_productos:
            sintoma_a_productos[s] = []
        sintoma_a_productos[s].append({
            'nombre': nombre_completo,
            'precio': prod['precio'],
            'imagen': prod['imagen']
        })

# Exportar
data = {
    "productos": productos,
    "sintoma_a_productos": sintoma_a_productos
}

with open('datos_medicamentos.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("✅ Archivo 'datos_medicamentos.json' generado con productos únicos.")
conn.close()