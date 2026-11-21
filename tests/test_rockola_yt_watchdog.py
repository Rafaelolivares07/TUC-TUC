"""Regression: watchdog YT salta si no hay audio (2026-10-31 noche).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  python tests/test_rockola_yt_watchdog.py
Cubre: watchdog existe + fallback nativo + si falla/sin-url SALTA
(no mudo eterno) + skip con guardas (sigue pausado, misma cancion,
sin transicion) + ruta error tambien salta.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


R = (ROOT / 'templates/rockola_reproductor.html').read_text(encoding='utf-8')

_iw = R.find('[Watchdog YouTube] No arrancó en 5s')
WD = R[_iw:R.find('}, 3500);', _iw)] if _iw > -1 else ''
check('yt: watchdog existe', _iw > -1 and 'resolverAudioEnServidor(c.id)' in WD)
check('yt: fallback nativo', 'esYouTubeActual = false' in WD
      and 'player.play()' in WD)
check('yt: salta sin audio', 'okNativo' in WD and 'reintentarOSaltar(c)' in WD
      and 'Sin audio' in WD)
check('yt: skip con guardas',
      'if (!reproduciendo && cancionActual === c.id && !transitioning) reintentarOSaltar(c)' in WD)
check('yt: ruta error salta', 'Video no reproducible en YouTube' in R)

# 2026-11-21: cada intento arranca de cero (atorada en true varaba YT->YT en TV)
_iir = R.find('async function intentarReproducir(c) {')
_IR = R[_iir:R.find('cancionActualObjeto = c;', _iir)] if _iir > -1 else ''
check('yt: intento resetea bandera', 'playPendiente = true;' in _IR
      and 'reproduciendo = false;' in _IR)

# 2026-11-21: vigilante anti-silencio (30s sin audio con cola = salta solo)
_ivs = R.find('function vigilarSilencioSala()')
_VS = R[_ivs:R.find('\n}\n', _ivs)] if _ivs > -1 else ''
check('yt: vigila silencio', _ivs > -1
      and 'setInterval(vigilarSilencioSala, 5000)' in R)
check('yt: libera transicion', 'Transicion atorada 30s' in _VS
      and 'transitioning = false' in _VS)
check('yt: salta en silencio', 'Silencio 30s con cola' in _VS
      and 'silencioRachas >= 6' in _VS)

# 2026-11-21 v2: audible por AVANCE (congelado no vale) + pendiente acotado + pageshow
check('yt: audible avanza', 'ultimoAvanceTs' in _VS
      and 'tMax > 0' in _VS)
check('yt: arranque acotado', 'Arranque atorado 45s' in _VS
      and 'pendDesde' in _VS)
check('yt: pageshow recarga', "addEventListener('pageshow'" in R
      and 'ev.persisted' in R and 'location.reload()' in R)

# 2026-11-21: fallos no consumen la ultima (reintento acotado, no perdida)
_ir2 = R.find('async function reintentarOSaltar(')
_RT = R[_ir2:R.find('\n}\n', _ir2)] if _ir2 > -1 else ''
check('yt: reintenta sola', _ir2 > -1 and 'reintentosSola' in _RT
      and 'reintentosSola >= 5' in _RT)
check('yt: no consume sola', 'currentCola.length > 1' in _RT
      and 'cancionActual = null' in _RT)
check('yt: fallos reintentan', 'reintentarOSaltar(c)' in R
      and 'reintentarOSaltar()' in R)

print(f'\n{len(fails)} fallos' if fails else '\nOK: 15/15')
sys.exit(1 if fails else 0)
