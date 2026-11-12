# -*- coding: utf-8 -*-
"""Boton Desk/DESK unificado en 6 pantallas (2026-11-12, pedido Rafa).

El header lleva el boton al desk con href absoluto (regla kardex b3e85d8:
las salidas al monstruo no usan /inicio relativo). Rotulo: DESK en las
migradas; kardex se queda en 'Desk' por orden explicita de Rafa
(mayusculas indiferentes, ya tiene lo que quiere: no tocar).
"""
import io
import sys

BASE = 'C:/Users/RAFAEL OLIVARES/Documents/TucTucV2'
ESPERADO = {
    'kardex': 'Desk',
    'ventas_costos': 'DESK',
    'catalogo_productos': 'DESK',
    'entradas': 'DESK',
    'produccion': 'DESK',
    'tesoreria': 'DESK',
}
fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


for tpl, rotulo in sorted(ESPERADO.items()):
    html = io.open(BASE + '/templates/%s.html' % tpl, encoding='utf-8').read()
    check('%s rotulado %s' % (tpl, rotulo), '>%s<' % rotulo in html)
    check('%s sin boton Inicio' % tpl, '>Inicio<' not in html)
    check('%s href desk absoluto' % tpl,
          'href="https://desk.tuc-tuc.co/inicio"' in html)

print('fails:', len(fails))
sys.exit(1 if fails else 0)
