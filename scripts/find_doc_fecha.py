import os, re

files = [
    r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\restaurantes.py',
    r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\tiendas.py',
    r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\inventarios.py',
]

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"\n=== {os.path.basename(file)} ===")
    for m in re.finditer(r'documento_fecha\s*[:=]\s*([^\n,]+)', content):
        print(f"Line approx match: {m.group(0)}")
