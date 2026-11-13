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

# 13. precalentar: paridad estatica lista <-> codigo
eleg = set()
for f in glob.glob(os.path.join(ROOT, 'app', 'blueprints', '*.py')):
    mod = os.path.basename(f)[:-3]
    for ln in open(f, encoding='utf-8').read().splitlines():
        s = ln.strip()
        if s.startswith('def _asegurar_') or s.startswith('def _crear_tablas('):
            nom = s[4:s.index('(')]
            if nom.endswith('_impl'):
                continue
            args = s[s.index('(') + 1:s.index(')')]
            narg = 0 if not args.strip() else len(args.split(','))
            if narg <= 1:
                eleg.add(mod + '.' + nom)
eleg.discard('crm._asegurar_pywebpush')
reg = set(m + '.' + n for m, n in asegurar.PRECALENTAR)
check('precalentar paridad', eleg == reg,
      'extra:' + str(sorted(reg - eleg))[:120] + ' falta:' + str(sorted(eleg - reg))[:120])

# 14-16. precalentar funcional con modulo falso
import types  # noqa: E402
_calls = []


def _mkfake():
    def _u0():
        asegurar.asegurar_una_vez('fake.u0', lambda: _calls.append(('u0',)))
    def _u1(conn):
        asegurar.asegurar_una_vez('fake.u1', lambda: _calls.append(('u1', conn)))
    def _uboom(conn):
        asegurar.asegurar_una_vez('fake.uboom', lambda: 1 / 0)
    m = types.ModuleType('app.blueprints.fakeb')
    m._u0 = _u0
    m._u1 = _u1
    m._uboom = _uboom
    return m


class _FC:
    def close(self):
        pass


_orig_pre = asegurar.PRECALENTAR
_orig_rec = asegurar.reclamar_scheduler
_mdb = types.ModuleType('app.db')
_fconn = _FC()
_mdb.get_db_connection = lambda: _fconn
sys.modules['app.db'] = _mdb
sys.modules['app.blueprints.fakeb'] = _mkfake()
asegurar.PRECALENTAR = [('fakeb', '_u0'), ('fakeb', '_u1'), ('fakeb', '_uboom')]
asegurar.reclamar_scheduler = lambda: True
try:
    asegurar._flags.pop('fake.u0', None)
    asegurar._flags.pop('fake.u1', None)
    asegurar._flags.pop('fake.uboom', None)
    _calls.clear()
    _n1 = asegurar.precalentar_ddl()
    check('precalentar corre todo', _n1 == 3 and [c[0] for c in _calls] == ['u0', 'u1']
          and _calls[1][1] is _fconn, str(_n1) + str(_calls)[:100])
    _calls.clear()
    _n2 = asegurar.precalentar_ddl()
    check('precalentar no repite', _n2 == 3 and _calls == [], str(_n2))
    asegurar.reclamar_scheduler = lambda: False
    _calls.clear()
    _n3 = asegurar.precalentar_ddl()
    check('precalentar respeta lider', _n3 == 0 and _calls == [], str(_n3))
finally:
    asegurar.PRECALENTAR = _orig_pre
    asegurar.reclamar_scheduler = _orig_rec
    sys.modules.pop('app.db', None)
    sys.modules.pop('app.blueprints.fakeb', None)
    asegurar._flags.pop('fake.u0', None)
    asegurar._flags.pop('fake.u1', None)
    asegurar._flags.pop('fake.uboom', None)
# 17. wrappers anidados no traban (RLock 13/11)
asegurar._flags.pop('fake.outer', None)
asegurar._flags.pop('fake.inner', None)
_nest = []
def _inner():
    asegurar.asegurar_una_vez('fake.inner', lambda: _nest.append('in'))
def _outer():
    asegurar.asegurar_una_vez('fake.outer', lambda: (_inner(), _nest.append('out')))
import threading as _th  # noqa: E402
_t = _th.Thread(target=_outer, daemon=True)
_t.start()
_t.join(10)
check('anidado no traba', (not _t.is_alive()) and _nest == ['in', 'out'], str(_nest)[:60])
asegurar._flags.pop('fake.outer', None)
asegurar._flags.pop('fake.inner', None)
print('---')
print(f"OK {total[0]} checks" if not fails else f"FALLOS: {fails}")
sys.exit(1 if fails else 0)
