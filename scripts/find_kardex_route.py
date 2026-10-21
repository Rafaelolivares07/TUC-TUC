with open(r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\app\blueprints\inventarios.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if '/kardex' in line or 'def ' in line and 'kardex' in line.lower():
        print(f"Line {idx+1}: {line.strip()}")
