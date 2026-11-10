# -*- coding: utf-8 -*-
"""Voz: turno de audio entre terminales con mutex (10/11).

Caso Rafa: varios Muse reproducían al tiempo. El candado de reproducir.ps1
tenía carrera (Test-Path y luego New-Item: dos pasan a la vez) y habla_edge.py
no tenía ninguno (dos síntesis al mismo mp3). Ahora ambos toman el MISMO mutex
de sesion ('Local\\TucTucVoz', atómico, se libera si muere el dueño).
Uso: python tests/test_voz_turno.py (raiz TucTucV2)
"""
import os
import subprocess
import sys
import time

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = open(os.path.join(ROOT, 'muse_voz', 'reproducir.ps1'), encoding='utf-8').read()
PY = open(os.path.join(ROOT, 'muse_voz', 'habla_edge.py'), encoding='utf-8').read()
HAB = open(os.path.join(ROOT, 'muse_voz', 'hablar.ps1'), encoding='utf-8').read() if os.path.exists(os.path.join(ROOT, 'muse_voz', 'hablar.ps1')) else ''
MUTEX = 'Local\\TucTucVoz'

# 1. Mismo mutex en ambos lados (propiedad clave)
check('ps1 usa mutex sesion', MUTEX in PS1)
check('py usa mismo mutex', MUTEX in PY.replace('\\\\', '\\'))
check('ps1 espera turno', 'WaitOne(' in PS1)
check('ps1 suelta turno', 'ReleaseMutex()' in PS1)
check('py espera turno', 'WaitForSingleObject' in PY)
check('py suelta turno', 'ReleaseMutex' in PY)

# 2. Fuera la carrera vieja (revisar-y-luego-crear no es atómico)
check('ps1 sin New-Item candado', 'New-Item -ItemType Directory -Path $lockDir' not in PS1)

# 2b. hablar.ps1: un mp3 único por mensaje (nadie pisa el archivo ajeno)
check('hablar existe', bool(HAB))
check('hablar mp3 unico', '$PID' in HAB and 'Ticks' in HAB)
check('hablar usa habla+reproduce', 'habla_edge.py' in HAB and 'reproducir.ps1' in HAB)
check('hablar limpia mp3', 'Remove-Item $mp3' in HAB)

# 3. py_compila
r = subprocess.run([sys.executable, '-m', 'py_compile',
                    os.path.join(ROOT, 'muse_voz', 'habla_edge.py')],
                   capture_output=True, text=True, timeout=120)
check('py_compile habla_edge.py', r.returncode == 0, (r.stderr or '')[:200])

# 4. Funcional: el mutex serializa dos turnos (nombre de prueba aparte)
ps = (
    "$m = [System.Threading.Mutex]::new($false, 'Local\\TucTucVozTest'); "
    "$m.WaitOne(30000) | Out-Null; Start-Sleep -Seconds 2; $m.ReleaseMutex(); $m.Dispose()"
)
try:
    t0 = time.time()
    p1 = subprocess.Popen(['powershell', '-NoProfile', '-Command', ps],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(['powershell', '-NoProfile', '-Command', ps],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    c1 = p1.wait(timeout=60)
    c2 = p2.wait(timeout=60)
    dt = time.time() - t0
    check('dos turnos salen 0', c1 == 0 and c2 == 0, f'{c1},{c2}')
    check('turnos en fila (>=3.5s)', dt >= 3.5, f'{dt:.1f}s')
except Exception as e:
    check('harness mutex', False, f'{type(e).__name__}: {e}')

print(f'--- {total[0] - len(fails)}/{total[0]} OK ---')
sys.exit(1 if fails else 0)
