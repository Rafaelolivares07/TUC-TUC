# -*- coding: utf-8 -*-
"""muse_wake: despierta la sesion Muse (trigger __MUSE__) y reenvia su outbox a Telegram.
Lo mejor del merlin_daemon: inbox/outbox + pegar trigger + minimizar + cooldown.
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
TRIGGER = '__MUSE__'
COOLDOWN_SEC = 30
_started = False
_last_wake = 0.0
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


def _cycle_tabs_to(title, wshell):
    """Busca la pestana en TODAS las ventanas WT con Ctrl+Tab verificado. True si queda enfocada."""
    try:
        import win32gui
        import win32process
        import win32api
        hwnds = []

        def _enum(h, acc):
            if not win32gui.IsWindowVisible(h):
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(h)
                hp = win32api.OpenProcess(1024, False, pid)
                name = win32process.GetModuleFileNameEx(hp, 0).lower()
                win32api.CloseHandle(hp)
                if 'windowsterminal' in name:
                    acc.append((h, pid))
            except Exception:
                pass

        win32gui.EnumWindows(_enum, hwnds)
        _l('wake ciclo: %d ventanas WT' % len(hwnds))
        for hwnd, pid in hwnds:
            try:
                try:
                    wshell.AppActivate(pid)
                except Exception:
                    pass
                time.sleep(0.5)
                if win32gui.GetForegroundWindow() != hwnd:
                    try:
                        wshell.AppActivate(hwnd)
                    except Exception:
                        pass
                    time.sleep(0.5)
                if win32gui.GetForegroundWindow() != hwnd:
                    _l('wake ciclo: foco no llego pid=%d' % pid)
                    continue
                vistos = []
                for _ in range(30):
                    if win32gui.GetForegroundWindow() != hwnd:
                        _l('wake ciclo: foco perdido a mitad')
                        break
                    t = win32gui.GetWindowText(hwnd) or ''
                    if title.lower() in t.lower():
                        return True
                    if len(vistos) < 6:
                        vistos.append(t[:25])
                    wshell.SendKeys('^{TAB}')
                    time.sleep(0.3)
                else:
                    _l('wake ciclo: 30 tabs sin match pid=%d' % pid)
                    continue
                _l('wake ciclo: vistos=%s' % vistos)
            except Exception as e:
                _l('wake ciclo ventana error %s' % type(e).__name__)
                continue
        return False
    except Exception as e:
        _l('wake ciclo error %s' % type(e).__name__)
        return False


def _is_muse(exe):
    base = exe.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    return base in ('muse.exe', 'muse-code.exe') or \
        (base.startswith('muse-bin-') and base.endswith('.exe'))


def _ancestry_muse_pid():
    """PID de mi CLI: ancestro muse si existe (cadena viva), si no el unico muse vivo.
    El listener es huerfano (su shell murio), por eso el ancestro falla ahi."""
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

    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(0x2, 0)
    procs = {}
    pe = PE()
    pe.dwSize = ctypes.sizeof(PE)
    if k.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            procs[pe.th32ProcessID] = (pe.th32ParentProcessID, pe.szExeFile.lower())
            if not k.Process32NextW(snap, ctypes.byref(pe)):
                break
    k.CloseHandle(snap)
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
    """Enfoca pestana por titulo, pega trigger, minimiza, devuelve foco. False si aborta."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        import win32gui
        import win32clipboard
        pid = _ancestry_muse_pid()
        if pid and _conpty_inject(pid, TRIGGER + '\r\n'):
            _l('wake: inyectado ConPTY pid=%d' % pid)
            return True
        _l('wake: ConPTY fallo, via ventana...')
        if not title:
            _l('wake: sin titulo, aborto')
            return False
        wshell = win32com.client.Dispatch('WScript.Shell')
        try:
            prev = win32gui.GetForegroundWindow()
        except Exception:
            prev = None
        matched = False
        if wshell.AppActivate(title):
            time.sleep(0.3)
            actual = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            if title.lower() in actual.lower():
                matched = True
        if not matched:
            _l('wake: via rapida fallo, ciclo pestanas...')
            matched = _cycle_tabs_to(title, wshell)
        if not matched:
            _l('wake: pestana no encontrada, aborto seguro')
            return False
        old = None
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                old = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception:
            pass
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(TRIGGER)
            win32clipboard.CloseClipboard()
            time.sleep(0.3)
            wshell.SendKeys('^v')
            time.sleep(0.4)
            wshell.SendKeys('{ENTER}')
            time.sleep(0.5)
            wshell.SendKeys('{ENTER}')
            time.sleep(0.5)
        finally:
            if old is not None:
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, old)
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
        try:
            import ctypes
            hwnd = win32gui.GetForegroundWindow()
            if hwnd and hwnd != prev:
                win32gui.ShowWindow(hwnd, 6)
            if prev:
                wshell.AppActivate(int(ctypes.windll.user32.GetWindowThreadProcessId(prev, None)))
        except Exception:
            pass
        return True
    except Exception as e:
        _l('wake error %s' % type(e).__name__)
        return False


def notify(text, chat_id, message_id):
    """Escribe inbox y despierta (con cooldown). True si inbox quedo."""
    global _last_wake
    write_inbox(build_inbox(text, chat_id, message_id))
    now = time.time()
    if now - _last_wake < COOLDOWN_SEC:
        _l('wake: cooldown, solo inbox')
        return True
    _last_wake = now
    if wake_tab(load_title()):
        _l('wake: trigger enviado')
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
