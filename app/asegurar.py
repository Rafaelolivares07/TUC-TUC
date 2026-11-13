# -*- coding: utf-8 -*-
"""Guardias de arranque: DDL una-sola-vez + liderazgo del scheduler.

Causa raiz de los cuelgues 12/11 y 13/11: el DDL de `_asegurar_*` corria en
cada peticion y en cada tick del scheduler, desde los 2 workers x 4 hilos.
La cola de candados eterna trababa los 8 hilos y la app quedaba en 000.

Reglas desde 2026-11-13:
- Todo DDL idempotente (`CREATE/ALTER IF NOT EXISTS`) corre UNA vez por
  proceso worker, con candado entre hilos. Si falla, se marca igual y se
  registra: se reintenta al reiniciar el worker (cada deploy o max-requests).
  Nunca rompe la peticion en curso.
- Los jobs del scheduler solo los corre el worker lider (lockfile + pid +
  sello). Si el lider muere, otro toma el mando en el proximo tick.
Solo stdlib: este modulo debe seguir importable sin flask ni psycopg2.
"""

import os
import tempfile
import threading
import time

_flags = {}
_lock = threading.Lock()


def asegurar_una_vez(clave, fn):
    """Corre fn() una sola vez por proceso. Hilos concurrentes: solo uno
    corre, los demas esperan el candado y siguen. Si fn() falla, se deja
    constancia y se marca igual (reintento al reiniciar el worker)."""
    if _flags.get(clave):
        return
    with _lock:
        if _flags.get(clave):
            return
        try:
            fn()
        except Exception as e:
            print("[asegurar] %s fallo (reintento al reiniciar): %s: %s"
                  % (clave, type(e).__name__, e))
        finally:
            _flags[clave] = True


_SCHED_LOCK = os.path.join(tempfile.gettempdir(), 'tuctuc_scheduler.lock')
_SCHED_STALE_SEG = 900


def _leer_sello():
    try:
        with open(_SCHED_LOCK) as f:
            partes = f.read().strip().split()
        return int(partes[0]), float(partes[1]) if len(partes) > 1 else 0.0
    except Exception:
        return None, 0.0


def _pid_vivo(pid):
    # Windows: NUNCA os.kill(pid, 0): CTRL_C_EVENT es 0 e inyecta
    # Ctrl+C real (al padre mata la consola; a si mismo suicida).
    # Se pregunta al kernel sin senales (13/11, 4 sesiones muertas).
    if os.name == 'nt':
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not h:
                return False
            try:
                code = ctypes.wintypes.DWORD()
                if not ctypes.windll.kernel32.GetExitCodeProcess(
                        h, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(h)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def reclamar_scheduler():
    """True si este proceso es el lider del scheduler. El lider re-sella en
    cada tick; si muere (o el sello envejece >15 min), otro worker lo toma."""
    yo = os.getpid()
    ahora = time.time()
    try:
        fd = os.open(_SCHED_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, ("%d %f" % (yo, ahora)).encode())
        os.close(fd)
        return True
    except FileExistsError:
        pass
    except OSError:
        return False
    dueno, sello = _leer_sello()
    if dueno == yo:
        try:
            with open(_SCHED_LOCK, 'w') as f:
                f.write("%d %f" % (yo, ahora))
        except OSError:
            pass
        return True
    if dueno is not None and _pid_vivo(dueno) and (ahora - sello) < _SCHED_STALE_SEG:
        return False
    try:
        tmp = "%s.%d" % (_SCHED_LOCK, yo)
        with open(tmp, 'w') as f:
            f.write("%d %f" % (yo, ahora))
        os.replace(tmp, _SCHED_LOCK)
    except OSError:
        return False
    dueno2, _sello2 = _leer_sello()
    return dueno2 == yo
