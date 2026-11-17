"""Regression: globo de conteo vive adentro de la tira de auditoria.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_kardex_globo_auditoria.py
Pin estatico sobre kardex_js.html + kardex.html (sin BD/DOM):
  renderizarAuditoriaKardex
Regla: el globo de conteo (100% Coinciden BD/SEDE/TABLA) se muda
adentro de la tira de auditoria en cada render: se desprende antes
de reconstruir el innerHTML (si no, el rebuild lo destruye) y se
reinserta tras el grupo Auditoria, sin ml-auto de la fila vieja.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / 'templates' / 'partials' / 'kardex_js.html'
HTML = ROOT / 'templates' / 'kardex.html'

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


js = JS.read_text(encoding='utf-8')
html = HTML.read_text(encoding='utf-8')

ini = js.find('function renderizarAuditoriaKardex')
fin = js.find('\nfunction renderizarBodegasKardex')
cuerpo = js[ini:fin] if ini >= 0 and fin > ini else ''

check('funcion localizada', bool(cuerpo))
check('mueve el globo', 'kardex-conteo-cotejo' in cuerpo)
check('desprende antes del rebuild', '.remove()' in cuerpo)
check('reinserta en la fila', 'insertBefore' in cuerpo)
check('sin ml-auto viejo', "classList.remove('ml-auto')" in cuerpo
      or 'classList.remove("ml-auto")' in cuerpo)
check('nodo existe al cargar', 'id="kardex-conteo-cotejo"' in html)

print(f'--- {len(fails)} fallos ---')
sys.exit(1 if fails else 0)
