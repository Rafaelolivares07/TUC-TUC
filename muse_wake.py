# -*- coding: utf-8 -*-
"""muse_wake: despierta la sesion Muse (trigger __MUSE__) y reenvia su outbox a Telegram.
Inbox/outbox + inyeccion ConPTY (sin foco ni clipboard) + cooldown.
- Inbox/outbox: muse_inbox.json / muse_outbox.json en V2 (separados de Claude).
- Titulo de pestana: %TEMP%\\muse_tab_title.txt (lo escribe INICIAR_MUSE.bat).
- Sin titulo coincidente visible: NO pega (aborta seguro); el mensaje igual
  queda en sala + inbox y Muse lo procesa en su siguiente turno.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

V2 = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(V2, 'muse_inbox.json')
OUTBOX = os.path.join(V2, 'muse_outbox.json')
TITLE_FILE = os.path.join(tempfile.gettempdir(), 'muse_tab_title.txt')
CLI_PID_FILE = os.path.join(tempfile.gettempdir(), 'muse_cli_pid.txt')
TRIGGER = '__MUSE__'
COOLDOWN_SEC = 30
VERIFY_SEC = 90
_started = False
_last_wake = 0.0
_wake_scheduled = False
_log = None


def _l(msg):
    if _log is not None:
        _log(msg)
    else:
        print(msg, flush=True)


def configure(logfn):
    global _log
    _log = logfn


def build_inbox(text, chat_id, message_id):
    return {'texto': text, 'chat_id': str(chat_id), 'message_id': message_id,
            'fecha': time.strftime('%Y-%m-%d %H:%M:%S')}


def write_inbox(payload, path=INBOX):
    try:
        cur = json.load(open(path, encoding='utf-8'))
        items = cur if isinstance(cur, list) else [cur]
    except (OSError, ValueError):
        items = []
    items.append(payload)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False)


def load_title(path=TITLE_FILE):
    try:
        return open(path, encoding='utf-8').read().strip() or None
    except OSError:
        return None


def _snapshot():
    """{pid: (ppid, exe_lower)} via Toolhelp32. {} si falla."""
    import ctypes
    from ctypes import wintypes

    class PE(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_wchar * 260)]

    procs = {}
    try:
        k = ctypes.windll.kernel32
        snap = k.CreateToolhelp32Snapshot(0x2, 0)
        pe = PE()
        pe.dwSize = ctypes.sizeof(PE)
        if k.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                procs[pe.th32ProcessID] = (pe.th32ParentProcessID, pe.szExeFile.lower())
                if not k.Process32NextW(snap, ctypes.byref(pe)):
                    break
        k.CloseHandle(snap)
    except Exception:
        pass
    return procs


def load_cli_pid(path=CLI_PID_FILE):
    """Pid del CLI Muse grabado por la sesion; None si ausente/corrupto/muerto/no-muse."""
    try:
        pid = int(open(path, encoding='utf-8').read().strip())
    except (OSError, ValueError):
        return None
    procs = _snapshot()
    if pid in procs and _is_muse(procs[pid][1]):
        return pid
    return None


def _muse_pid_for_tab(title):
    """Muse hijo de la ventana WT cuyo titulo calza (determinista con N sesiones)."""
    if not title:
        return None
    try:
        import win32gui
        import win32process
        wt_pids = []

        def _enum(h, acc):
            if not win32gui.IsWindowVisible(h):
                return
            t = (win32gui.GetWindowText(h) or '').lower()
            if title.lower() not in t:
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(h)
                acc.append(pid)
            except Exception:
                pass

        win32gui.EnumWindows(_enum, wt_pids)
        if not wt_pids:
            return None
        procs = _snapshot()
        hits = []
        for pid, (ppid, exe) in procs.items():
            if not _is_muse(exe):
                continue
            p, seen = ppid, set()
            while p and p not in seen:
                seen.add(p)
                if p in wt_pids:
                    hits.append(pid)
                    break
                p = procs.get(p, (0, ''))[0]
        if len(hits) == 1:
            return hits[0]
        _l('wake: %d muses bajo pestana %r' % (len(hits), title))
        return None
    except Exception as e:
        _l('wake tab-match error %s' % type(e).__name__)
        return None


def _is_muse(exe):
    base = exe.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    return base in ('muse.exe', 'muse-code.exe') or \
        (base.startswith('muse-bin-') and base.endswith('.exe'))


def _ancestry_muse_pid():
    """PID de mi CLI: ancestro muse si existe (cadena viva), si no el unico muse vivo.
    El listener es huerfano (su shell murio), por eso el ancestro falla ahi."""
    procs = _snapshot()
    muses = [pid for pid, (ppid, exe) in procs.items() if _is_muse(exe)]
    mine = set()
    p = os.getpid()
    while p and p not in mine:
        mine.add(p)
        p = procs.get(p, (0, ''))[0]
    for pid in muses:
        if pid in mine:
            return pid
    if len(muses) == 1:
        return muses[0]
    _l('wake: %d muses vivos, sin ancestro claro' % len(muses))
    return None


def _conpty_inject(pid, text):
    """Inyecta texto+Enter al console input buffer (sin foco, sin ventanas)."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    try:
        k.FreeConsole()
    except Exception:
        pass
    if not k.AttachConsole(pid):
        _l('wake conpty: attach fallo pid=%d' % pid)
        return False
    try:
        class KEY_EVENT(ctypes.Structure):
            _fields_ = [('bKeyDown', wintypes.BOOL), ('wRepeatCount', wintypes.WORD),
                        ('wVirtualKeyCode', wintypes.WORD), ('wVirtualScanCode', wintypes.WORD),
                        ('uChar', wintypes.WCHAR), ('dwControlKeyState', wintypes.DWORD)]

        class INPUT(ctypes.Structure):
            class _U(ctypes.Union):
                _fields_ = [('KeyEvent', KEY_EVENT)]

            _fields_ = [('EventType', wintypes.WORD), ('Event', _U)]

        u32 = ctypes.windll.user32
        VK_SHIFT = 0x10

        def _ev(vk, scan, ch, down, ctrl=0):
            ev = INPUT()
            ev.EventType = 1
            ke = ev.Event.KeyEvent
            ke.bKeyDown = down
            ke.wRepeatCount = 1
            ke.wVirtualKeyCode = vk
            ke.wVirtualScanCode = scan
            ke.uChar = ch
            ke.dwControlKeyState = ctrl
            return ev

        seq = []
        for ch in text:
            if ch == '\r':
                seq.append(_ev(0x0D, 0x1C, ch, True))
                seq.append(_ev(0x0D, 0x1C, ch, False))
                continue
            vks = u32.VkKeyScanW(ord(ch))
            if vks == -1 or (vks & 0xFFFF) == 0xFFFF:
                vk, need_shift = 0x00, False
            else:
                vk, need_shift = vks & 0xFF, bool(vks & 0x100)
            scan = u32.MapVirtualKeyW(vk, 0) if vk else 0
            if need_shift:
                seq.append(_ev(VK_SHIFT, u32.MapVirtualKeyW(VK_SHIFT, 0), '\x00', True, VK_SHIFT))
            seq.append(_ev(vk, scan, ch, True, VK_SHIFT if need_shift else 0))
            seq.append(_ev(vk, scan, ch, False, VK_SHIFT if need_shift else 0))
            if need_shift:
                seq.append(_ev(VK_SHIFT, u32.MapVirtualKeyW(VK_SHIFT, 0), '\x00', False, 0))
        h = k.GetStdHandle(-10)
        written = wintypes.DWORD(0)
        ok = True
        if len(seq) > 4:
            arr1 = (INPUT * (len(seq) - 4))(*seq[:-4])
            ok = k.WriteConsoleInputW(h, arr1, len(seq) - 4, ctypes.byref(written)) and \
                written.value == len(seq) - 4
        time.sleep(0.8)
        arr2 = (INPUT * 4)(*seq[-4:])
        ok2 = k.WriteConsoleInputW(h, arr2, 4, ctypes.byref(written)) and written.value == 4
        return bool(ok and ok2)
    finally:
        k.FreeConsole()


def wake_tab(title):
    """Inyecta trigger por ConPTY al CLI correcto. Nunca toca foco, ventanas
    ni clipboard (01/11: el pegado por ventana interrumpia a Rafa al escribir).
    Sin pid claro, aborta seguro: el mensaje queda en sala + inbox."""
    try:
        pid, via = load_cli_pid(), 'pid-file'
        if not pid:
            pid, via = _muse_pid_for_tab(title), 'pestana'
        if not pid:
            pid, via = _ancestry_muse_pid(), 'ancestro'
        if pid and _conpty_inject(pid, TRIGGER + '\r\n'):
            _l('wake: inyectado ConPTY pid=%d (%s)' % (pid, via))
            return True
        _l('wake: sin pid claro o attach fallo, aborto seguro (inbox intacto)')
        return False
    except Exception as e:
        _l('wake error %s' % type(e).__name__)
        return False


def _still_pending(ids, path=INBOX):
    """Ids que siguen en inbox (sin consumir). Sin archivo = nada pendiente."""
    try:
        cur = json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return []
    items = cur if isinstance(cur, list) else [cur]
    have = set(str(m.get('message_id')) for m in items)
    return [i for i in ids if str(i) in have]


def _verify_loop(ids):
    """Entrega verificada: si el inbox no se consume, re-inyecta una vez."""
    time.sleep(VERIFY_SEC)
    if not _still_pending(ids):
        _l('wake: entrega confirmada')
        return
    _l('wake: sin confirmacion, reintento ids=%s' % ids)
    if wake_tab(load_title()):
        _l('wake: reintento enviado')
    time.sleep(VERIFY_SEC)
    pend = _still_pending(ids)
    if pend:
        _l('wake: SIN CONFIRMACION ids=%s (revisar manual)' % pend)
    else:
        _l('wake: entrega confirmada (2do intento)')


def _delayed_wake(delay, ids):
    """Wake diferido tras cooldown (cierra la carrera read-vs-queue)."""
    global _wake_scheduled, _last_wake
    time.sleep(delay)
    _wake_scheduled = False
    if not _still_pending(ids):
        return
    _last_wake = time.time()
    if wake_tab(load_title()):
        _l('wake: trigger diferido enviado')
        threading.Thread(target=_verify_loop, args=(ids,), daemon=True).start()


def notify(text, chat_id, message_id):
    """Escribe inbox y despierta (con cooldown). True si inbox quedo."""
    global _last_wake, _wake_scheduled
    write_inbox(build_inbox(text, chat_id, message_id))
    now = time.time()
    if now - _last_wake < COOLDOWN_SEC:
        _l('wake: cooldown, solo inbox')
        if not _wake_scheduled:
            _wake_scheduled = True
            delay = COOLDOWN_SEC - (now - _last_wake) + 1
            threading.Thread(target=_delayed_wake, args=(delay, [message_id]),
                             daemon=True).start()
        return True
    _last_wake = now
    if wake_tab(load_title()):
        _l('wake: trigger enviado')
        threading.Thread(target=_verify_loop, args=([message_id],), daemon=True).start()
    return True


def _outbox_loop(base_getter):
    import urllib.request
    import urllib.parse
    while True:
        try:
            if os.path.exists(OUTBOX):
                with open(OUTBOX, encoding='utf-8') as f:
                    ob = json.load(f)
                contenido = (ob.get('contenido') or '').strip()
                voz = bool(ob.get('voz'))
                os.unlink(OUTBOX)
                if contenido:
                    base, cid = base_getter()
                    if base:
                        data = urllib.parse.urlencode({'chat_id': cid, 'text': contenido}).encode()
                        req = urllib.request.Request(base + '/sendMessage', data=data)
                        urllib.request.urlopen(req, timeout=20).read()
                        if voz:
                            env = os.path.join(V2, 'muse_tg_enviar.py')
                            subprocess.run([sys.executable, env, contenido, '--solo-voz'],
                                           timeout=180)
                        _l('outbox => telegram (%d chars)%s' % (len(contenido), ' +voz' if voz else ''))
            time.sleep(2)
        except Exception as e:
            _l('outbox error %s' % type(e).__name__)
            time.sleep(5)


def ensure_started(logfn, base_getter):
    global _started
    configure(logfn)
    if _started:
        return
    _started = True
    t = threading.Thread(target=_outbox_loop, args=(base_getter,), daemon=True)
    t.start()
