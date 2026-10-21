with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\caja.html', 'r', encoding='utf-8') as f:
    caja = f.readlines()

for idx, line in enumerate(caja):
    if 'fecha-documento' in line:
        print(f"Line {idx+1}: {line.strip()}")
