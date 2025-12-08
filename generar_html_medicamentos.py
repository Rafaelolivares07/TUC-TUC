import sqlite3
import json
import os

# === CONFIGURACIÓN ===
DB_PATH = 'medicamentos.db'          # Ajusta si tu base tiene otro nombre
HTML_OUTPUT = 'medicamentos_busqueda.html'

# === CONEXIÓN Y EXTRACCIÓN ===
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Productos únicos: cada fila en PRECIOS es un producto
cur.execute("""
    SELECT
        p.id,
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
        'id': row['id'],
        'nombre': row['nombre_medicamento'],
        'fabricante': row['fabricante'],
        'precio': row['precio'] or 0,
        'imagen': row['imagen'] or ''
    })

# Síntomas por medicamento_id
cur.execute("""
    SELECT ms.medicamento_id, s.nombre
    FROM medicamento_sintoma ms
    JOIN sintomas s ON ms.sintoma_id = s.id
""")
sintomas_dict = {}
for row in cur.fetchall():
    mid = row[0]
    if mid not in sintomas_dict:
        sintomas_dict[mid] = []
    sintomas_dict[mid].append(row[1])

# Relación producto → medicamento_id
cur.execute("SELECT id, medicamento_id FROM precios")
prod_to_med = {r[0]: r[1] for r in cur.fetchall()}

# Asignar síntomas a cada producto
for p in productos:
    med_id = prod_to_med.get(p['id'])
    p['sintomas'] = sintomas_dict.get(med_id, [])

conn.close()

# === GENERAR HTML ===
html_content = f'''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Medicamentos – Búsqueda por Síntoma</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
      margin: 0; padding: 16px;
      background: #f8f9fa;
      color: #212529;
    }}
    h1 {{
      text-align: center;
      font-size: 1.3em;
      margin: 0 0 16px;
      color: #1a73e8;
    }}
    #search {{
      width: 100%;
      padding: 12px 16px;
      font-size: 1em;
      border: 1px solid #ddd;
      border-radius: 12px;
      box-sizing: border-box;
      margin-bottom: 16px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    .product {{
      background: white;
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 14px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      border-left: 4px solid #1a73e8;
    }}
    .name {{
      font-weight: bold;
      font-size: 1.1em;
      margin-bottom: 6px;
      color: #111;
    }}
    .price {{
      color: #2e7d32;
      font-weight: bold;
      margin: 6px 0;
    }}
    .symptoms {{
      font-size: 0.92em;
      color: #555;
      line-height: 1.4;
    }}
    #results {{
      max-height: 75vh;
      overflow-y: auto;
    }}
    .no-results {{
      text-align: center;
      padding: 30px 20px;
      color: #777;
    }}
  </style>
</head>
<body>
  <h1>Busca por medicamento, síntoma o fabricante</h1>
  <input type="text" id="search" placeholder="Ej: dol, ibupro, fiebre, Bayer..." autofocus autocomplete="off" />
  <div id="results"></div>

  <script>
    const productos = {json.dumps(productos, ensure_ascii=False, indent=2)};

    function normalize(str) {{
      return str.toLowerCase()
                .normalize("NFD")
                .replace(/[\\u0300-\\u036f]/g, "")
                .trim();
    }}

    function buscar(termino) {{
      const t = normalize(termino);
      if (!t) {{
        document.getElementById('results').innerHTML = '';
        return;
      }}

      const resultados = productos.filter(p => {{
        const texto = `${{p.nombre}} ${{p.fabricante}} ${{p.sintomas.join(' ')}}`;
        return normalize(texto).includes(t);
      }});

      mostrarResultados(resultados);
    }}

    function mostrarResultados(lista) {{
      const div = document.getElementById('results');
      if (lista.length === 0) {{
        div.innerHTML = '<div class="no-results">No se encontraron resultados para "<strong>' + 
                        document.getElementById("search").value + 
                        '</strong>".</div>';
        return;
      }}

      div.innerHTML = lista.map(p => `
        <div class="product">
          <div class="name">${{p.nombre}} <small>(${{p.fabricante}})</small></div>
          <div class="price">$${{p.precio.toLocaleString('es-CO')}}</div>
          <div class="symptoms"><strong>Síntomas:</strong> ${{p.sintomas.length ? p.sintomas.join(', ') : '—'}}</div>
        </div>
      `).join('');
    }}

    document.getElementById('search').addEventListener('input', (e) => {{
      buscar(e.target.value);
    }});
  </script>
</body>
</html>
'''

# Guardar
with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ Archivo generado: {os.path.abspath(HTML_OUTPUT)}")
print("➡️  Pásalo a tu celular y compártelo por WhatsApp como documento.")