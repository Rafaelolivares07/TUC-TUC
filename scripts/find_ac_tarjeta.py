with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\inventario_admin.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'tarjeta-ac-input' in line or 'clearSelectedComponent' in line or 'tarjeta-selected-chip' in line or 'tarjeta-ac-id' in line or 'setupTarjetaAutocomplete' in line or 'abrirModalTarjeta' in line:
        print(f"Line {idx+1}: {line.encode('ascii', 'replace').decode('ascii').strip()}")
