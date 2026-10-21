import os, re

base_dir = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app'
for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8') as file_obj:
                content = file_obj.read()
                if 'INSERT INTO productos' in content or 'INSERT INTO catalogo_productos' in content:
                    print(f"Found in {f}")
