import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('templates/caja.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines, 1):
    if 'id=' in l and 'flash' in l:
        print(f"{i}: {l.strip()[:100]}")
