# -*- coding: utf-8 -*-
"""DDL una-sola-vez + scheduler lider (13/11, raiz de los cuelgues 12/11-13/11).
Uso:  python tests/test_asegurar_unavez.py
Queda en disco; git lo ignora (regla test_*.py), se sube con -f.
"""
import importlib.util
import os
import sys
import threading
import time

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app import asegurar  # noqa: E402

# 1. corre una sola vez aunque se llame muchas veces
veces = [0]


def _trabajo():
    veces[0] += 1


asegurar.asegurar_una_vez('t1', _trabajo)
asegurar.asegurar_una_vez('t1', _trabajo)
asegurar.asegurar_una_vez('t1', _trabajo)
check('una vez en 3 llamadas', veces[0] == 1, repr(veces[0]))

# 2. hilos concurrentes: solo uno corre
veces2 = [0]
_lock_c = threading.Lock()


def _trabajo2():
    time.sleep(0.05)
    with _lock_c:
        veces2[0] += 1


hilos = [threading.Thread(target=lambda: asegurar.asegurar_una_vez('t2', _trabajo2))
         for _ in range(20)]
[t.start() for t in hilos]
[t.join() for t in hilos]
check('20 hilos -> 1 corrida', veces2[0] == 1, repr(veces2[0]))

# 3. si falla, no rompe y se marca igual (reintento al reiniciar)
veces3 = [0]


def _boom():
    veces3[0] += 1
    raise RuntimeError('ddl trabado')


try:
    asegurar.asegurar_una_vez('t3', _boom)
    asegurar.asegurar_una_vez('t3', _boom)
    ok3 = (veces3[0] == 1)
except Exception as e:  # noqa: BLE001
    ok3 = False
    extra3 = repr(e)
check('fallo no rompe + no reintenta', ok3, '' if ok3 else extra3)

# 4. claves distintas son independientes
veces4a, veces4b = [0], [0]
asegurar.asegurar_una_vez('t4a', lambda: veces4a.__setitem__(0, 1))
asegurar.asegurar_una_vez('t4b', lambda: veces4b.__setitem__(0, 1))
check('claves independientes', veces4a[0] == 1 and veces4b[0] == 1)

# 5. liderazgo scheduler: primero reclama, mismo pid revalida
_lock_tmp = os.path.join(ROOT, 'tests', '_tmp_sched_%d.lock' % os.getpid())
asegurar._SCHED_LOCK = _lock_tmp
if os.path.exists(_lock_tmp):
    os.unlink(_lock_tmp)
check('reclamo inicial', asegurar.reclamar_scheduler() is True)
check('revalida mismo pid', asegurar.reclamar_scheduler() is True)

# 6. lider vivo ajeno -> no quita (mock determinista: getppid es fragil,
# bajo pythonw/CIM el padre es un servicio inaccesible)
check('pid propio vivo', asegurar._pid_vivo(os.getpid()) is True)
_orig_vivo = asegurar._pid_vivo
asegurar._pid_vivo = lambda pid: True
try:
    with open(_lock_tmp, 'w') as f:
        f.write('%d %f' % (2 ** 30 - 7, time.time()))
    check('respeta lider vivo', asegurar.reclamar_scheduler() is False)
finally:
    asegurar._pid_vivo = _orig_vivo

# 7. lider muerto -> toma el mando
with open(_lock_tmp, 'w') as f:
    f.write('%d %f' % (2 ** 30, time.time()))
check('toma mando lider muerto', asegurar.reclamar_scheduler() is True)

# 8. sello viejo (>15 min) -> toma el mando aunque pid exista
with open(_lock_tmp, 'w') as f:
    f.write('%d %f' % (os.getppid(), time.time() - 2000))
check('toma mando sello viejo', asegurar.reclamar_scheduler() is True)
os.unlink(_lock_tmp)

# 9. scheduler envuelve los 4 jobs con _solo_lider
sched = open(os.path.join(ROOT, 'app', 'scheduler.py'), encoding='utf-8').read()
check('4 jobs con lider', sched.count('_solo_lider(') >= 5, str(sched.count('_solo_lider(')))

# 10. todo _impl tiene su wrapper una-vez (pin anti-regresion)
import glob  # noqa: E402
faltan = []
for f in glob.glob(os.path.join(ROOT, 'app', 'blueprints', '*.py')):
    src = open(f, encoding='utf-8').read()
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith('def ') and s.endswith('_impl(conn):'):
            nombre = s[4:-len('(conn):')]
            if f"asegurar_una_vez('{nombre}'" not in src and 'asegurar_una_vez(' not in src:
                faltan.append(os.path.basename(f) + ':' + nombre)
check('todo impl con wrapper', faltan == [], str(faltan)[:200])

# 11. sin SET timeout 0 en app (restaurantes lo restauraba a 0)
mal = []
for f in glob.glob(os.path.join(ROOT, 'app', 'blueprints', '*.py')):
    src = open(f, encoding='utf-8').read()
    if "statement_timeout = '0'" in src or 'statement_timeout = 0' in src:
        mal.append(os.path.basename(f))
check('sin timeout 0', mal == [], str(mal)[:200])

# 12. respaldo admin con tope propio (tablas grandes > 30s)
core = open(os.path.join(ROOT, 'app', 'blueprints', 'core.py'), encoding='utf-8').read()
check('backup tope 600s', 'SET statement_timeout = 600000' in core)

print('---')
print(f"OK {total[0]} checks" if not fails else f"FALLOS: {fails}")
sys.exit(1 if fails else 0)
