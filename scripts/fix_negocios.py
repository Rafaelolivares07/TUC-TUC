import os

path = r"C:\Users\RAFAEL OLIVARES\Documents\tuctucv2\app\blueprints\negocios.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Fix unterminated f-string
code = code.replace(
    'return f"{base}\nAtendio: {nombre_cajero}"',
    'return f"{base}\\nAtendio: {nombre_cajero}"'
)

# Fix indentation of centros_rows
code = code.replace(
    '    ).fetchone()\n        centros_rows = []',
    '    ).fetchone()\n    centros_rows = []'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Fixed syntax in negocios.py")
