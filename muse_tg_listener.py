# -*- coding: utf-8 -*-
"""muse_tg_listener: Telegram -> bridge_chat.md (solo recepcion).

Long-poll a getUpdates; agrega los mensajes de Rafael a la sala de juntas.
- No escribe en BD (no despierta a Claude/Antigravity ni al daemon Merlin).
- No reenvia nada a Telegram (cero spam; los envios los hace Muse a mano).
- Token+chat_id se leen de BD (CONFIGURACION_SISTEMA) via tunel 5435.
Uso:  C:\\Tools\\Python313\\pythonw.exe muse_tg_listener.py
Vive detached; log en %TEMP%\\muse_tg_listener.log. Parar: taskkill /PID <pid>.
"""
import os
import sys
import tempfile
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime

V2 = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(V2, 'bridge_chat.md')
LOG = os.path.join(tempfile.gettempdir(), 'muse_tg_listener.log')
OFFSET_FILE = os.path.join(tempfile.gettempdir(), 'muse_tg_offset.txt')
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'muse_tg_listener.lock')
DB = 'postgresql://postgres:halo23032001@localhost:5435/tuctuc'
POLL_TIMEOUT = 25
RETRY_SEC = 30


def log(msg):
    line = '%s %s' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def load_offset(path):
    try:
        return int(open(path, encoding='utf-8').read().strip())
    except (OSError, ValueError):
        return 0


def save_offset(path, off):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(str(off))


def format_entry(ts, text):
    return '\n---\n\n### [%s] \U0001F464 Rafael (v\xeda Telegram):\n\n%s\n' % (ts, text)


def extract_update(u):
    """Devuelve (kind, msg): kind en message/edited_message/None."""
    for kind in ('message', 'edited_message'):
        m = u.get(kind)
        if m:
            return kind, m
    return None, {}


def should_deliver(cfg_id, msg):
    """Pasa si el remitente o el chat es Rafael (cubre privado, grupos, topicos)."""
    f = str((msg.get('from') or {}).get('id'))
    ch = str((msg.get('chat') or {}).get('id'))
    return f == str(cfg_id) or ch == str(cfg_id)


def pick_voice_file(msg):
    """file_id de nota de voz/audio, o None (documents se ignoran)."""
    for kind in ('voice', 'audio'):
        m = msg.get(kind)
        if m and m.get('file_id'):
            return m['file_id']
    return None


def fetch_voice_text(base, file_id):
    """Descarga nota de voz de Telegram y la transcribe -> (texto, duracion_s).
    Reintenta 3 veces (parpadeos de red). file_id queda en log para rescate manual."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import muse_stt
    log('stt intento file_id=%s' % file_id)
    info = tg_call(base, '/getFile', {'file_id': file_id}, timeout=20)
    fpath = (info.get('result') or {}).get('file_path')
    if not fpath:
        return None, 0
    tok = base.split('/bot', 1)[1]
    local = os.path.join(tempfile.gettempdir(), 'muse_tg_voice.ogg')
    last = None
    for intento, espera in ((1, 5), (2, 10), (3, 20)):
        try:
            urllib.request.urlretrieve('https://api.telegram.org/file/bot' + tok + '/' + fpath, local)
            last = None
            break
        except Exception as e:
            last = e
            log('stt descarga intento %d fallo %s; espero %ds' % (intento, type(e).__name__, espera))
            time.sleep(espera)
    if last is not None:
        raise last
    dur = 0
    try:
        import av
        cc = av.open(local)
        if len(cc.streams.audio):
            s = cc.streams.audio[0]
            dur = int(float(s.duration * s.time_base)) if s.duration else 0
        cc.close()
    except Exception:
        pass
    text = muse_stt.transcribe(local)
    try:
        os.unlink(local)
    except OSError:
        pass
    return text, dur


_lockfh = None


def single_flight(path=LOCK_FILE):
    """Una sola instancia: byte-lock msvcrt (el SO lo libera al morir).
    A prueba de reinicio: sin pid-stale, sin steals manuales."""
    global _lockfh
    import msvcrt
    _lockfh = open(path, 'a+b')
    try:
        _lockfh.seek(0)
        msvcrt.locking(_lockfh.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        _lockfh.close()
        _lockfh = None
        return False
    _lockfh.seek(0)
    _lockfh.truncate()
    _lockfh.write(str(os.getpid()).encode())
    _lockfh.flush()
    return True


def read_token():
    """Lee (token, chat_id) de BD. None si el tunel/BD no responde."""
    try:
        import psycopg2
        c = psycopg2.connect(DB, connect_timeout=10)
        cur = c.cursor()
        cur.execute('SELECT telegram_token, telegram_chat_id FROM "CONFIGURACION_SISTEMA" WHERE id = 1')
        row = cur.fetchone()
        c.close()
        if row and row[0] and row[1]:
            return row[0], str(row[1])
    except Exception as e:
        log('BD no disponible: %s' % type(e).__name__)
    return None


def tg_call(base, method, params=None, timeout=30):
    data = None
    url = base + method
    if params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def append_bridge(text):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(BRIDGE, 'a', encoding='utf-8', newline='') as f:
        f.write(format_entry(ts, text))


def run():
    if not single_flight():
        return 0
    log('inicio pid=%d' % os.getpid())
    creds = None
    while creds is None:
        creds = read_token()
        if creds is None:
            time.sleep(RETRY_SEC)
    token, chat_id = creds
    base = 'https://api.telegram.org/bot' + token
    try:
        me = tg_call(base, '/getMe')
        log('bot=%s' % me.get('result', {}).get('username'))
    except Exception as e:
        log('getMe fallo: %s; sigo con poll' % type(e).__name__)
    offset = load_offset(OFFSET_FILE)
    log('poll desde offset=%d (cola pendiente se entrega, nada se salta)' % offset)
    import muse_wake as _wake_boot
    _wake_boot.ensure_started(log, lambda: (base, chat_id))
    errs = 0
    while True:
        try:
            ups = tg_call(base, '/getUpdates', {'offset': offset, 'timeout': POLL_TIMEOUT},
                          timeout=POLL_TIMEOUT + 10).get('result', [])
            errs = 0
            for u in ups:
                offset = u['update_id'] + 1
                save_offset(OFFSET_FILE, offset)
                kind, m = extract_update(u)
                if kind is None:
                    log('ignorado update=%d (sin mensaje)' % u['update_id'])
                    continue
                f = str((m.get('from') or {}).get('id'))
                ch = str((m.get('chat') or {}).get('id'))
                if not should_deliver(chat_id, m):
                    log('filtrado update=%d kind=%s chat=%s from=%s' % (u['update_id'], kind, ch, f))
                    continue
                text = m.get('text')
                if not text:
                    vid = pick_voice_file(m)
                    if vid:
                        try:
                            heard, dur = fetch_voice_text(base, vid)
                            text = '[audio %ds] %s' % (dur, heard) if heard else '[audio sin transcripcion]'
                            log('stt ok (%ds)' % dur)
                        except Exception as e:
                            text = '[audio fallo, reenviar por favor]'
                            log('stt error %s file_id=%s' % (type(e).__name__, vid))
                    else:
                        text = '[mensaje sin texto]'
                if kind == 'edited_message':
                    text = '[editado] ' + text
                append_bridge(text)
                log('puente <= telegram (%d chars) update=%d kind=%s' % (len(text), u['update_id'], kind))
                try:
                    import muse_wake as wake
                    wake.ensure_started(log, lambda: (base, chat_id))
                    wake.notify(text, chat_id, m.get('message_id'))
                except Exception as e:
                    log('wake fallo %s' % type(e).__name__)
        except KeyboardInterrupt:
            break
        except Exception as e:
            errs += 1
            wait = min(60, 5 * errs)
            log('poll error %s; reintento en %ds' % (type(e).__name__, wait))
            time.sleep(wait)
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass
    log('fin')
    return 0


if __name__ == '__main__':
    sys.exit(run())
