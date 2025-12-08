import requests
import json

# Configuración
GOOGLE_API_KEY = 'AIzaSyCiAtNFl95bJJFuqiNsiYynBS3LuDisq9g'
SEARCH_ENGINE_ID = '40c8305664a9147e9'

# Medicamento de prueba
medicamento = "antalgine"

print(f">> Buscando informacion sobre: {medicamento}")
print("-" * 50)

# 1. Buscar en Google Custom Search
query = f"{medicamento} medicamento presentacion fabricante colombia"
url_api = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={SEARCH_ENGINE_ID}&q={query}&num=5"

print(f"\n>> Consultando Google Custom Search API...")
resp = requests.get(url_api, timeout=10)

if resp.status_code == 200:
    data = resp.json()
    items = data.get("items", [])
    print(f"OK Resultados encontrados: {len(items)}\n")

    # Mostrar resultados
    for i, item in enumerate(items, 1):
        print(f"{i}. {item.get('title', 'Sin titulo')}")
        print(f"   {item.get('snippet', 'Sin descripcion')}")
        print(f"   Link: {item.get('link', '')}\n")

    # 2. Intentar usar Gemini para analizar
    print("\n" + "=" * 50)
    print(">> Probando Gemini API...")
    print("=" * 50)

    # Combinar información de los resultados
    contexto = "\n".join([
        f"{item.get('title', '')} - {item.get('snippet', '')}"
        for item in items
    ])

    # URL de Gemini API
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GOOGLE_API_KEY}"

    prompt = f"""Basándote en la siguiente información sobre un medicamento:

{contexto}

Extrae y responde ÚNICAMENTE en formato JSON sin texto adicional:
{{
    "nombre_completo": "nombre del medicamento con presentación completa (ej: ACETAMINOFEN 500MG TABLETAS)",
    "fabricante": "nombre del laboratorio o fabricante más mencionado",
    "confianza": "alta/media/baja según la certeza de la información"
}}

Si no encuentras información clara, usa "confianza": "baja"."""

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    headers = {
        "Content-Type": "application/json"
    }

    gemini_resp = requests.post(gemini_url, json=payload, headers=headers, timeout=15)

    if gemini_resp.status_code == 200:
        gemini_data = gemini_resp.json()

        # Extraer texto de respuesta
        if 'candidates' in gemini_data and len(gemini_data['candidates']) > 0:
            texto_respuesta = gemini_data['candidates'][0]['content']['parts'][0]['text']
            print(f"\nOK Respuesta de Gemini:\n{texto_respuesta}")

            # Intentar parsear JSON
            try:
                # Limpiar markdown si existe
                if '```json' in texto_respuesta:
                    texto_respuesta = texto_respuesta.split('```json')[1].split('```')[0]
                elif '```' in texto_respuesta:
                    texto_respuesta = texto_respuesta.split('```')[1].split('```')[0]

                resultado = json.loads(texto_respuesta.strip())
                print(f"\n>> RESULTADO PARSEADO:")
                print(f"   Nombre completo: {resultado.get('nombre_completo')}")
                print(f"   Fabricante: {resultado.get('fabricante')}")
                print(f"   Confianza: {resultado.get('confianza')}")
            except Exception as e:
                print(f"\n!! No se pudo parsear JSON: {e}")
        else:
            print(f"!! Respuesta vacia de Gemini")
            print(f"Respuesta completa: {json.dumps(gemini_data, indent=2)}")
    else:
        print(f"ERROR Gemini API: {gemini_resp.status_code}")
        print(f"Respuesta: {gemini_resp.text}")
else:
    print(f"ERROR Google Search: {resp.status_code}")
    print(f"Respuesta: {resp.text}")
