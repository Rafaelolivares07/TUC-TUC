"""Vigilante menu-voz del arranque Muse (2026-11-18, orden Rafa).

Habla SOLO cuando el menu de temas ya esta pintado en el chat, nunca antes.
Contrato con FIRSTMSG de INICIAR_MUSE.bat: la agente crea
%TEMP%\\muse_menu_listo.mark al pintar el menu; este script lo ve y avisa
por voz (Salome via hablar.ps1).

Falla-cierra: sin marca de boot, sin mark fresco, con respuesta de Rafa en
el chat, con otro vigilante vivo o pasado el timeout => silencio y exit 0.
Uso: pythonw muse_menu_voz.py   (el .bat lo lanza oculto en [8/8])
Self-test: python muse_menu_voz.py --probar
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

V2 = Path(__file__).resolve().parent
TMP = Path(os.environ.get('TEMP', r'C:\Windows\Temp'))
BOOT = TMP / 'muse_boot.mark'
MARK = TMP / 'muse_menu_listo.mark'
LOCK = TMP / 'muse_menu_voz.lock'
VOZ_TXT = TMP / 'muse_menu_voz.txt'
HABLAR = V2 / 'muse_voz' / 'hablar.ps1'
SESSIONS = Path(os.environ.get('USERPROFILE', '')) / '.local' / 'share' / 'muse' / 'sessions'

FRASE = 'mi amor, ya cargue todo y el menu esta en pantalla. Dime el numero del tema y arrancamos.'
TIMEOUT_MIN = 20
POLL_S = 2
GRACIA_S = 6
LOCK_MAX_MIN = 30


def menu_listo(mark=MARK, boot_mtime=None):
    """True si el mark existe y es de este boot (fresco)."""
    try:
        mt = mark.stat().st_mtime
    except OSError:
        return False
    return boot_mtime is None or mt >= boot_mtime


def adquirir_lock(lock=LOCK, max_min=LOCK_MAX_MIN):
    """True si tomamos el lock (instancia unica). Lock viejo se pisa."""
    try:
        age_min = (time.time() - lock.stat().st_mtime) / 60
        if age_min < max_min:
            return False
    except OSError:
        pass
    try:
        lock.write_text(f'{os.getpid()} {time.time()}', encoding='ascii')
        return True
    except OSError:
        return False


def usuario_contesto(sessions=SESSIONS, boot_mtime=0.0, mark_mtime=0.0):
    """True si Rafa escribio en el chat despues del mark (sesiones del boot).

    Superficie: eventos runtime.user_intent.accepted del session.jsonl
    (recorded_at en microsegundos epoch). Lineas malas se saltan.
    """
    try:
        logs = [p for p in sessions.rglob('session.jsonl')
                if p.stat().st_mtime > boot_mtime]
    except OSError:
        return False
    for p in logs:
        try:
            fh = p.open(encoding='utf-8')
        except OSError:
            continue
        with fh:
            for ln in fh:
                if 'user_intent.accepted' not in ln:
                    continue
                try:
                    o = json.loads(ln)
                except (ValueError, TypeError):
                    continue
                try:
                    if float(o.get('recorded_at', 0)) / 1e6 > mark_mtime:
                        return True
                except (ValueError, TypeError):
                    continue
    return False


def hablar(txt=VOZ_TXT, frase=FRASE, hablar_ps1=HABLAR):
    """Sintetiza+reproduce una vez (reintento unico si falla). Return True si sono."""
    ps = shutil.which('powershell') or r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    try:
        txt.write_text(frase, encoding='ascii')
    except OSError:
        return False
    for _ in range(2):
        try:
            r = subprocess.run([ps, '-NoProfile', '-File', str(hablar_ps1), str(txt)],
                               capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.SubprocessError):
            continue
        out = (r.stdout or '') + (r.stderr or '')
        if r.returncode == 0 and 'Traceback' not in out:
            return True
    return False


def main():
    try:
        boot_mtime = BOOT.stat().st_mtime
    except OSError:
        return 0
    if not adquirir_lock():
        return 0
    try:
        fin = time.time() + TIMEOUT_MIN * 60
        while time.time() < fin:
            if menu_listo(boot_mtime=boot_mtime):
                mark_mtime = MARK.stat().st_mtime
                time.sleep(GRACIA_S)
                if usuario_contesto(boot_mtime=boot_mtime, mark_mtime=mark_mtime):
                    return 0
                hablar()
                return 0
            time.sleep(POLL_S)
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass
    return 0


def probar():
    """Self-test con fixtures en TEMP (no habla, no toca el boot real)."""
    import tempfile
    fails = []

    def check(n, c):
        print(('PASS ' if c else 'FAIL ') + n)
        if not c:
            fails.append(n)

    d = Path(tempfile.mkdtemp(prefix='menuvoz_'))
    try:
        boot = d / 'boot.mark'
        mark = d / 'listo.mark'
        lock = d / 'voz.lock'
        boot.write_text('BOOT', encoding='ascii')
        t0 = boot.stat().st_mtime
        check('sin mark => no listo', menu_listo(mark, t0) is False)
        mark.write_text('viejo', encoding='ascii')
        viejo = t0 - 3600
        os.utime(mark, (viejo, viejo))
        check('mark viejo => no listo', menu_listo(mark, t0) is False)
        mark.write_text('2026-11-18T08:50:00', encoding='ascii')
        check('mark fresco => listo', menu_listo(mark, t0) is True)
        check('lock libre se toma', adquirir_lock(lock) is True)
        check('lock tomado se respeta', adquirir_lock(lock) is False)
        os.utime(lock, (viejo, viejo))
        check('lock viejo se pisa', adquirir_lock(lock) is True)

        ses = d / 'sessions' / '2026' / '11' / '18' / 'abc'
        ses.mkdir(parents=True)
        log = ses / 'session.jsonl'
        mm = mark.stat().st_mtime
        antes = int((mm - 60) * 1e6)
        despues = int((mm + 60) * 1e6)
        log.write_text(
            '{"record_type":"event","payload_type":"runtime.session","recorded_at":%d}\n'
            'linea corrupta sin json\n'
            '{"record_type":"event","payload_type":"runtime.user_intent.accepted","recorded_at":%d,"payload":{}}\n'
            % (antes, antes), encoding='utf-8')
        check('sin respuesta tras mark => silencio no aplica',
              usuario_contesto(ses.parent.parent.parent.parent, t0, mm) is False)
        with log.open('a', encoding='utf-8') as fh:
            fh.write('{"record_type":"event","payload_type":"runtime.user_intent.accepted","recorded_at":%d}\n' % despues)
        check('respuesta tras mark => se respeta',
              usuario_contesto(ses.parent.parent.parent.parent, t0, mm) is True)
        check('frase ASCII pura', all(ord(c) < 128 for c in FRASE))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print('PROBAR:', 'OK' if not fails else f'FAIL ({len(fails)})')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(probar() if len(sys.argv) > 1 and sys.argv[1] == '--probar' else main())
