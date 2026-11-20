# -*- coding: utf-8 -*-
"""Tarjeta estandar en pagina propia: ruta + template unico + poda de modales (19/11).
Uso: python tests/test_tarjeta_standalone.py (raiz TucTucV2)
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


def read(rel):
    with open(rel, encoding='utf-8') as f:
        return f.read()


def crlf_pure(rel):
    with open(rel, 'rb') as f:
        raw = f.read()
    return b'\n' in raw and raw.count(b'\r\n') == raw.count(b'\n')


INV = 'app/blueprints/inventarios.py'
TPL = 'templates/tarjeta.html'
CUATRO = [
    'templates/inventario_admin.html',
    'templates/catalogo_productos.html',
    'templates/entradas.html',
    'templates/produccion.html',
]

py = read(INV)
check('ruta /tarjeta/<producto_id>', "@bp.route('/tarjeta/<int:producto_id>')" in py)
check('ruta /tarjeta/<negocio>/<producto>', "@bp.route('/tarjeta/<int:negocio_id>/<int:producto_id>')" in py)
check('def tarjeta_standalone', 'def tarjeta_standalone(producto_id=None, negocio_id=None)' in py)
check('ruta renderiza tarjeta.html', "render_template('tarjeta.html'" in py)
check('ruta pide login', 'tarjeta_standalone' in py and 'auth.admin_login' in py)

tj = read(TPL)
from jinja2 import Environment
try:
    Environment().parse(tj)
    check('tarjeta.html parsea Jinja', True)
except Exception as e:  # noqa: BLE001
    check('tarjeta.html parsea Jinja', False, str(e)[:120])
for marca in ['id="overlay-tarjeta"', 'tarjeta-prod-id', 'tarjeta-nombre-prod',
              'guardarTarjeta', 'cargarTarjeta', 'volverTarjeta',
              'tarjeta-page-ac-input', 'TARJETA_PRODUCTO_ID', 'Decimales vista:']:
    check(f'tarjeta.html trae {marca}', marca in tj)
for resto in ['cerrarModalTarjeta', 'abrirModalTarjeta(', 'class="overlay hidden"',
              'function cargarProductos(', 'cargarTarjetasResumen();']:
    check(f'tarjeta.html sin {resto}', resto not in tj)
lineas = tj.splitlines()
usos_cp = [i for i, s in enumerate(lineas) if 'cargarProductos(' in s]
guardados = all('typeof cargarProductos' in '\n'.join(lineas[max(0, i - 2):i + 1]) for i in usos_cp)
check('tarjeta.html cargarProductos solo tras guarda typeof', bool(usos_cp) and guardados)

for t in CUATRO:
    txt = read(t)
    base = os.path.basename(t)
    check(f'{base} sin modal tarjeta', 'id="overlay-tarjeta"' not in txt)
    for fn in ['function abrirModalTarjeta(', 'function guardarTarjeta(',
               'function renderLineasTarjeta(', 'function cargarTarjeta(',
               'cerrarModalTarjeta']:
        check(f'{base} sin {fn}', fn not in txt)
    check(f'{base} CRLF puro', crlf_pure(t))
check('tarjeta.html CRLF puro', crlf_pure(TPL))

inv = read('templates/inventario_admin.html')
check('inventario navega a /tarjeta/', "/tarjeta/'+NEGOCIO_ID+'" in inv)
check('inventario conserva resumen', 'renderTarjetasTable' in inv)
check('inventario conserva borrado reporte', 'eliminarTarjetaDirecta' in inv and 'ejecutarEliminacionTarjeta' in inv)
check('inventario ?tarjeta= redirige', 'params.get' in inv and '/tarjeta/' in inv)
cat = read('templates/catalogo_productos.html')
check('catalogo navega a /tarjeta/', "/tarjeta/'+NEGOCIO_ID+'" in cat)
check('catalogo ?tarjeta= redirige', 'abrirTarjetaInicialDesdeUrl();' in cat)
ent = read('templates/entradas.html')
check('entradas navega a /tarjeta/', "/tarjeta/'+NEGOCIO_ID+'" in ent)
pro = read('templates/produccion.html')
check('produccion boton Ver tarjeta', 'verTarjetaProduccion' in pro and 'Ver tarjeta' in pro)

import re
ESPERADOS = {
    'templates/inventario_admin.html': 4,
    'templates/catalogo_productos.html': 1,
    'templates/entradas.html': 1,
}
for t, n in ESPERADOS.items():
    txt = read(t)
    base = os.path.basename(t)
    malos = re.findall(r"location\.href='/tarjeta/'[^\"\n]*\)\"", txt)
    check(f'{base} onclick /tarjeta/ sin parentesis sobrante', not malos, str(malos[:2])[:150])
    onclicks = re.findall(r'onclick="[^"\n]*location\.href=\'/tarjeta/[^"\n]*"', txt)
    check(f'{base} {n} boton(es) a /tarjeta/', len(onclicks) == n, f'hay {len(onclicks)}')
    check(f'{base} botones /tarjeta/ parentesis balanceados',
          all(o.count('(') == o.count(')') for o in onclicks))
check('produccion abre /tarjeta/ en funcion (no inline)', "window.open('/tarjeta/'" in pro)

om = read('templates/partials/buscador_omni.html')
check('omni badge dice Tarjeta estandar', "'Tarjeta est\\u00e1ndar \\u203a'" in om)
check('omni sin badge Receta', "'Receta \\u203a'" not in om)
check('omni titulo dato dice Tarjeta estandar', "titulo: 'Tarjeta est\\u00e1ndar" in om)
check('omni sin titulo Receta producto', "titulo: 'Receta ' + p.nombre" not in om)
check('omni meta explica receta/formula/mezcla/ensamble', 'receta, f\\u00f3rmula, mezcla o ensamble seg\\u00fan el negocio' in om)
check('omni sin Costo receta', 'Costo receta' not in om and 'Sin costo receta' not in om)
mo = read('app/buscador_motor.py')
check('motor url receta directa a /tarjeta/', "'receta': f'/tarjeta/{nid}/{pid}'" in mo)
check('motor sin rodeo catalogo ?tarjeta=', '?tarjeta=1&producto_id={pid}' not in mo)
res = read('templates/restaurante_admin.html')
check('restaurante link directo /tarjeta/', '/tarjeta/{{ restaurante.tercero_id }}/${i.id}' in res)
check('restaurante sin rodeo ?tarjeta=', '?tarjeta=1&producto_id=' not in res)
tie = read('templates/tienda_admin.html')
check('tienda link directo /tarjeta/', '/tarjeta/{{ tienda.tercero_id }}/${p.id}' in tie)
check('tienda sin rodeo ?tarjeta=', '?tarjeta=1&producto_id=' not in tie)
check('reporte badge T. estandar', '>T. est\u00e1ndar</span>' in inv)
check('reporte sin badge Receta', 'color:#0369a1">Receta</span>' not in inv)
check('tarjeta.html subtitulo explicativo', 'en restaurantes es la receta, en otros negocios la f' in tj)

check('omni semilla entrada puntual', "'inv_tarjeta_puntual'" in mo)
check('omni puntual endpoint tarjeta', "'inventarios.tarjeta_standalone'" in mo)
check('omni puntual url consulta', "'/tarjeta?negocio_id={nid}'" in mo)
check('omni puntual keywords receta/formula/mezcla', "'receta puntual'" in mo and "'formula puntual'" in mo and "'mezcla producto'" in mo)
py_inv = read('app/blueprints/inventarios.py')
check('ruta /tarjeta consulta', "@bp.route('/tarjeta')" in py_inv)
check('tarjeta producto opcional', 'def tarjeta_standalone(producto_id=None, negocio_id=None)' in py_inv)
check('tarjeta consulta lee negocio_id', "request.args.get('negocio_id', type=int)" in py_inv)
check('tarjeta render sin producto', "producto_id=prod_row['id'] if prod_row else None" in py_inv)
check('tarjeta.html id null sin producto', "producto_id if producto_id else 'null'" in tj)
check('tarjeta.html rama consulta', '!TARJETA_PRODUCTO_ID' in tj and ').focus()' in tj)
check('tarjeta.html titulo condicional', '{% if producto_nombre %}' in tj)
check('tarjeta.html guia consulta', 'Busca un producto arriba para ver su tarjeta' in tj)
check('omni reporte keywords mezcla/componentes', "'mezclas'" in mo and "'componentes'" in mo)

lin_rep = next(s for s in mo.splitlines() if "'inv_tab_tarjetas'" in s)
lin_pun = next(s for s in mo.splitlines() if "'inv_tarjeta_puntual'" in s)
for palabra in ['ensamble', 'ensamblar', 'ensambles', 'produccion', 'producciones historicas']:
    check(f'reporte responde a {palabra}', palabra in lin_rep)
    check(f'puntual responde a {palabra}', palabra in lin_pun)

check('omni titulo reporte explicito', "'Tarjetas Estándar (todas: fórmulas, recetas y ensambles)'" in mo)
check('omni sin titulo reporte viejo', "'Tarjetas Estándar (Fórmulas y Recetas)'" not in mo)
check('omni titulo puntual explicito', "'Tarjeta Estándar puntual (ver una sola)'" in mo)
check('omni sin titulo puntual viejo', "'Tarjeta Estándar puntual (ver una)'" not in mo)
check('motor dict descripciones', '_DESCRIPCIONES' in mo and "('inventarios.tarjeta_standalone', '')" in mo and "('inventarios.admin_inventario', 'tab=tarjetas')" in mo)
check('motor descripcion reporte todas', 'aquí las ves y gestionas TODAS' in mo)
check('motor descripcion puntual una', 'aquí ves y editas UNA sola' in mo)
check('motor fila trae descripcion', "'descripcion': _DESCRIPCIONES.get(_k, '')" in mo)
check('omni fila pinta descripcion', 'r.descripcion' in om and 'escapeHtml(r.descripcion)' in om)

check('omni semilla historial produccion', "'inv_produccion_historial'" in mo)
check('omni historial url vista', "'/produccion/{nid}?vista=historial'" in mo)
lin_hist = next((s for s in mo.splitlines() if "'inv_produccion_historial'" in s), '')
for palabra in ['producciones historicas', 'historial produccion', 'que se produjo', 'ordenes anteriores']:
    check(f'historial responde a {palabra}', palabra in lin_hist)
check('motor desc produccion antelacion', "('inventarios.produccion_standalone', '')" in mo and 'prepara con antelación' in mo)
check('motor desc historial que-se-produjo', "('inventarios.produccion_standalone', 'vista=historial')" in mo and 'Qué se produjo antes' in mo)
check('motor desc ensamble momento-venta', "('inventarios.admin_inventario', 'tab=ensambles')" in mo and 'momento exacto de la venta' in mo)
check('motor desc ensambles-historicos consulta', "('inventarios.admin_inventario', 'tab=ensambles_historicos')" in mo and 'Solo consulta' in mo)
pro = read('templates/produccion.html')
check('produccion lee vista historial', "qp.get('vista')" in pro and "vista === 'historial'" in pro)
check('produccion abre historial y baja', 'prod-historial-wrapper' in pro and 'toggleHistorialProduccion()' in pro)

check('omni rutas boton dice Abrir', '>Abrir ➔</span>' in om)
check('omni rutas sin boton Saltar', '>Saltar ➔</span>' not in om)

check('tarjeta subtitulo dice para 1 unidad', 'Cantidades para producir 1 unidad' in tj)
check('tarjeta header Cant por 1 ud', 'Cant. × 1 ud.' in tj)
check('tarjeta header Subtotal por 1 ud', 'Subtotal × 1 ud.' in tj)
check('tarjeta total por 1 unidad', 'Costo total × 1 unidad' in tj)
check('tarjeta th cantidad con title', 'title="Cantidad de cada insumo para producir 1 unidad"' in tj)
check('tarjeta input cant con title', 'title="Cantidad para 1 unidad"' in tj)

check('tarjeta badge para-1-unidad junto al nombre', 'id="tarjeta-para-1-unidad"' in tj)
check('tarjeta badge 1 grande', 'text-2xl font-black text-rose-600 font-mono leading-none">1</span>' in tj)
check('tarjeta badge UNIDAD evidente', 'text-sm font-black text-rose-700">UNIDAD</span>' in tj)

print(f'--- {total[0] - len(fails)}/{total[0]} OK ---')
if fails:
    print('FALLAS:', fails)
    sys.exit(1)
