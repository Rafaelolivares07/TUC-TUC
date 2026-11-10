# -*- coding: utf-8 -*-
"""Static: redirect uploads ausentes a Cloudinary (10/11).

Fase 2 de liberacion de disco: las 371 fotos de static/uploads viven en
Cloudinary; si el archivo no esta en local, /static/uploads/<f> responde 301
a la nube (mapa app/uploads_cloud_map.json). Mientras el local exista, se
sirve local (cero cambio de conducta). Sin BD, sin nginx.
Uso: python tests/test_static_cloud_redirect.py (raiz TucTucV2)
"""
import json
import os
import subprocess
import sys
import tempfile

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = open(os.path.join(ROOT, 'app', '__init__.py'), encoding='utf-8').read()
MAPA_P = os.path.join(ROOT, 'app', 'uploads_cloud_map.json')

# 1. Marcadores
check('existe _resolver_static_cloud', 'def _resolver_static_cloud(' in INIT)
check('wrapper engancha static', "app.view_functions['static']" in INIT)
check('wrapper firma filename (Flask lo llama por kw)', 'def _static_con_cloud(filename)' in INIT)
check('wrapper delega por kw (lambda Flask 3)', '_orig_static(filename=filename)' in INIT)
check('redirect 301 cacheable', 'redirect(' in INIT and 'immutable' in INIT)
check('mapa existe', os.path.exists(MAPA_P))
try:
    MAPA = json.load(open(MAPA_P, encoding='utf-8'))
    check('mapa 371 entradas', len(MAPA) == 371, f'n={len(MAPA)}')
    _u0 = next(iter(MAPA.values()))
    _url0 = _u0.get('url') if isinstance(_u0, dict) else _u0
    check('mapa urls cloudinary', str(_url0).startswith('https://res.cloudinary.com/'))
except Exception as e:
    check('mapa legible', False, f'{type(e).__name__}: {e}')
    MAPA = {}

# 2. Funcional: helper aislado sobre dir temporal
try:
    _a = INIT.index('def _resolver_static_cloud(')
    _b = len(INIT)
    for _m in ('\ndef ', '\nclass ', '\n@'):
        _p = INIT.find(_m, _a + 10)
        if _p > 0:
            _b = min(_b, _p)
    _ns = {'os': os}
    exec(INIT[_a:_b], _ns)
    res = _ns['_resolver_static_cloud']
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'uploads'))
        with open(os.path.join(tmp, 'uploads', 'quedo.png'), 'w') as f:
            f.write('x')
        _mapa = {'falta.png': {'url': 'https://res.cloudinary.com/demo/falta'}}
        check('no-uploads -> None', res('js/app.js', tmp, _mapa) is None)
        check('local existe -> None', res('uploads/quedo.png', tmp, _mapa) is None)
        check('ausente en mapa -> url', res('uploads/falta.png', tmp, _mapa) == 'https://res.cloudinary.com/demo/falta')
        check('ausente sin mapa -> None', res('uploads/otra.png', tmp, _mapa) is None)
        check('traversal -> None', res('uploads/../x.png', tmp, _mapa) is None)
        check('subruta -> None', res('uploads/a/b.png', tmp, _mapa) is None)
except Exception as e:
    check('harness resolver', False, f'{type(e).__name__}: {e}')

# 3. py_compile
r = subprocess.run([sys.executable, '-m', 'py_compile',
                    os.path.join(ROOT, 'app', '__init__.py')],
                   capture_output=True, text=True, timeout=120)
check('py_compile __init__.py', r.returncode == 0, (r.stderr or '')[:200])

print(f'--- {total[0] - len(fails)}/{total[0]} OK ---')
sys.exit(1 if fails else 0)
