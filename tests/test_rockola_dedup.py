# -*- coding: utf-8 -*-
"""Rockola: dedup de descargas YouTube (10/11).

Caso Rafa: 'Abrazame Muy Fuerte' se descargó 4 veces (mismo video, distinto
item_id) porque /resolver descargaba sin mirar si el video ya estaba en disco.
/resolver ahora canoniza el video (ID) y reusa el archivo existente de la sala.
La cola no cambia (cada pedido sigue siendo una entrada).
Uso: python tests/test_rockola_dedup.py (raiz TucTucV2)
"""
import os
import subprocess
import sys

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = open(os.path.join(ROOT, 'app', 'blueprints', 'rockola.py'), encoding='utf-8').read()

# 1. Marcadores
check('existe _canon_youtube', 'def _canon_youtube(' in PY)
check('existe _buscar_descarga_existente', 'def _buscar_descarga_existente(' in PY)
_ini = PY.find('def resolver(')
_fin = PY.find('\n@bp.route', _ini + 10)
RES = PY[_ini:_fin] if _ini >= 0 and _fin > _ini else ''
check('resolver canoniza target', '_canon_youtube(target_url)' in RES)
check('resolver reusa con cache', RES.count('cache=True') >= 2)
check('reuso excluye item propio', 'excluir_id' in PY)
check('reuso acota consulta', 'LIMIT 500' in PY)

# 2. Funcional: _canon_youtube sobre casos reales
try:
    _a = PY.index('def _canon_youtube(')
    _b = len(PY)
    for _m in ('\ndef ', '\n@bp.route', '\nclass '):
        _p = PY.find(_m, _a + 10)
        if _p > 0:
            _b = min(_b, _p)
    _ns = {}
    exec(PY[_a:_b], _ns)
    canon = _ns['_canon_youtube']
    base = canon('https://www.youtube.com/watch?v=ABC123xyz_-&t=30s')
    check('watch vs youtu.be', base and base == canon('https://youtu.be/ABC123xyz_-'))
    check('watch vs shorts', base == canon('https://www.youtube.com/shorts/ABC123xyz_-'))
    check('watch vs movil', base == canon('https://m.youtube.com/watch?v=ABC123xyz_-'))
    check('watch vs embed', base == canon('https://www.youtube.com/embed/ABC123xyz_-'))
    check('distinto video difiere', base != canon('https://youtu.be/OTRO4567890'))
    check('vacio/None/bulro -> None',
          canon('') is None and canon(None) is None and canon('notaurl') is None)
except Exception as e:
    check('harness canon', False, f'{type(e).__name__}: {e}')

# 3. py_compile
r = subprocess.run([sys.executable, '-m', 'py_compile',
                    os.path.join(ROOT, 'app', 'blueprints', 'rockola.py')],
                   capture_output=True, text=True, timeout=120)
check('py_compile rockola.py', r.returncode == 0, (r.stderr or '')[:200])

print(f'--- {total[0] - len(fails)}/{total[0]} OK ---')
sys.exit(1 if fails else 0)
