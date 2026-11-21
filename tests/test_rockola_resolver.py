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
check('resolver: descarga disco', "open(parte, 'wb')" in FN
      and 'timeout=120' in FN and 'os.replace(parte, tmp_path)' in FN)
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

# 2026-11-21: in-flight (no duplicar descargas) + atomicas (no servir parciales)
_ip = py.find('def _descargar_youtube_con_pytubefix(')
PFX = py[_ip:py.find('\n\n\n@bp.route', _ip)] if _ip > -1 else ''
check('resolver: pytube atomico', "nombre_id + '.part' + ext" in PFX
      and 'os.replace(out_path, final)' in PFX)
check('resolver: in-flight', '_DESCARGAS_EN_CURSO' in RZ
      and 'for _turno in range(2)' in RZ
      and 'evento_descarga.wait(timeout=100)' in RZ)
check('resolver: pendiente honesto', 'pendiente=True' in RZ
      and 'Descarga en curso' in RZ)
check('resolver: libera turno', RZ.count('_liberar_descarga(clave_descarga, evento_descarga)') >= 4)

print(f'\n{len(fails)} fallos' if fails else '\nOK: 12/12')
sys.exit(1 if fails else 0)
