import os

for fname in ["tiendas.py", "restaurantes.py"]:
    path = os.path.join(r"C:\Users\RAFAEL OLIVARES\Documents\tuctucv2\app\blueprints", fname)
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    code = code.replace('return f"{base}\nAtendio: {nombre_cajero}"', 'return f"{base}\\nAtendio: {nombre_cajero}"')
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)

print("Fixed raw newlines in tiendas.py and restaurantes.py")
