import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.blueprints.crm import _GLOBO_CHAT_SNIPPET

start = _GLOBO_CHAT_SNIPPET.find('<script>') + len('<script>')
end = _GLOBO_CHAT_SNIPPET.find('</script>')
js_code = _GLOBO_CHAT_SNIPPET[start:end]

lines = js_code.split('\n')
for i, l in enumerate(lines):
    sq = l.count("'")
    dq = l.count('"')
    if sq % 2 != 0:
        print(f"Line {i+1} has odd single quotes: {repr(l)}")
    if dq % 2 != 0:
        print(f"Line {i+1} has odd double quotes: {repr(l)}")
print("Syntax check finished.")
