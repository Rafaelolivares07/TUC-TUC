"""Regression: INICIAR_MUSE.bat mudo -> FIRSTMSG bootstrap -> menu en chat.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  python tests/test_iniciar_muse.py [ruta_bat]
Sin args prueba el launcher del repo.
2026-11-18: el arranque ya NO pide tema previo ni habla (murieron los
2 saludos falsos: Helena en autoarranque + Salome pre-tema). Muse carga
todo el contexto base y pide el tema en el chat al estar 100% listo.
Falla autentico: este test contra INICIAR_MUSE.bat pre-2026-11-18
(con menu previo ELEGIR_TEMA) falla en los pines de arranque mudo.
"""
import re
import sys
from pathlib import Path

BAT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'INICIAR_MUSE.bat'
raw = BAT.read_bytes()
text = raw.decode('utf-8')

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


# 1) pasos [1/8]-[8/8] presentes y en orden
marks = [f'[{i}/8]' for i in range(1, 9)]
pos = [text.find(m) for m in marks]
check('pasos [1/8]-[8/8] presentes y en orden', all(p >= 0 for p in pos) and pos == sorted(pos))

# 2) [5/8] MUDO: muestra tema anterior, sin menu previo ni voz (2026-11-18)
check('tema: no invoca selector', 'ELEGIR_TEMA' not in text and 'SELECTOR' not in text)
check('tema: muestra anterior como referencia', 'Anterior: !TEMA_ANT!' in text and 'tema_activo.txt' in text)
check('tema: avisa menu en chat al estar listo', 'en el chat al estar listo' in text)
check('tema: sin menu previo (una sola guarda IsInputRedirected, la del PAT)',
      text.count('IsInputRedirected') == 1)

# 3) [6/8] deriva ETIQUETA via muse_cuota --etiqueta, fallback tuctuc (82918cf mato WriteAllText)
drv = [ln for ln in text.splitlines() if 'muse_cuota.py" --etiqueta' in ln]
check('etiqueta: linea --etiqueta unica', len(drv) == 1)
if drv:
    d = drv[0]
    check('etiqueta: guarda en ETIQUETA',
          'set "ETIQUETA=%%e"' in d)
    check('etiqueta: fallback tuctuc', 'if not defined ETIQUETA set "ETIQUETA=tuctuc"' in text)

# 4) [8/8] abre wt con titulo fijo anti-override; fallos quedan visibles
check('launch: wt --title ETIQUETA --suppressApplicationTitle',
      'wt --title "!ETIQUETA!" --suppressApplicationTitle' in text)
check('launch: pestana solo corre muse', re.search(r'cmd /k !MUSECMD!', text) is not None)
check('launch: sale 0 tras wt ok', 'exit /b 0' in text)
check('launch: fallos visibles con etiqueta', ':wt_fallo' in text and ':sin_wt' in text and 'title !ETIQUETA!' in text)
check('launch: prompt inicial auto-arranque',
      'set "FIRSTMSG=' in text and '!MUSECMD! --yolo "!FIRSTMSG!"' in text)
fm = [ln for ln in text.splitlines() if ln.startswith('set "FIRSTMSG=')]
check('launch: FIRSTMSG bootstrap unico', len(fm) == 1)
if fm:
    check('launch: FIRSTMSG carga base en silencio y menu en chat',
          'silencio' in fm[0] and 'menu de tema' in fm[0])
    check('launch: FIRSTMSG espera numero o trabaja con anterior',
          'espera el numero' in fm[0] and 'tema anterior' in fm[0])

# 5) EOL CRLF puro (cmd lo exige)
check('EOL CRLF puro', raw.replace(b'\r\n', b'').count(b'\n') == 0 and raw.replace(b'\r\n', b'').count(b'\r') == 0)

# 6) regla cmd: cero parentesis en texto de echo dentro de bloques (...).
# Un ')' literal ahi aborta el parseo ("No se esperaba") y cierra la ventana.
def paren_fails():
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        if re.match(r'\s*rem\b', ln, re.I):
            continue
        for m in re.finditer(r'\(echo\b', ln, re.I):
            depth, q, k = 0, False, m.start()
            while k < len(ln):
                c = ln[k]
                if c == '"':
                    q = not q
                elif not q and c == '(':
                    depth += 1
                elif not q and c == ')':
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            inner = re.sub(r'"[^"]*"', '', ln[m.start() + 1:k])
            if '(' in inner or ')' in inner:
                out.append((i, ln.strip()))
                break
    return out


pf = paren_fails()
check('bloques: echos sin parentesis', not pf, '; '.join(f'L{i}' for i, _ in pf))

# 7) cuota Muse en [8/8] concatenada al titulo (no en [7/8])
p78 = text.find('[7/8]')
p88 = text.find('[8/8]')
pcuota = text.find('muse_cuota.py')
check('cuota: invocada en [6/8] (etiqueta) y [8/8] (tag)', text.count('muse_cuota.py') == 2 and text.find('[6/8]') < pcuota < p78 and text.find('muse_cuota.py', p78) > p88)
check('cuota: tag leido y antepuesto a ETIQUETA',
      'muse_cuota_tag.txt' in text and 'set "ETIQUETA=!CUOTATAG! !ETIQUETA!"' in text)
_cuota = (BAT.parent / 'muse_cuota.py').read_text(encoding='utf-8')
check('cuota: tag = % libre semanal local (API miente)',
      '_tag_libre(cs, techo)' in _cuota and "'%d%%'" in _cuota)
check('cuota: uso local desde session.jsonl', '_uso_local' in _cuota and 'session.jsonl' in _cuota)
check('cuota: tag limpio antes de leer', 'set "CUOTATAG="' in text)
check('cuota: titulo final visible', 'echo   Titulo: !ETIQUETA!' in text)
check('wake: titulo guardado para wake', 'muse_tab_title.txt' in text)

# 8) voz lista en [7/8] (chequeo + scripts en repo)
pvoz = text.find('import edge_tts')
check('voz: chequea edge-tts en [7/8]', p78 >= 0 and p78 < pvoz < p88)
check('voz: scripts en repo',
      (BAT.parent / 'muse_voz' / 'habla_edge.py').exists() and (BAT.parent / 'muse_voz' / 'reproducir.ps1').exists())

# 9) selector: herramienta manual sin voz (2026-11-18, arranque ya no lo invoca)
_ps1 = BAT.parent.parent / 'docs' / '_conversacion' / 'ELEGIR_TEMA.ps1'
if _ps1.exists():
    _b = _ps1.read_bytes().lstrip(b'\xef\xbb\xbf')
    check('selector: ASCII puro', all(c < 128 for c in _b))
else:
    check('selector: ASCII puro', False)
if _ps1.exists():
    _t = _ps1.read_text(encoding='utf-8-sig')
    check('selector: cero voz (sin habla_edge/reproducir/frases)',
          'habla_edge' not in _t and 'reproducir' not in _t and '$frases' not in _t and 'Get-Random' not in _t)
    check('tema: prompt espera sin tope hasta elegir', 'AddSeconds(120)' not in _t and 'while ($true)' in _t and 'Enter = salir sin cambios' in _t)
    check('tema: sin consola no bloquea', 'IsInputRedirected' in _t)
    check('tema: -Choice directo + guarda puntero', 'param([int]$Choice' in _t and 'Set-Content $pointer' in _t)
check('log: marcadores [N/8] a muse_arranque.log', text.count('>>"%LOG%"') >= 8 and 'WT_EXIT=' in text and 'FIN_OK' in text)

# 10) autoarranque MUDO: cero SAPI, cero daemon vivo (2026-11-18)
_merlin = BAT.parent.parent.parent / 'iniciar_merlin.ps1'
if _merlin.exists():
    _m = _merlin.read_text(encoding='utf-8-sig')
    check('autoarranque: sin sintesis SAPI',
          'System.Speech' not in _m and 'Speak(' not in _m and 'SelectVoice' not in _m
          and 'SpeechSynthesizer' not in _m)
    _vivas = [ln for ln in _m.splitlines()
              if 'DAEMON' in ln and 'Start-Process' in ln and not ln.lstrip().startswith('#')]
    check('autoarranque: daemon sin linea viva', not _vivas, '; '.join(_vivas))
    check('autoarranque: abre INICIAR MUSE.lnk', 'INICIAR MUSE.lnk' in _m)
else:
    check('autoarranque: sin sintesis SAPI', False)
    check('autoarranque: daemon sin linea viva', False)
    check('autoarranque: abre INICIAR MUSE.lnk', False)

# 11) vigilante menu-voz: habla SOLO tras menu pintado (2026-11-18, orden Rafa)
# Falla autentico: sin vigilante la voz salia antes del menu visible (turno
# del 18-nov manana: "te deje el menu en pantalla" sin menu en pantalla).
# Contrato: FIRSTMSG prohibe voz en arranque + ordena crear muse_menu_listo.mark
# al pintar el menu; muse_menu_voz.py habla al verlo (falla-cierra: sin mark,
# sin marca de boot, con respuesta de Rafa o con otro vigilante vivo = silencio).
check('vigilante: FIRSTMSG prohibe voz en arranque',
      fm and 'NO uses la voz' in fm[0])
check('vigilante: FIRSTMSG ordena mark al pintar menu',
      fm and 'muse_menu_listo.mark' in fm[0])
check('vigilante: bat toca marca de boot', 'muse_boot.mark' in text)
check('vigilante: bat lanza watcher oculto',
      'muse_menu_voz.py' in text and 'pythonw' in text)
_wv = BAT.parent / 'muse_menu_voz.py'
check('vigilante: script existe', _wv.exists())
if _wv.exists():
    _w = _wv.read_text(encoding='utf-8')
    check('vigilante: habla via hablar.ps1', 'hablar.ps1' in _w)
    check('vigilante: lock instancia unica', 'muse_menu_voz.lock' in _w)
    check('vigilante: timeout y falla-cierra (3+ salidas 0)',
          'TIMEOUT_MIN' in _w and _w.count('return 0') >= 3)
    check('vigilante: respeta respuesta de Rafa', 'user_intent' in _w)
    import subprocess as _sp
    _r = _sp.run([sys.executable, str(_wv), '--probar'],
                 capture_output=True, text=True, timeout=60)
    check('vigilante: self-test verde', _r.returncode == 0 and 'PROBAR: OK' in _r.stdout,
          (_r.stdout + _r.stderr)[-200:])

# 12) titulo unico por arranque: MUSE + etiqueta + fecha + hora, mayusculas (2026-11-20, orden Rafa)
# Falla autentico: doble arranque 16:08/16:09 con titulo "90% coordinacion" en ambas (misma cuota + tema previo).
check('titulo: antepone MUSE y agrega fecha+hora', 'set "ETIQUETA=MUSE !ETIQUETA! %date:~0,5% !HHMM!"' in text)
check('titulo: hora HH:MM con cero (sin espacio)', 'set "HHMM=%time:~0,5%"' in text and 'set "HHMM=!HHMM: =0!"' in text)
check('titulo: mayusculas via python + patron set/p', ".upper()" in text and 'set /p ETIQUETA=<"%TEMP%\\muse_tab_title.txt"' in text)
check('titulo: compone antes de mostrar Titulo', 0 <= text.find('!HHMM!') < text.find('echo   Titulo: !ETIQUETA!'))

print('RESULTADO:', 'PASS' if not fails else f'FAIL ({len(fails)})')
sys.exit(1 if fails else 0)
