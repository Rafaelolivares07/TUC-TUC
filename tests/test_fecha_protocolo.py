"""Regression: protocolo fecha — motor unico, gate inventario, preview auditorias.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_fecha_protocolo.py
Protocolo: fecha se mueve por documento completo con el mismo veredicto
desde cualquier evento; mantenimiento delega a inventario solo si aplica;
auditorias previsualizan impacto antes de guardar.
"""
import inspect
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


def src(name):
    return inspect.getsource(getattr(INV, name)) if hasattr(INV, name) else ''


SRC_MV = src('_mover_fecha_documento')
SRC_RD = src('_recostear_productos_detalle')
SRC_A = src('api_cambiar_fecha_documento_inventario')
SRC_B = src('api_modificar_documento_mantenimiento')

check('motor fecha existe', hasattr(INV, '_mover_fecha_documento'))
check('motor toca MI+saldos+MC',
      'UPDATE movimientos_inventario' in SRC_MV
      and 'UPDATE saldo_por_documentos' in SRC_MV
      and 'UPDATE movimientos_contables' in SRC_MV)
check('detalle compartido con afectados',
      hasattr(INV, '_recostear_productos_detalle') and "'afectados'" in SRC_RD)
check('kardex delega al motor', '_mover_fecha_documento(' in SRC_A)
check('mantenimiento delega al motor', '_mover_fecha_documento(' in SRC_B)
check('mantenimiento gate inventario', 'tiene_inventario' in SRC_B)
check('motor aplica veredicto periodo', '_veredicto_cambio_fecha(' in SRC_MV)
check('kardex respuesta intacta', "'productos_detalle'" in SRC_A)

AUD = (ROOT / 'templates' / 'auditor_documentos.html').read_text(encoding='utf-8')
MAN = (ROOT / 'templates' / 'mantenimiento_admin.html').read_text(encoding='utf-8')
check('auditor previsualiza impacto',
      'verificar-cambio-fecha' in AUD and 'det-impacto-fecha' in AUD)
check('mant previsualiza impacto',
      'verificar-cambio-fecha' in MAN and 'aud-impacto-fecha' in MAN)

N = 10
print(f'{N - len(fails)}/{N} checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
