# -*- coding: utf-8 -*-
"""Boton DESK en ventas-costos (2026-11-12, pedido Rafa).

El boton <- Inicio del header pasa a rotularse DESK (mayusculas): es la
marca de pantallas ya actualizadas al respecto. Y el href va absoluto al
desk, misma regla del kardex (b3e85d8): las salidas al monstruo no usan
/inicio relativo.
"""
import io
import sys

BASE = 'C:/Users/RAFAEL OLIVARES/Documents/TucTucV2'
fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


html = io.open(BASE + '/templates/ventas_costos.html', encoding='utf-8').read()

# 1. Rotulo DESK en mayusculas, sin resto de "Inicio" en botones
check('boton rotulado DESK', '>DESK<' in html)
check('sin boton Inicio', '>Inicio<' not in html)

# 2. Href absoluto al desk (no relativo)
check('href desk absoluto', 'href="https://desk.tuc-tuc.co/inicio"' in html)

# 3. Invariantes: flecha + marca corporativa intactas
i_nav = html.find('Navegacion y Contexto')
check('flecha del boton intacta', '&larr;' in html)
check('DESK dentro del bloque navegacion',
      0 < i_nav < html.find('>DESK<'))
check('marca TUC TUC intacta', 'TUC TUC' in html and 'negocio_nombre' in html)

print('fails:', len(fails))
sys.exit(1 if fails else 0)
