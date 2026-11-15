"""Regression: hallazgo de costo absurdo en linea de entrada con solucion.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_entrada_hallazgo_costo.py
Backend (stub conn, sin BD): _auditar_linea_costo detecta posible error
  de digitacion con ref sana = mediana ultimas 5 compras; propone
  cantidad sugerida cuando el factor >=10x (o <=0.1x).
Frontend (estatico): entradas+admin consultan validar-costo en vivo,
  muestran tarjeta explicita con boton Usar-sugerencia e Ignorar.
Regla: ante costo absurdo el algoritmo avisa + propone, no calla.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.blueprints import inventarios as INV  # noqa: E402

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


class _Cur:
    def __init__(self, one, all_):
        self._one = one
        self._all = all_

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class _Conn:
    def __init__(self, one, all_):
        self._one = one
        self._all = all_

    def execute(self, sql, params=()):
        return _Cur(self._one, self._all)


TOL = {'tol': 15.0}
HIST = [{'valor_unitario': v} for v in (5.0, 2.59, 5.18, 5.18, 5.16)]

check('helper existe', hasattr(INV, '_auditar_linea_costo'))
H = getattr(INV, '_auditar_linea_costo', lambda *a, **k: 'SIN-HELPER')

h = H(_Conn(TOL, HIST), 59, 298, 25000000, 25900)
check('carbon 25M -> hallazgo', isinstance(h, dict) and h.get('cantidad_sugerida') == 5019)
check('carbon factor huge', isinstance(h, dict) and h.get('factor', 0) > 1000)
check('linea sana -> None', H(_Conn(TOL, HIST), 59, 298, 5000, 25900) is None)
check('sin historial -> None', H(_Conn(TOL, [{'valor_unitario': 5.18}]), 59, 298, 25000000, 25900) is None)
check('total cero -> None', H(_Conn(TOL, HIST), 59, 298, 5000, 0) is None)
check('cantidad cero -> None', H(_Conn(TOL, HIST), 59, 298, 0, 25900) is None)

import inspect  # noqa: E402
check('save advierte hallazgo', 'Posible error de digitaci' in inspect.getsource(INV._registrar_entrada_inventario))

EN = (ROOT / 'templates' / 'entradas.html').read_text(encoding='utf-8')
AD = (ROOT / 'templates' / 'inventario_admin.html').read_text(encoding='utf-8')
check('entradas consulta validar-costo', 'validar-costo' in EN and 'function verificarHallazgoCosto' in EN)
check('entradas boton usar+ignorar', 'aplicarHallazgoCosto' in EN and 'ignorarHallazgoCosto' in EN)
check('admin consulta validar-costo', 'validar-costo' in AD and 'function verificarHallazgoCosto' in AD)
check('admin boton usar+ignorar', 'aplicarHallazgoCosto' in AD and 'ignorarHallazgoCosto' in AD)

N = 12
print(f'{N - len(fails)}/{N} checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
