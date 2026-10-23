import re, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.blueprints.crm import _GLOBO_CHAT_SNIPPET

start = _GLOBO_CHAT_SNIPPET.find('<script>') + len('<script>')
end = _GLOBO_CHAT_SNIPPET.find('</script>')
js_code = _GLOBO_CHAT_SNIPPET[start:end]

with open('temp_globo.js', 'w', encoding='utf-8') as f:
    f.write(js_code)

print("Wrote temp_globo.js")
