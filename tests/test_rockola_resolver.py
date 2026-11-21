"""Regression: /resolver cobalt con timeout realista (2026-10-31 noche).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  python tests/test_rockola_resolver.py
Cubre: instancia viva primero (liubquanti) + timeout POST >= 20s
(la viva tarda >6s y el timeout viejo la mataba) + descarga a disco +
respuesta /archivo + error honesto si todo cae.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


py = (ROOT / 'app/blueprints/rockola.py').read_text(encoding='utf-8')

_ic = py.find('COBALT_APIS = [')
CB = py[_ic:py.find('\n]\n', _ic)] if _ic > -1 else ''
_if = py.find('def _descargar_youtube_con_cobalt(')
FN = py[_if:py.find('\n\n\ndef ', _if)] if _if > -1 else ''

check('resolver: viva primero', CB.find('liubquanti') > -1
      and CB.find('liubquanti') < CB.find('melon.clxxped'))
check('resolver: timeout realista', 'timeout=25' in FN and 'timeout=6' not in FN)
check('resolver: descarga disco', "open(tmp_path, 'wb')" in FN
      and 'timeout=120' in FN)
_ir = py.find('def resolver(')
RZ = py[_ir:py.find('\n\n\n@bp.route', _ir)] if _ir > -1 else ''
check('resolver: responde archivo', '/archivo/' in RZ and "descarga[\"path\"]" in RZ)
check('resolver: error honesto', 'ok=False' in RZ)

# 2026-11-21: 0-byte no se sirve ni se guarda (envenenaba cache)
check('resolver: helper bytes', 'def _archivo_audio_valido(' in py
      and 'getsize(path) > 1000' in py)
check('resolver: cache honesto', '_archivo_audio_valido(ruta)' in RZ
      and 'os.remove(ruta)' in RZ)
check('resolver: descarga valida', '_archivo_audio_valido(descarga["path"])' in RZ
      and 'Descarga vacia' in RZ)

print(f'\n{len(fails)} fallos' if fails else '\nOK: 8/8')
sys.exit(1 if fails else 0)
