with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\caja.html', 'r', encoding='utf-8') as f:
    caja_content = f.read()

for line in caja_content.splitlines():
    if 'fecha' in line.lower() and ('fetch' in line.lower() or 'body:' in line.lower() or 'json.stringify' in line.lower() or 'payload' in line.lower() or 'data' in line.lower()):
        print("caja.html line:", line)

with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\vendedor_pedido.html', 'r', encoding='utf-8') as f:
    vp_content = f.read()

for line in vp_content.splitlines():
    if 'fecha' in line.lower() and ('fetch' in line.lower() or 'body:' in line.lower() or 'json.stringify' in line.lower() or 'payload' in line.lower() or 'data' in line.lower()):
        print("vendedor_pedido.html line:", line)
