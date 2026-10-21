with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\tiendas.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        if 'INSERT INTO productos' in line or 'DELETE FROM productos' in line or 'UPDATE productos' in line:
            print(f"tiendas.py line {idx+1}: {line.strip()}")

with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\restaurantes.py', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        if 'INSERT INTO productos' in line or 'DELETE FROM productos' in line or 'UPDATE productos' in line:
            print(f"restaurantes.py line {idx+1}: {line.strip()}")
