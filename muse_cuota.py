# -*- coding: utf-8 -*-
"""Cuota Muse Code: cuadro de consumo para launcher y escritorio.

Imprime cuadro completo y deja tag corto (% libre semanal, '80%') en
%TEMP%/muse_cuota_tag.txt para concatenar al titulo WT. Best-effort exit 0.
`--voz` ademas habla el resumen. `--etiqueta` imprime el tema corto.

2026-11-04: la API (subs_usage.used_percent) no sirve (0% con 65+ llamadas
reales) -> se mide consumo LOCAL REAL de los session.jsonl. Regla Rafa:
el maximo semanal visto vale 95% aprox (auto-sube si se supera el record).
"""
import csv
import glob
import json
import math
import os
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BOG = ZoneInfo('America/Bogota')
DIAS = ['lun', 'mar', 'mie', 'jue', 'vie', 'sab', 'dom']
DIAS_LARGO = {'lun': 'lunes', 'mar': 'martes', 'mie': 'miercoles', 'jue': 'jueves',
              'vie': 'viernes', 'sab': 'sabado', 'dom': 'domingo'}
TAG = os.path.join(tempfile.gettempdir(), 'muse_cuota_tag.txt')
HOME = os.path.expanduser('~')
SESSIONS = os.path.join(HOME, '.local', 'share', 'muse', 'sessions')
HIST = os.path.join(HOME, '.local', 'share', 'muse', 'cuota_hist.csv')
SESCACHE = os.path.join(HOME, '.local', 'share', 'muse', 'cuota_ses.csv')
TEMA = os.path.join(HOME, 'Documents', 'docs', '_conversacion', 'tema_activo.txt')
TOKS = ('input_tokens', 'output_tokens', 'cached_tokens', 'reasoning_tokens',
        'cache_read_tokens', 'cache_write_tokens')
ANCHO = 64


def _pct(v):
    """Porcentaje redondeado hacia arriba (02/11: <1% ya no sale 0%)."""
    return int(math.ceil(float(v or 0)))


def _compact(n):
    """14300000 -> '14.3M'; 509156339 -> '509M'; 320500 -> '320K'."""
    n = float(n or 0)
    for div, suf in ((1e9, 'G'), (1e6, 'M'), (1e3, 'K')):
        if n >= div:
            v = n / div
            if v >= 100:
                return '%d%s' % (int(round(v)), suf)
            return ('%.1f' % v).rstrip('0').rstrip('.') + suf
    return str(int(n))


def _techo(maxv):
    """Tope 100% implicito: el maximo visto vale 95%."""
    return int(round(maxv / 0.95)) if maxv > 0 else 0


def _paprox(cs, ref):
    """% aproximado semanal: el maximo visto vale 95%. None sin referencia."""
    if ref <= 0:
        return None
    return min(95, int(cs / ref * 95))


def _falta(seg):
    seg = max(0, int(seg))
    d, seg = divmod(seg, 86400)
    h, seg = divmod(seg, 3600)
    m = seg // 60
    if d > 0:
        return '%d dias %d h' % (d, h)
    if h > 0:
        return '%d h %02d min' % (h, m)
    return '%d min' % m


def _tema_corto(linea):
    """'10_marketing_pautas_tracking_ventas.md' -> 'marketing'; '' -> 'tuctuc'."""
    t = (linea or '').strip().lstrip('\ufeff')
    t = re.sub(r'^\d+_', '', t)
    if t.lower().endswith('.md'):
        t = t[:-3]
    tok = re.split(r'[_-]', t, 1)[0].strip().lower()
    return tok or 'tuctuc'


def _tag_libre(cs, techo):
    """Tag titulo: '% libre semanal' ('80%') o 's/ref' sin referencia."""
    if techo <= 0:
        return 's/ref'
    return '%d%%' % max(0, 100 - int(cs / techo * 100))


def _toks(u):
    n = 0
    for k in TOKS:
        try:
            n += int(u.get(k) or 0)
        except (TypeError, ValueError):
            pass
    return n


def _ts(o):
    try:
        t = float(o.get('recorded_at') or 0)
    except (TypeError, ValueError):
        return 0
    while t > 1e12:
        t /= 1000.0
    return t


def _uso_local(desde_ventana, desde_semana):
    """(llamadas_vent, llamadas_sem, tok_vent, tok_sem) desde session.jsonl."""
    cw = cs = tw = ts = 0
    try:
        rutas = glob.glob(os.path.join(SESSIONS, '*', '*', '*', '*', 'session.jsonl'))
        rutas += glob.glob(os.path.join(SESSIONS, '*', '*', '*', '*', 'subagent', '*', 'session.jsonl'))
    except OSError:
        return 0, 0, 0, 0
    for p in rutas:
        try:
            if os.path.getmtime(p) < desde_semana:
                continue
        except OSError:
            continue
        try:
            f = open(p, encoding='utf-8')
        except OSError:
            continue
        with f:
            for ln in f:
                try:
                    o = json.loads(ln)
                except ValueError:
                    continue
                ev = (o.get('payload') or {}).get('event') or {}
                if ev.get('kind') != 'model_completed':
                    continue
                u = ev.get('usage') or {}
                if not isinstance(u, dict):
                    continue
                toks = _toks(u)
                if toks <= 0:
                    continue
                t = _ts(o)
                if t < desde_semana:
                    continue
                cs += 1
                ts += toks
                if t >= desde_ventana:
                    cw += 1
                    tw += toks
    return cw, cs, tw, ts


def _sesiones():
    """{sid: (mtime, llamadas, tok)} con cache incremental en disco."""
    cache = {}
    try:
        with open(SESCACHE, encoding='utf-8') as f:
            for r in csv.reader(f):
                if len(r) == 4 and r[0] != 'sid':
                    cache[r[0]] = (float(r[1]), int(r[2]), int(r[3]))
    except (OSError, ValueError):
        pass
    tot = {}
    try:
        dirs = glob.glob(os.path.join(SESSIONS, '*', '*', '*', '*'))
    except OSError:
        dirs = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        sid = os.path.relpath(d, SESSIONS).replace(os.sep, '/')
        logs = [p for p in glob.glob(os.path.join(d, 'session.jsonl')) +
                glob.glob(os.path.join(d, 'subagent', '*', 'session.jsonl'))
                if os.path.isfile(p)]
        if not logs:
            continue
        try:
            mt = max(os.path.getmtime(p) for p in logs)
        except OSError:
            continue
        if sid in cache and cache[sid][0] >= mt:
            tot[sid] = cache[sid]
            continue
        c = t = 0
        for p in logs:
            try:
                f = open(p, encoding='utf-8')
            except OSError:
                continue
            with f:
                for ln in f:
                    try:
                        o = json.loads(ln)
                    except ValueError:
                        continue
                    ev = (o.get('payload') or {}).get('event') or {}
                    if ev.get('kind') != 'model_completed':
                        continue
                    u = ev.get('usage') or {}
                    if not isinstance(u, dict):
                        continue
                    k = _toks(u)
                    if k > 0:
                        c += 1
                        t += k
        tot[sid] = (mt, c, t)
    try:
        with open(SESCACHE, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['sid', 'mtime', 'calls', 'tok'])
            for sid, (mt, c, t) in sorted(tot.items()):
                w.writerow([sid, mt, c, t])
    except OSError:
        pass
    return tot


def _max_sem_hist():
    """Maximo semanal visto en el historial (techo empirico sin freno)."""
    try:
        with open(HIST, encoding='utf-8') as f:
            return max([int(r[2]) for r in csv.reader(f) if len(r) > 2 and r[2].isdigit()] or [0])
    except (OSError, ValueError):
        return 0


def _anotar_hist(cw, cs, tw, ts, uw, us):
    try:
        nuevo = not os.path.exists(HIST)
        with open(HIST, 'a', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(['fecha_bog', 'win_calls', 'week_calls', 'win_tok', 'week_tok', 'api_w', 'api_s'])
            w.writerow([datetime.now(BOG).strftime('%Y-%m-%d %H:%M'), cw, cs, tw, ts, uw, us])
    except OSError:
        pass


def _borde():
    return '+' + '-' * (ANCHO - 2) + '+'


def _linea(txt=''):
    return '| ' + txt[:ANCHO - 4].ljust(ANCHO - 4) + ' |'


def _fila(celdas, anchos):
    return '|' + '|'.join(c[:a].ljust(a) for c, a in zip(celdas, anchos)) + '|'


def _sepfila(anchos):
    return '+' + '+'.join('-' * a for a in anchos) + '+'


def _hablar(cs, pap, corte, ses_c):
    try:
        import subprocess
        base = os.path.dirname(os.path.abspath(__file__))
        txt = 'Llevas %d llamadas esta semana' % cs
        if pap is not None:
            txt += ', como el %d por ciento aproximado de tu maximo' % pap
        dia = DIAS_LARGO.get(corte.split()[0], '')
        if dia:
            txt += '. La semana cierra el %s' % dia
        if ses_c:
            txt += '. Tu sesion de hoy lleva %d llamadas' % ses_c
        vt = os.path.join(tempfile.gettempdir(), 'muse_cuota_voz.txt')
        vm = os.path.join(tempfile.gettempdir(), 'muse_cuota_voz.mp3')
        open(vt, 'w', encoding='utf-8').write(txt)
        subprocess.run([r'C:\Tools\Python313\python.exe',
                        os.path.join(base, 'muse_voz', 'habla_edge.py'), vt, vm],
                       capture_output=True, timeout=60)
        subprocess.run(['powershell', '-NoProfile', '-File',
                        os.path.join(base, 'muse_voz', 'reproducir.ps1'), vm],
                       capture_output=True, timeout=60)
    except Exception:
        pass


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--etiqueta':
        try:
            with open(TEMA, encoding='utf-8-sig') as f:
                print(_tema_corto(f.readline()))
        except Exception:
            pass
        return 0
    try:
        os.unlink(TAG)
    except OSError:
        pass
    try:
        a = json.load(open(os.path.join(HOME, '.config', 'muse', 'auth.json')))
        tok = a['providers']['meta']['access_token']
    except Exception:
        print('  Cuota Muse: sin login [muse login]')
        return 0
    ahora = datetime.now(timezone.utc).timestamp()
    hoy = datetime.now(BOG)
    tier, uw, us = '?', 0, 0
    win_start, sem_start = ahora - 5 * 3600, ahora - 7 * 24 * 3600
    win_reset, sem_reset = ahora + 5 * 3600, ahora + 7 * 24 * 3600
    try:
        req = urllib.request.Request(
            'https://api.meta.ai/muse-code/key', data=json.dumps({}).encode(),
            headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'},
            method='POST')
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        u = d.get('subs_usage') or {}
        w = u.get('window') or {}
        s = u.get('weekly') or {}
        tier = d.get('subs_tier_name') or '?'
        uw = _pct(w.get('used_percent', 0))
        us = _pct(s.get('used_percent', 0))
        win_reset = w.get('resets_at', 0) or win_reset
        sem_reset = s.get('resets_at', 0) or sem_reset
        win_start = win_reset - (w.get('window_duration_mins', 300) or 300) * 60
        sem_start = sem_reset - 7 * 24 * 3600
    except Exception:
        pass
    try:
        cw, cs, tw, ts = _uso_local(win_start, sem_start)
        prev_max = _max_sem_hist()
        _anotar_hist(cw, cs, tw, ts, uw, us)
        maxv = max(prev_max, cs)
        techo = _techo(maxv)
        pap = _paprox(cs, maxv)
        if pap is None:
            sem_pct, sem_lib = 's/ref', 's/ref'
        else:
            sem_pct = '~%d%%' % pap
            sem_lib = '~%d%%' % (100 - int(cs / techo * 100))
        dias_van = max((ahora - sem_start) / 86400.0, 0.05)
        dias_quedan = max((sem_reset - ahora) / 86400.0, 0)
        prom_gasto = int(cs / dias_van)
        prom_puedes = int((techo - cs) / dias_quedan) if dias_quedan > 0.05 and techo > cs else 0
        rw = datetime.fromtimestamp(win_reset, timezone.utc).astimezone(BOG)
        rs = datetime.fromtimestamp(sem_reset, timezone.utc).astimezone(BOG)
        corte = '%s %s' % (DIAS[rs.weekday()], rs.strftime('%d/%m'))
        tot = _sesiones()
        if tot:
            sid_rec = max(tot, key=lambda k: tot[k][0])
            rec_c, rec_t = tot[sid_rec][1], tot[sid_rec][2]
            rec_fecha = '%s/%s %s' % (sid_rec[5:7], sid_rec[8:10], sid_rec[11:19])
            sid_max = max(tot, key=lambda k: tot[k][1])
            max_c, max_fecha = tot[sid_max][1], '%s/%s' % (sid_max[5:7], sid_max[8:10])
        else:
            rec_c = rec_t = max_c = 0
            rec_fecha = max_fecha = 's/datos'
        W = [10, 9, 9, 7, 7, 15]
        print(_borde())
        print(_linea('CUOTA MUSE %s %s  [%s]' % (DIAS[hoy.weekday()], hoy.strftime('%d/%m %H:%M'), tier)))
        print(_borde())
        print(_fila(['', 'LLAMADAS', 'TOKENS', 'USADO', 'LIBRE', 'CORTE/REF'], W))
        print(_sepfila(W))
        print(_fila(['SEMANA', str(cs), _compact(ts), sem_pct, sem_lib,
                      '%s %s' % (corte, rs.strftime('%H:%M'))], W))
        print(_fila(['VENTANA', str(cw), _compact(tw), '', '', 'hoy ' + rw.strftime('%H:%M')], W))
        print(_fila(['SESION', str(rec_c), _compact(rec_t), '', '', rec_fecha], W))
        print(_borde())
        print(_linea('faltan sem %s | vent %s' % (_falta(sem_reset - ahora), _falta(win_reset - ahora))))
        print(_linea('ritmo ~%d/dia gastado | puedes ~%d/dia sin pasar' % (prom_gasto, prom_puedes)))
        print(_linea('tu record sem %d | sesion %d (%s)' % (maxv, max_c, max_fecha)))
        print(_linea('% aproximados: tu record semanal vale 95%'))
        print(_borde())
        if prev_max > 0 and cs >= prev_max:
            print(_linea('Nuevo record semanal sin freno: el 95% se movio solo.'))
            print(_borde())
        elif prev_max > 0 and cs >= 0.8 * prev_max:
            print(_linea('AVISO: cerca de tu maximo semanal.'))
            print(_borde())
        print(_linea('API Meta dice %d%%/%d%% (no confiable, referencia)' % (uw, us)))
        print(_borde())
        with open(TAG, 'w') as f:
            f.write(_tag_libre(cs, techo))
        if len(sys.argv) > 1 and sys.argv[1] == '--voz':
            _hablar(cs, pap, corte, rec_c)
    except Exception as e:
        print('  Cuota Muse: no disponible [%s]' % type(e).__name__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
