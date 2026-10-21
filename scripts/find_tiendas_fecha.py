with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\tiendas.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'documento_fecha' in line or 'fecha_pedido' in line:
        print(f"Line {idx+1}: {line.strip()}")
