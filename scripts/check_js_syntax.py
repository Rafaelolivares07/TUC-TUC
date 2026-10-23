import re

with open('templates/chat_v3.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace Jinja tags cleanly
html_clean = re.sub(r'\{%.*?%\}', '/* jinja */', html)
# replace '{{ ... }}' with 'jinja_var'
html_clean = re.sub(r'["\']\{\{.*?\}\}["\']', '"jinja_var"', html_clean)
html_clean = re.sub(r'\{\{.*?\}\}', '0', html_clean)

scripts = re.findall(r'<script>(.*?)</script>', html_clean, re.DOTALL)
print(f"Found {len(scripts)} script blocks.")

for idx, s in enumerate(scripts):
    fn = f'temp_script_{idx}.js'
    with open(fn, 'w', encoding='utf-8') as sf:
        sf.write(s)
    print(f"Wrote {fn}")
