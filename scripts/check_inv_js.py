import re, subprocess, os

with open('templates/inventario_admin.html', 'r', encoding='utf-8') as fh:
    html = fh.read()

scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', html, re.DOTALL)
print('Total scripts:', len(scripts))

has_err = False
for i, s in enumerate(scripts):
    clean = re.sub(r'\{\{.*?\}\}', '""', s)
    clean = re.sub(r'\{%.*?%\}', '', clean)
    fn = f'_test_script_{i}.js'
    with open(fn, 'w', encoding='utf-8') as out:
        out.write(clean)
    res = subprocess.run(['node', '--check', fn], capture_output=True, text=True)
    if res.returncode != 0:
        print(f'Script {i} ERROR:')
        print(res.stderr)
        has_err = True
    else:
        print(f'Script {i}: OK')
    if os.path.exists(fn):
        os.remove(fn)

if not has_err:
    print('ALL SCRIPTS SYNTAX OK!')
