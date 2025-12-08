import sqlite3
import html
import webbrowser
import requests
import re

DB_PATH = "medicamentos.db"
GOOGLE_API_KEY = 'AIzaSyCiAtNFl95bJJFuqiNsiYynBS3LuDisq9g'
SEARCH_ENGINE_ID = '40c8305664a9147e9'

def obtener_medicamentos():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, nombre FROM medicamentos ORDER BY id LIMIT 10")
    data = cur.fetchall()
    conn.close()
    return [{"id": row[0], "nombre": row[1]} for row in data]

def buscar_con_google(nombre):
    """Busca usando Google Custom Search API."""
    palabras = nombre.split()
    medicamento = palabras[0]
    
    sitios = ["locatelcolombia.com", "farmatodo.com.co", "cruzverde.com.co", "larebajavirtual.com"]  
    query_con_sitios = f"{medicamento} precio " + " OR ".join([f"site:{s}" for s in sitios])
    query_sin_sitios = f"{medicamento} precio farmacia colombia"
    
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&q={query_con_sitios}&num=10"
    
    print(f"   🔍 Buscando: {medicamento}")
    
    try:
        resp = requests.get(url, timeout=10)
        print(f"   📡 Status: {resp.status_code}")
        if resp.status_code != 200:
            return []
        
        items = resp.json().get("items", [])
        print(f"   📊 Google devolvió {len(items)} resultados")  # <--- AQUÍ
        # Si no hay resultados, buscar SIN restricción de sitios
        if not items:
            print(f"   🔄 Buscando en cualquier sitio...")
            url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&q={query_sin_sitios}&num=10"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
        
        # Si aún no hay, intentar con 2 palabras
        if not items and len(palabras) >= 2:
            medicamento = f"{palabras[0]} {palabras[1]}"
            query = f"{medicamento} precio farmacia colombia"
            url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&q={query}&num=10"
            print(f"   🔄 Reintentando con: {medicamento}")
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
        
        patron_precio = re.compile(r'\$\s*(\d{1,3}(?:[.,]\d{3})+)|\$\s*(\d{4,7})\b')
        resultados = []
        
        for item in items[:5]:
            titulo = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")

            print(f"   🔎 Título: {titulo[:50]}...")
            print(f"   📝 Snippet: {snippet[:80]}...")  # <--- AGREGA ESTO
            texto = f"{titulo} {snippet}"
            match = patron_precio.search(texto)
            
            if match:
                precio_str = match.group(1) or match.group(2)
                precio_limpio = re.sub(r'[.,\s]', '', precio_str)
                precio = int(precio_limpio)
                
                sitio = "Otro"
                link_lower = link.lower()
                if "locatel" in link_lower:
                    sitio = "Locatel"
                elif "farmatodo" in link_lower:
                    sitio = "Farmatodo"
                elif "cruzverde" in link_lower:
                    sitio = "Cruz Verde"
                elif "larebaja" in link_lower:
                    sitio = "La Rebaja"
                elif "cafam" in link_lower:
                    sitio = "Cafam"
                
                resultados.append({
                    "nombre": titulo,
                    "precio": f"${precio:,}",
                    "url": link,
                    "sitio": sitio
                })
        
        return resultados
        
    except Exception as e:
        print(f"   ⚠️ Error: {str(e)[:60]}")
        return []

def generar_html(resultados):
    html_code = """
    <html>
    <head>
      <meta charset="utf-8">
      <title>Reporte Medicamentos</title>
      <style>
        body { font-family: Arial; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        h1 { color: #007b5e; text-align: center; }
        .med-section { margin: 20px 0; }
        .med-header { background: #007b5e; color: white; padding: 10px; border-radius: 5px; }
        .resultado { background: #f9f9f9; padding: 10px; margin: 5px 0; border-left: 3px solid #007b5e; }
        .precio { color: #007b5e; font-weight: bold; font-size: 1.2em; }
        a { color: #007b5e; text-decoration: none; }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>🏥 Búsqueda de Medicamentos</h1>
    """
    
    for med, items in resultados.items():
        if items:
            html_code += f"""
            <div class="med-section">
                <div class="med-header">📦 {html.escape(med)} - {len(items)} resultados</div>
            """
            
            for it in items:
                html_code += f"""
                <div class="resultado">
                    <div><strong>{html.escape(it['nombre'][:80])}</strong></div>
                    <div class="precio">{html.escape(it['precio'])} - {html.escape(it['sitio'])}</div>
                    <div><a href="{html.escape(it['url'])}" target="_blank">Ver producto →</a></div>
                </div>
                """
            
            html_code += "</div>"
    
    html_code += """
      </div>
    </body>
    </html>
    """
    
    with open("reporte_locatel.html", "w", encoding="utf-8") as f:
        f.write(html_code)
    
    print("\n✅ Reporte generado: reporte_locatel.html")
    webbrowser.open("reporte_locatel.html")

def main():
    print("\n🔍 Buscando medicamentos...\n")
    
    meds = obtener_medicamentos()
    resultados = {}
    
    for i, med in enumerate(meds, 1):
        nombre = med["nombre"]
        print(f"[{i}/{len(meds)}] ➡️ {nombre}")
        
        items = buscar_con_google(nombre)
        resultados[nombre] = items
        
        if items:
            print(f"   ✅ {len(items)} resultados\n")
        else:
            print(f"   ⚠️ Sin resultados\n")
    
    generar_html(resultados)
    print("\n✅ LISTO!\n")

if __name__ == "__main__":
    main()