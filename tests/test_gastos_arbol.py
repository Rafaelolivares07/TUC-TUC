# -*- coding: utf-8 -*-
"""Arbol en autocomplete concepto gasto (2026-11-21, pedido Rafa).

Cada cuenta se cuelga bajo su padre real (codigo_padre, dato PUC):
mayor = titulo gris sin clic, auxiliar = escogible indentado.
Si la consulta no trae ni una auxiliar, aviso claro en vez de silencio.
"""
import io
import sys

BASE = 'C:/Users/RAFAEL OLIVARES/Documents/TucTucV2'
PY = io.open(BASE + '/app/blueprints/contabilidad.py', encoding='utf-8').read()
HTML = io.open(BASE + '/templates/gastos_pane.html', encoding='utf-8').read()
fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


def cuerpo(nombre_def):
    ini = PY.find('def %s' % nombre_def)
    assert ini > 0, nombre_def
    fin = PY.find('\ndef ', ini + 4)
    return PY[ini:fin if fin > 0 else len(PY)]


buscar = cuerpo('api_gastos_conceptos_buscar')
lineas_get = cuerpo('api_gastos_lineas')

check('buscar select trae codigo_padre', 'AS codigo_padre' in buscar)
check('buscar completa padres de referencia', 'padres' in buscar and 'ANY(' in buscar)
check('buscar json pasa codigo_padre', "'codigo_padre'" in buscar)
check('buscar sin derivar padre por digitos', 'codigo[:' not in buscar)
check('lineas conceptos trae codigo_padre', 'codigo_padre' in lineas_get)

check('builder buildFilasArbol', 'function buildFilasArbol' in HTML)
check('arbol cuelga por codigo_padre', 'codigo_padre' in HTML)
check('indentacion por profundidad', 'padding-left' in HTML)
check('aviso sin auxiliar', 'rubro para escoger' in HTML)
check('huerfanos no se pierden', 'visitados' in HTML)
check('gasConceptos pasa codigo_padre',
      'codigo_padre' in HTML.split('gasConceptos = (d.conceptos')[1].split('clearGasConcepto')[0])

print('fails:', len(fails))
sys.exit(1 if fails else 0)
