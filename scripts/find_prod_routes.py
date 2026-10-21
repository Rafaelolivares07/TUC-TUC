with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\inventarios.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if '/api/inventario/producto/' in line or 'api_inventario_producto' in line:
        print(f"Line {idx+1}: {line.strip()}")
