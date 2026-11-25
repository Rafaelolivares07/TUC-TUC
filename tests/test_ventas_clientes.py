# -*- coding: utf-8 -*-
"""Reporte ventas por cliente (2026-11-22, pedido Rafa).

Clon de ventas-costos agrupado por cliente: misma pagina (filtros
fechas juntas + franja horaria aparte con explicacion, centro, PDF),
tabla por cliente
(Cliente|Docs|Ticket|Cant|Venta|Costo|Margen|%) y detalle por documento
con columna Producto (no Cliente). Sin edicion de tiempos (eso vive
en la pagina por producto).
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


from app.blueprints.inventarios import _query_reporte_ventas_clientes


class _FakeCur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.sql = ''
        self.params = ()

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = tuple(params)
        return _FakeCur(self._rows)


CANNED = [
    {'cli_id': 7, 'cli_nombre': 'Pepito Perez', 'docs': 3,
     'cantidad_vendida': 10.0, 'total_ventas_pesos': 100000.0,
     'total_costo_pesos': 60000.0, 'total_costo_kardex': 60500.0,
     'minutos_prep_pond': 30.0, 'minutos_ens_pond': 20.0},
    {'cli_id': None, 'cli_nombre': 'Mostrador', 'docs': 1,
     'cantidad_vendida': 2.0, 'total_ventas_pesos': 20000.0,
     'total_costo_pesos': 0.0, 'total_costo_kardex': 0.0,
     'minutos_prep_pond': 0.0, 'minutos_ens_pond': 4.0},
]


def _corre(rows=CANNED, **kw):
    c = _FakeConn(rows)
    kw.setdefault('costo_hora_mod', 16000.0)
    kw.setdefault('personas_mod', 1.0)
    datos = _query_reporte_ventas_clientes(c, 59, '2026-11-01', '2026-11-22', **kw)
    return c, datos


# 1. Agrupacion y matematica por cliente
c0, d0 = _corre()
check('agrupa: 2 filas', len(d0) == 2, str(len(d0)))
check('grupo con id', d0[0]['cliente_id'] == 7 and d0[0]['nombre_cliente'] == 'Pepito Perez')
check('grupo mostrador', d0[1]['cliente_id'] is None and d0[1]['nombre_cliente'] == 'Mostrador')
check('ticket promedio', abs(d0[0]['ticket_promedio'] - 100000.0 / 3) < 0.01)
_mod0 = 50.0 * 16000.0 / 60.0
check('MOD ponderado', abs(d0[0]['total_mod'] - _mod0) < 0.01, str(d0[0]['total_mod']))
check('margen total', abs(d0[0]['margen_total'] - (100000.0 - 60000.0 - _mod0)) < 0.01)
check('desfase >100 flaggea', d0[0]['tiene_desfase'] is True)
check('costo cero flaggea', d0[1]['tiene_costo_cero'] is True)
check('minutos por cliente', d0[0]['minutos_prep'] == 30.0 and d0[0]['minutos_ens'] == 20.0)

# 2. SQL: agrupacion + params + reuso de horas
check('sql agrupa por cliente', 'COALESCE(ped.cliente_id, ped.id_tercero)' in c0.sql
      and 'GROUP BY' in c0.sql)
check('sql une terceros para nombre', 'JOIN terceros' in c0.sql)
check('sql minutos ponderados', 'minutos_prep_pond' in c0.sql and 'minutos_ens_pond' in c0.sql)
check('sin horas: params intactos', list(c0.params) == [59, '2026-11-01', '2026-11-22', 59],
      str(list(c0.params)))
c1, _d1 = _corre(hora_desde='11:00', hora_hasta='15:00')
check('horas reutilizadas', '::time' in c1.sql and '11:00' in c1.params and '15:01' in c1.params)

# 3. Rutas y registro (pines de fuente)
inv_src = (BASE / 'app' / 'blueprints' / 'inventarios.py').read_text(encoding='utf-8')
check('ruta pagina', "@bp.route('/ventas-clientes')" in inv_src)
check('vista standalone', 'def ventas_clientes_standalone' in inv_src)
check('api reporte', 'reporte-ventas-clientes' in inv_src)
check('api detalle', 'reporte-ventas-clientes/detalle' in inv_src)
check('api pdf', 'reporte-ventas-clientes/pdf' in inv_src)
check('redirect por tab', "'ventas_clientes'" in inv_src)
busc_src = (BASE / 'app' / 'buscador_motor.py').read_text(encoding='utf-8')
check('omni: entrada clientes', "'ventas_clientes'" in busc_src
      and '/ventas-clientes/{nid}' in busc_src)
init_src = (BASE / 'app' / '__init__.py').read_text(encoding='utf-8')
check('bypass subdominio', "/ventas-clientes" in init_src)

# 4. Plantilla clonada y adaptada
TPL = BASE / 'templates' / 'ventas_clientes.html'
check('plantilla existe', TPL.exists())
html = TPL.read_text(encoding='utf-8') if TPL.exists() else ''
check('titulo por cliente', 'Margen de Contribuci\u00f3n por Cliente' in html)
_parts = html.split('<thead')
check('tres thead (tabla + detalle doc + detalle grupo)', len(_parts) == 4, str(len(_parts)))
_main = _parts[1] if len(_parts) > 1 else ''
_det = _parts[2] if len(_parts) > 2 else ''
_gru = _parts[3] if len(_parts) > 3 else ''
check('tabla: Cliente+Docs+Ticket', '>Cliente<' in _main and '>Docs<' in _main
      and 'Ticket' in _main)
check('tabla: sin columna Producto', '>Producto<' not in _main)
check('detalle: columna Producto', '>Producto<' in _det)
check('detalle: sin columna Cliente', '>Cliente<' not in _det)
check('grupo: cols Producto+Docs+Margen', '>Producto</th>' in _gru and '>Docs</th>' in _gru
      and '>Margen</th>' in _gru)
check('detalle: pasa cliente', 'cliente_id=' in html and 'cliente_nombre=' in html)
check('urls api clientes', 'reporte-ventas-clientes?' in html
      and 'reporte-ventas-clientes/detalle?' in html
      and 'reporte-ventas-clientes/pdf?' in html)
check('horas incluidas', 'id="vc-hora-desde"' in html and 'vcHorasQS()' in html)
_c_d = html.find('id="vc-desde"')
_c_hd = html.find('id="vc-hora-desde"')
_c_h = html.find('id="vc-hasta"')
_c_hh = html.find('id="vc-hora-hasta"')
check('orden: fechas juntas, horas aparte despues',
      0 < _c_d < _c_h < _c_hd < _c_hh)
check('franja explicada', 'dentro de cada d' in html
      and '11:00 AM a 3:00 PM' in html and '12:00 AM a 11:59 PM' in html
      and '6:00 PM a 2:00 AM' in html and 'trasnoche' in html)
check('colspan 8/10', 'desgloseVisibleVC ? 10 : 8' in html)
check('sin editor tiempos', 'actualizarTiempoProdVC' not in html)

# 5. Conmutador documento/agrupado en detalle (2026-11-24, pedido Rafa)
check('toggle vistas', "vcVistaClientes(this,'doc')" in html and "vcVistaClientes(this,'grupo')" in html)
check('toggle rotulos', 'Por documento' in html and 'Por producto' in html)
check('titulo dual', 'Agrupado por Producto' in html and 'vc-det-titulo' in html)
check('cuerpo detalle', 'vc-det-cuerpo' in html)
check('cache doc+docs', 'detailRow._vcDocs = docs' in html and 'detailRow._vcHtmlDoc' in html)
check('agrupador puro', 'function vcAgruparDocs(docs, modo)' in html)
check('grupo productos', 'function vcGrupoProductosHTML(docs)' in html)
check('grupo usa modo producto', "vcAgruparDocs(docs, 'producto')" in html)
check('grupo col Producto', '>Producto</th>' in html)

# 6. CSS propio sin CDN (2026-11-25, caso Margarita)
check('sin tailwind CDN', 'cdn.tailwindcss.com' not in html)
check('sin google fonts', 'fonts.googleapis.com' not in html and 'fonts.gstatic.com' not in html)
check('link css propio', '/static/CSS/app.css?v=' in html)
_css = (BASE / 'static' / 'CSS' / 'app.css').read_text(encoding='utf-8')
check('css existe y pesa', len(_css) > 50000)
check('css trae Inter self-host', 'font-family:Inter' in _css and '/static/fonts/Inter-' in _css)
check('css trae tailwind', '.bg-slate-50' in _css and '.text-emerald-700' in _css)
check('woff2 en disco', os.path.exists(BASE / 'static' / 'fonts' / 'Inter-700.woff2') and os.path.exists(BASE / 'static' / 'fonts' / 'JetBrainsMono-400.woff2'))

print('fails:', len(fails))
sys.exit(1 if fails else 0)
