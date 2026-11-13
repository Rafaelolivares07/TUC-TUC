# -*- coding: utf-8 -*-
"""Catalogo unico en datos: semilla + urls + omni filtrado (04/11).
Uso: python tests/test_catalogo_pantallas.py (raiz TucTucV2)
"""
import os
import sys

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

# Contrato 13/11: el wrapper corre 1x/worker; los pines van contra el impl
from app.blueprints.core import (  # noqa: E402
    _asegurar_pantallas_catalogo_impl as _asegurar_pantallas_catalogo,
    _url_pantalla, _endpoints_otorgados, _manuales_otorgados)
from app import buscador_motor as motor  # noqa: E402
from app.buscador_motor import _CATALOGO_PANTALLAS, _MIGRAR_GRANTS  # noqa: E402


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, existe=False, endpoints=(), queries=()):
        self.stmts = []
        self.existe = existe
        self.endpoints = set(endpoints)
        self.queries = set(queries)
        self.commits = 0

    def execute(self, q, p=None):
        self.stmts.append(q)
        if q.strip().startswith('SELECT 1 FROM pantallas WHERE endpoint'):
            return _Cur([{'x': 1}] if self.existe else [])
        if q.strip().startswith('SELECT id FROM pantallas WHERE clave'):
            return _Cur([{'id': 7}] if self.existe else [])
        if q.strip().startswith('SELECT id FROM pantallas WHERE endpoint'):
            return _Cur([{'id': 9}] if self.existe else [])
        if 'SELECT p.endpoint FROM permisos_terceros' in q:
            return _Cur([{'endpoint': e} for e in self.endpoints])
        if 'SELECT p.query FROM permisos_terceros' in q:
            return _Cur([{'query': e} for e in self.queries])
        if 'FROM terceros WHERE id' in q:
            return _Cur([{'id': p[0]}])
        return _Cur([])

    def commit(self):
        self.commits += 1


# 1. semilla inserta 59 filas nuevas
c = _Conn(existe=False)
_asegurar_pantallas_catalogo(c)
stmts = ' '.join(c.stmts)
check('seed crea tabla', 'CREATE TABLE IF NOT EXISTS pantallas' in stmts)
check('seed 7 columnas', stmts.count('ADD COLUMN IF NOT EXISTS') == 7)
check('seed indice unico', 'ux_pantallas_clave' in stmts)
check('seed 59 inserts', sum('INSERT INTO pantallas' in s for s in c.stmts) == 59)
_dels = [s for s in c.stmts if s.strip().startswith('DELETE')]
check('seed delete solo huerfanos', len(_dels) == 59 and all('NOT EXISTS (SELECT 1 FROM permisos_terceros' in s for s in _dels))
check('seed commit', c.commits == 1)
check('datos 59', len(_CATALOGO_PANTALLAS) == 59)
check('datos 34+25', sum(1 for f in _CATALOGO_PANTALLAS if f[9]) == 34)

# 2. semilla con todo existente rellena huecos sin insertar
c = _Conn(existe=True)
_asegurar_pantallas_catalogo(c)
check('backfill sin inserts', not any('INSERT INTO pantallas' in s for s in c.stmts))
check('backfill 59 por-ID', sum('UPDATE pantallas SET clave =' in s for s in c.stmts) == 59)

# 3. constructor de URL
check('tpl pagina', _url_pantalla({'url_tpl': '/contabilidad/{nid}', 'endpoint': 'x', 'query': None}, 59, None) == '/contabilidad/59')
check('tpl tab', _url_pantalla({'url_tpl': '/contabilidad/{nid}?tab=puc', 'endpoint': 'x', 'query': 'tab=puc'}, 59, None) == '/contabilidad/59?tab=puc')
check('tpl sin nid', _url_pantalla({'url_tpl': '/contabilidad/{nid}', 'endpoint': 'x', 'query': None}, None, None) == '#')
check('tpl sin slug', _url_pantalla({'url_tpl': '/tienda/{slug}/caja', 'endpoint': 'x', 'query': None}, 59, None) == '#')
check('kardex slug', _url_pantalla({'url_tpl': None, 'endpoint': 'inventarios.kardex_standalone', 'query': None}, 59, 'sand') == 'https://sand.tuc-tuc.co/kardex')
check('kardex nid', _url_pantalla({'url_tpl': None, 'endpoint': 'inventarios.kardex_standalone', 'query': None}, 59, None) == '/inventario/59/kardex')

from flask import Flask, Blueprint  # noqa: E402
_fapp = Flask(__name__)
_bpi = Blueprint('inventarios', __name__)


@_bpi.route('/inventario/<int:negocio_id>')
def admin_inventario(negocio_id):
    return ''


_bpt = Blueprint('tiendas', __name__)


@_bpt.route('/tienda/<slug>/caja')
def tienda_caja(slug):
    return ''


_fapp.register_blueprint(_bpi)
_fapp.register_blueprint(_bpt)
_fapp.test_request_context('/').push()
check('resolver nid', _url_pantalla({'url_tpl': None, 'endpoint': 'inventarios.admin_inventario', 'query': None}, 59, None) == '/inventario/59')
check('resolver slug', _url_pantalla({'url_tpl': None, 'endpoint': 'tiendas.tienda_caja', 'query': None}, 59, 'sand') == '/tienda/sand/caja')
check('resolver query', _url_pantalla({'url_tpl': None, 'endpoint': 'inventarios.admin_inventario', 'query': 'tab=puc'}, 59, None) == '/inventario/59?tab=puc')
check('resolver nada', _url_pantalla({'url_tpl': None, 'endpoint': 'no.existe', 'query': None}, 59, None) == '#')

# 4. endpoints otorgados
c = _Conn(endpoints={'a.b', 'c.d', None})
check('admin todo', _endpoints_otorgados(c, {'rol': 'Administrador'}) is None)
check('colaborador set', _endpoints_otorgados(c, {'usuario_id': 58, 'active_negocio_id': 59}) == {'a.b', 'c.d'})
check('sin negocio vacio', _endpoints_otorgados(c, {'usuario_id': 58}) == set())

# 5. catalogo omni desde filas + filtro
FILAS = [
    {'nombre': 'Caja POS / Terminal de Ventas', 'modulo': 'Ventas', 'icono': 'C', 'endpoint': 'tiendas.tienda_caja', 'query': None, 'url_tpl': '/tienda/{slug}/caja', 'keywords': '["caja", "pos"]', 'sugerido': True},
    {'nombre': 'Plan Único de Cuentas (PUC)', 'modulo': 'Contabilidad > Cuentas', 'icono': 'P', 'endpoint': 'contabilidad.admin_contabilidad', 'query': 'tab=puc', 'url_tpl': '/contabilidad/{nid}?tab=puc', 'keywords': '["puc"]', 'sugerido': True},
    {'nombre': 'Rota', 'modulo': 'X', 'icono': '', 'endpoint': 'x.y', 'query': None, 'url_tpl': '/r', 'keywords': 'no-json{', 'sugerido': False},
]
base = motor._obtener_catalogo_base(negocio_id=59, slug='sand', filas=FILAS)
check('filas forma', len(base) == 3 and base[0]['url'] == '/tienda/sand/caja' and base[1]['keywords'] == ['puc'])
check('filas endpoint', base[0]['endpoint'] == 'tiendas.tienda_caja')
check('keywords roto', base[2]['keywords'] == ['no-json{'])
filtr = motor._obtener_catalogo_base(negocio_id=59, slug='sand', otorgados={'tiendas.tienda_caja'}, filas=FILAS)
check('filtro endpoints', [e['titulo'] for e in filtr] == ['Caja POS / Terminal de Ventas'])
dup = motor._obtener_catalogo_base(negocio_id=59, slug='sand', filas=FILAS + [FILAS[0]])
check('dedupe endpoint+query', len(dup) == 3)
res = motor.buscar_omni('puc', negocio_id=59, slug='sand', filas=FILAS)
check('omni halla', any(r['titulo'].startswith('Plan Único') for r in res['rutas']))
res2 = motor.buscar_omni('puc', negocio_id=59, slug='sand', otorgados={'tiendas.tienda_caja'}, filas=FILAS)
check('omni filtra', all('Plan Único' not in r['titulo'] for r in res2['rutas']))
res3 = motor.buscar_omni('', negocio_id=59, slug='sand', otorgados={'tiendas.tienda_caja'}, filas=FILAS)
check('sugeridos filtran', [r['titulo'] for r in res3['rutas']] == ['Caja POS / Terminal de Ventas'])

# 6. pines
SRC = open(os.path.join(ROOT, 'app', 'blueprints', 'core.py'), encoding='utf-8').read()
check('api pasa otorgados', 'otorgados=otorgados' in SRC)
check('enforce endpoint', 'AND p.endpoint = %s' in SRC)
check('selects otorgable', SRC.count('otorgable IS NOT FALSE') >= 4)
check('agrupar modulo col', "p.get('modulo') or _SECCIONES_MENU" in SRC)
INI = open(os.path.join(ROOT, 'app', '__init__.py'), encoding='utf-8').read()
check('arranque siembra', '_asegurar_pantallas_catalogo' in INI)
MOT = open(os.path.join(ROOT, 'app', 'buscador_motor.py'), encoding='utf-8').read()
check('motor lee BD', 'FROM pantallas' in MOT)
check('motor sin dict fijo', "'titulo': 'Caja POS / Terminal de Ventas'" not in MOT)

# 7. manuales de ayuda como filas otorgables
_MAN = [f for f in _CATALOGO_PANTALLAS if f[0].startswith('manual_')]
check('manuales 7', len(_MAN) == 7)
check('manuales modulo', all(f[4] == 'Manuales de ayuda' for f in _MAN))
check('manuales endpoint', all(f[2] == 'core.core_ver_manual' for f in _MAN))
check('manuales query', sorted(f[5] for f in _MAN) == sorted(
    'doc=' + s for s in ('contabilidad', 'tienda', 'restaurante', 'domotica',
                         'asistencia-remota', 'alegra', 'vendedor')))
check('manuales orden', sorted(f[8] for f in _MAN) == [300, 310, 320, 330, 340, 350, 360])
check('manuales otorgables', all(f[9] for f in _MAN))
_MANF = {'nombre': 'Manual de Tienda', 'modulo': 'Manuales de ayuda', 'icono': 'L',
         'endpoint': 'core.core_ver_manual', 'query': 'doc=tienda', 'url_tpl': '/docs/tienda',
         'keywords': '["manual"]', 'sugerido': False}
check('rutas excluye manuales',
      len(motor._obtener_catalogo_base(negocio_id=59, slug='sand', filas=FILAS + [_MANF])) == 3)
_cq = _Conn(queries={'doc=tienda', 'doc=restaurante', None})
check('man admin todo', _manuales_otorgados(_cq, {'rol': 'Administrador'}) is None)
check('man colaborador set',
      _manuales_otorgados(_cq, {'usuario_id': 58, 'active_negocio_id': 59}) == {'tienda', 'restaurante'})
check('man sin negocio vacio', _manuales_otorgados(_cq, {'usuario_id': 58}) == set())
_rm = motor.buscar_omni('mesa', filas=[])
_sm = {a['url'].split('/docs/')[1].split('#')[0] for a in _rm['ayuda']}
check('omni ayuda multimanual', len(_sm) >= 2 and 'restaurante' in _sm)
_rf = motor.buscar_omni('mesa', filas=[], manuales_otorgados={'restaurante'})
check('omni ayuda filtra',
      len(_rf['ayuda']) > 0 and all(a['url'].startswith('/docs/restaurante') for a in _rf['ayuda']))
_r0 = motor.buscar_omni('mesa', filas=[], manuales_otorgados=set())
check('omni ayuda vacia', _r0['ayuda'] == [])
check('gate excluye visor', "'core.core_ver_manual'" in SRC)
check('visor chequea slug', "'manual_' + manual_slug" in SRC)
check('api pasa manuales', 'manuales_otorgados=manuales' in SRC)
check('motor filtra ayuda', 'manuales_otorgados is not None' in MOT)
import glob
_shadow = [(f, ln.strip()) for f in glob.glob(os.path.join(ROOT, 'app', 'blueprints', '*.py'))
           for ln in open(f, encoding='utf-8')
           if ("@bp.route('/docs/" in ln or '@bp.route("/docs/' in ln) and '<' not in ln]
check('visor sin sombras', _shadow == [], str(_shadow)[:200])

# 8. sanar grants viejos + full-text manuales
check('migra mapa', _MIGRAR_GRANTS == (('tiendas.admin_caja', 'caja_pos'),))
_CAJA = [f for f in _CATALOGO_PANTALLAS if f[0] == 'caja_pos'][0]
check('caja match ventas', 'Ventas' in _CAJA[1] and _CAJA[4] == 'Ventas'
      and _CAJA[2] == 'tiendas.tienda_caja')
TIE = open(os.path.join(ROOT, 'app', 'blueprints', 'tiendas.py'), encoding='utf-8').read()
check('caja endpoint real', 'def tienda_caja(' in TIE and 'def admin_caja(' not in TIE)
_cm = _Conn(existe=True)
_asegurar_pantallas_catalogo(_cm)
_sm = ' '.join(_cm.stmts)
check('migra update grants', 'UPDATE permisos_terceros SET pantalla_id' in _sm)
check('migra sin duplicar', 'DELETE FROM permisos_terceros WHERE pantalla_id' in _sm)
check('migra limpia huerfana', 'AND id <>' in _sm)
_rf = motor.buscar_omni('angulos', filas=[])
check('omni full-text cuerpo', any(a['url'].startswith('/docs/tienda') for a in _rf['ayuda']))
_FIL = motor._filas_desde_semilla()
_ot = {'inventarios.admin_inventario', 'contabilidad.admin_contabilidad',
       'core.core_gestion_permisos', 'tiendas.tienda_caja'}
_rm = motor.buscar_omni('ventas', otorgados=_ot, filas=_FIL)
check('margarita halla caja', any('Caja POS' in r['titulo'] for r in _rm['rutas']))

# 9. LIKE manual psycopg2-seguro + tries separados (04/11 pm: % pelado + ESCAPE
# doble rompian la consulta y el except comun vaciaba el omni de todo logueado)
check('like porciento doble', "LIKE 'manual\\_%%'" in SRC)
check('like sin escape', "LIKE 'manual\\_%%' ESCAPE" not in SRC)
check('tries separados', '_c1 = get_db_connection()' in SRC
      and 'manuales = _manuales_otorgados(_c1, session)' in SRC)

print(f'--- {total[0] - len(fails)}/{total[0]} ---')
sys.exit(1 if fails else 0)
