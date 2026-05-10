import urllib.request, json

url = "https://admin.tuc-tuc.co/agenda/merlin?token=merlin-agenda-2026"
with urllib.request.urlopen(url) as r:
    data = json.loads(r.read())

pendientes = [i for i in data['items'] if not i['completado']]
completados = [i for i in data['items'] if i['completado']]

print(f"=== AGENDA ({len(pendientes)} pendientes) ===")
for i in pendientes:
    fecha = f"  [{i['fecha_limite']}]" if i['fecha_limite'] else ""
    print(f"[{i['id']}] {i['texto']}{fecha}")
if completados:
    print(f"\n--- Completadas ({len(completados)}) ---")
    for i in completados:
        print(f"[{i['id']}] {i['texto']}")
