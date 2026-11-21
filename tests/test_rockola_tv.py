"""Regression: vista TV display-only (opcion A) sobre el mismo reproductor.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  python tests/test_rockola_tv.py
Cubre (2026-10-31): ruta /<sala>/tv (valida sala, tv_mode=True, no-cache) +
bloque condicional en rockola_reproductor.html (display gigante, start llama
a activar() existente, poll /cola propio, QR, progreso; motor sin tocar).
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
R = (ROOT / 'templates/rockola_reproductor.html').read_text(encoding='utf-8')

_ini = py.find('def tv_sala(')
TV = py[_ini:py.find('\n@bp.route(', _ini)] if _ini > -1 else ''

check('tv: ruta sala', "'/<sala_id>/tv'" in py and 'def tv_sala(' in py
      and "'/<sala_id>/reproductor/tv'" in py and "'/reproductor/<sala_id>/tv'" in py)
check('tv: valida sala', '_get_sala(conn, sala_id)' in TV)
check('tv: modo param', 'tv_mode=True' in TV)
check('tv: no cache', 'no-cache, no-store, must-revalidate' in TV)
check('tv: display', 'id="tv-display"' in R and 'tv_mode' in R)
check('tv: start', 'id="tv-start"' in R and 'tv-btn-empezar' in R)

_ini2 = R.find('async function tvEmpezar(')
TVJ = R[_ini2:R.find('</script>', _ini2)] if _ini2 > -1 else ''

check('tv: reclama control', 'await reclamarReproductor()' in TVJ)
check('tv: poll cola', '/cola' in TVJ and 'tvCargarCola' in TVJ)
check('tv: qr sala', 'QRCode' in TVJ and 'tv-qr' in TVJ)
check('tv: progreso', 'player1' in TVJ and 'tv-prog-fill' in TVJ)
check('tv: css modo', 'body.tv-mode' in R and '#tv-display { display: none; }' in R)

_inir = py.find('def reproductor_sala(')
REPRO = py[_inir:py.find('\n@bp.route(', _inir)] if _inir > -1 else ''
check('tv: query activa modo', "request.args.get('tv')" in REPRO
      and 'tv_mode=tv_mode' in REPRO)
_iau = R.find('function debeAutoreproducirAlEntrar()')
AUT = R[_iau:R.find('\n}', _iau)] if _iau > -1 else ''
check('tv: autoplay forzado', 'tv-mode' in AUT and 'return true' in AUT)

# 2026-11-01: TV real mudo con display vivo -> falla silenciosa visible + blindaje storage
_igid = R.find('function getDeviceId()')
GID = R[_igid:R.find('\n}\n', _igid)] if _igid > -1 else ''
check('tv: deviceid blindado', '_memDeviceId' in GID and 'try' in GID
      and 'localStorage' in GID)
_ign = R.find('function getDeviceName()')
GNAME = R[_ign:R.find('\n}\n', _ign)] if _ign > -1 else ''
check('tv: devicename blindado', '_memDeviceName' in GNAME and 'TV' in R[_ign - 800:_ign])
_irec = R.find('async function reclamarReproductor()')
REC = R[_irec:R.find('\n}\n', _irec)] if _irec > -1 else ''
check('tv: reclamar retorna', 'return true' in REC and REC.rstrip().endswith('return false;'))
check('tv: diag linea', 'id="tv-diag"' in R and 'function tvDiag(' in R
      and 'tvDiag(' in TVJ)
check('tv: vinculo visible', 'vinculo FALLO' in R and '_tvVincularError' in R
      and 'vinculo OK' in TVJ)
check('tv: motor ausente', 'MOTOR NO CARGO' in TVJ)
check('tv: estado audio', 'motor: SONANDO' in TVJ and 'esYouTubeActual' in TVJ)

# 2026-10-31 noche: diag colapsable + layout fijo (Rafa en vivo)
check('tv: diag colapsada', 'id="tv-diag" class="collapsed"' in R
      and '#tv-diag.collapsed' in R and "classList.toggle('collapsed')" in TVJ)
check('tv: diag autoexpande fallo', "indexOf('FALLO')" in R
      and "indexOf('MOTOR NO CARGO')" in R)
check('tv: sonando chica', '#tv-sonando { font-size: clamp(26px, 3.4vw, 58px)' in R
      and 'max-height: 2.5em' in R)
check('tv: columnas fijas', '.tv-main > * { min-width: 0; }' in R
      and 'min-height: 0; min-width: 0; }' in R)
check('tv: ellipsis nombres', '#tv-cola li > span:last-child' in R
      and 'text-overflow: ellipsis; }' in R)

# 2026-10-31 noche: diag fuera de la vista (Rafa), huella en codigo
check('tv: diag oculta', '#tv-diag { display: none;' in R
      and 'diag TV oculto' in R and 'function tvDiag(' in R
      and 'id="tv-diag"' in R)
check('tv: qr texto', 'Programa tu cancion desde tu celular' in R
      and 'Pide tu cancion' not in R)

# 2026-11-01: sala junto a marca; QR al fondo; cola sin corte (orden Rafa)
_itv = R.find('id="tv-display"')
_TV = R[_itv:] if _itv > -1 else ''
check('tv: qr al fondo', _TV.find('tv-qr-card') > _TV.find('id="tv-sonando"')
      and _TV.find('tv-qr-card') > _TV.find('id="tv-next-nombre"'))
check('tv: sala junto a marca',
      '.tv-head { display: flex; align-items: baseline; gap: 2vw; margin-bottom: 2vh; }' in R
      and _TV.find('tv-brand') < _TV.find('tv-sala'))
check('tv: cola no mocha', "'y ' + (resto.length" in R
      and '#tv-cola { list-style: none; margin-top: 1vh; flex: 1 1 auto; min-height: 0; overflow: hidden; }' in R
      and 'probe.offsetHeight' in R)
check('tv: slot imagen', 'tv-img-slot' in R and 'aspect-ratio: 16/9' in R
      and 'id="tv-img"' in R)
check('tv: rota imagen', 'const TV_IMGS' in R and 'function tvRotarImagen(' in R
      and 'tvRotarImagen(son ? son.id' in R)
check('tv: imgs existen', all(
      (ROOT / f'templates/../static/tv/rockola_{l}.jpg').exists()
      for l in 'abc') and R.count('/static/tv/rockola_') == 3)

# 2026-11-01: TV no se queda mudo (reanuda + salta atascos solo)
_iv = R.find('function vigilarAtascoAudio(')
_VIG = R[_iv:R.find('\n}\n', _iv)] if _iv > -1 else ''
check('tv: tap quita pausa', 'postModos({modo_pausa: false})' in TVJ)
check('tv: tap limpia stuck', '!fadeIntervalTimer) transitioning = false' in TVJ)
check('tv: vigila atasco', 'setInterval(vigilarAtascoAudio, 5000)' in R
      and 'reintentarOSaltar()' in _VIG and 'atascoRachas' in _VIG)
check('tv: error salta', "addEventListener('error', handlePlayerError)" in R
      and 'function handlePlayerError(' in R)
check('tv: ended reavanza', 'player.ended && !transitioning' in R)

# 2026-11-21: TV autonomo (Rafa: detras de EMPEZAR no debe sonar; el tap arranca)
check('tv: espera tap helper', 'function tvEsperandoTap(' in R
      and "getElementById('tv-start')" in R and "contains('visible')" in R)
check('tv: no suena tras boton', 'if (tvEsperandoTap()) { await prepararCancionEnPausa(c); return; }' in R)
check('tv: offline respeta tap', 'if (tvEsperandoTap()) { prepararCancionEnPausa(c); return; }' in R)
check('tv: reclamar no pausa', "contains('tv-mode')) player.play()" in REC)
check('tv: activar no pausa', "if (!document.body.classList.contains('tv-mode')) player.pause();" in R)
check('tv: flanco respeta tap', 'currentCola.length && !tvEsperandoTap()) togglePlayPause' in R)
check('tv: tap arranca motor', 'eTvGo' in TVJ and 'cancionActual = null' in TVJ
      and 'await verificarCola()' in TVJ and '!saltandoCancion' in TVJ)
check('tv: audible exige tiempo', 'p.currentTime > 0' in TVJ)

# 2026-11-21: barra pinta progreso YT directo (no negro)
check('tv: barra lee YT', 'getYtPlayerActivo()' in R and 'getCurrentTime' in R
      and 'getDuration' in R and "getElementById('tv-prog-fill')" in R)
check('tv: barra YT tocando', 'getPlayerState() === 1' in R)

# 2026-11-21: espera honesta mientras descarga + precarga temprana (no saltar lo no-listo)
_ivig = R.find('function vigilarSilencioSala()')
_VIGS = R[_ivig:R.find('\n}\n', _ivig)] if _ivig > -1 else ''
check('tv: watchdog respeta descarga', 'resolviendoActual' in _VIGS
      and 'Descarga atorada 4.5min' in _VIGS)
check('tv: resolve paciente', 'async function resolverAudioPaciente(' in R
      and 'Descargando audio...' in R and 'setTimeout(r, 15000)' in R)
check('tv: paciente aborta si suena', "typeof reproduciendo !== 'undefined' && reproduciendo) return null" in R)
check('tv: path iframe-muerto paciente', 'resolverAudioPaciente(c.id, 240000)' in R)
check('tv: fallback no pisa YT', 'if (audioUrl && cancionActual === c.id && !reproduciendo)' in R)
check('tv: precarga fondo', 'function precargarSiguientesEnFondo(' in R
      and 'precargarSiguientesEnFondo(); } catch (ePre) {}' in R
      and 'precargaFondoTs' in R)

print(f'\n{len(fails)} fallos' if fails else '\nOK: 54/54')
sys.exit(1 if fails else 0)
