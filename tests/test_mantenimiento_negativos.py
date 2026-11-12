# -*- coding: utf-8 -*-
"""Rastreo solo-lectura de negativos MC/MI (caso Rafa 11/11: F4 barrido).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_mantenimiento_negativos.py
GET /api/inventario/<neg>/mantenimiento/negativos: lista montos negativos
sin escribir nada. Nacio del debito -3110.97 de FV-650.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


PY = (ROOT / 'app' / 'blueprints' / 'inventarios.py').read_text(encoding='utf-8')
_ini = PY.find('def api_mantenimiento_negativos(')
_fin = PY.find('\ndef ', _ini + 10)
FN = PY[_ini:_fin] if _ini >= 0 and _fin > _ini else ''
check('existe endpoint', bool(FN))
check('ruta GET',
      "@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/negativos', methods=['GET'])"
      in PY)
check('solo lectura MC', 'mc.monto < 0' in FN)
check('solo lectura MI', 'valor_total < 0' in FN)
check('sin escrituras',
      all(k not in FN for k in ('INSERT INTO', 'UPDATE ', 'DELETE FROM')))
check('con limite', 'LIMIT' in FN)
check('trae comprobante', 'comprobante_id' in FN)
check('trae created_at', 'created_at' in FN)
check('trae cuenta', 'mc.cuenta' in FN)
check('requiere sesion', "'usuario_id' not in session" in FN)
check('respuesta ok', "'mc_negativos'" in FN and "'mi_negativos'" in FN)

r = subprocess.run([sys.executable, '-m', 'py_compile',
                    str(ROOT / 'app' / 'blueprints' / 'inventarios.py')],
                   capture_output=True, text=True, timeout=120)
check('py_compile inventarios.py', r.returncode == 0, (r.stderr or '')[:200])

print(f'{total[0] - len(fails)}/{total[0]} checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
