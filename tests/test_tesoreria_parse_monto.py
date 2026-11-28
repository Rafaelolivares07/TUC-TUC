# -*- coding: utf-8 -*-
"""Tesoreria: parser es-CO de montos. El patron viejo leia 27.627.561,00 como 27.6."""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PANE = os.path.join(ROOT, 'templates', 'tesoreria_transacciones_pane.html')
fails = []
total = [0]


def check(nombre, cond):
    total[0] += 1
    print(('PASS' if cond else 'FAIL'), nombre)
    if not cond:
        fails.append(nombre)


part = open(PANE, encoding='utf-8').read()

check('parser existe', 'function tes_parseMontoEsCO' in part)
check('cero patrones viejos', part.count("replace(/[^0-9.]/g, '')") == 0)
check('9 sitios usan parser', part.count('tes_parseMontoEsCO(') >= 10)

# Comportamiento real: extraer la funcion del pane y correrla en node.
CASOS = [
    ("27.627.561,00", 27627561.0),
    ("1.234,56", 1234.56),
    ("27.627", 27627.0),
    ("27627561", 27627561.0),
    ("27,627,561.00", 27627561.0),
    ("27.62", 27.62),
    ("$27.627,50", 27627.5),
    ("", 0.0),
    ("abc", 0.0),
]

m = re.search(r'function tes_parseMontoEsCO\(v\) \{', part)
if not m:
    check('node: funcion extraible', False)
else:
    i = part.index('{', m.start())
    depth = 0
    end = None
    for j in range(i, len(part)):
        if part[j] == '{':
            depth += 1
        elif part[j] == '}':
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    check('node: funcion extraible', end is not None)
    if end is not None:
        func_src = part[m.start():end]
        js = func_src + "\nconst CASOS = %s;\nCASOS.forEach(c => console.log(JSON.stringify(tes_parseMontoEsCO(c))));\n" % json.dumps([c[0] for c in CASOS])
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as fh:
                fh.write(js)
                tmp = fh.name
            r = subprocess.run(['node', tmp], capture_output=True, text=True, timeout=30)
            got = (r.stdout or '').strip().split('\n') if r.returncode == 0 else []
            ok = len(got) == len(CASOS)
            if ok:
                for (inp, esp), g in zip(CASOS, got):
                    try:
                        if abs(float(g) - esp) > 0.001:
                            ok = False
                            print('  caso %r -> %s (esperaba %s)' % (inp, g, esp))
                    except ValueError:
                        ok = False
            else:
                print('  node rc=%s err=%s' % (r.returncode, (r.stderr or '')[:200]))
            check('node: 9 casos es-CO/en/plano', ok)
        except Exception as e:
            print('  node error:', e)
            check('node: 9 casos es-CO/en/plano', False)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

print('%d/%d checks' % (total[0] - len(fails), total[0]))
sys.exit(1 if fails else 0)
