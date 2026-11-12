# -*- coding: utf-8 -*-
"""Acta en kardex + 7 datos omni (2026-11-12, pedido Rafa).

Endpoint kardex enriquecido (sin endpoint nuevo): ultima_acta del producto
y comparacion acta.stock_sistema vs linea.stock_anterior (si difieren, hubo
recosteo despues: NO se usa historial, orden explicita de Rafa). Kardex L3
muestra franja acta con aviso; fila omni Ver movimientos pinta 7 datos.
"""
import io
import sys

BASE = 'C:/Users/RAFAEL OLIVARES/Documents/TucTucV2'
fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


py = io.open(BASE + '/app/blueprints/inventarios.py', encoding='utf-8').read()
kx = io.open(BASE + '/templates/partials/kardex_js.html', encoding='utf-8').read()
om = io.open(BASE + '/templates/partials/buscador_omni.html', encoding='utf-8').read()

# 1. Endpoint: ultima_acta + comparacion con la linea (sin historial)
check('kardex devuelve ultima_acta', "'ultima_acta': ultima_acta" in py)
check('query ultima acta por fecha',
      'FROM inventario_fisico_actas' in py and 'ORDER BY fecha_hora DESC, id DESC' in py)
check('linea ligada ajuste/conteo', "motivo IN ('ajuste', 'conteo_conforme')" in py)
check('flag sistema_cambiado', "'sistema_cambiado'" in py and 'sist_en_acta' in py)
check('sin historial recosteos', 'recosteo_posterior_acta' not in py)

# 2. Kardex L3: franja acta + aviso
check('firma recibe acta',
      'renderizarAuditoriaKardex(auditoria, productoId, acta)' in kx)
check('llamada pasa d.ultima_acta',
      'renderizarAuditoriaKardex(d.auditoria, productoId, d.ultima_acta)' in kx)
check('franja sist/contado/dif',
      'acta.stock_sistema' in kx and 'acta.cantidad_contada' in kx and 'acta.diferencia' in kx)
check('aviso ya no rige', 'ya no rige' in kx and 'acta.saldo_anterior_actual' in kx)

# 3. Omni: 7 datos en Ver movimientos (misma fila, sin fila nueva)
check('omniCompletar7 existe', 'window.omniCompletar7 = async function(pid, idx, intento)' in om)
check('fetch kardex liviano',
      "'/api/inventario/producto/' + pid + '/kardex?por_pagina=1'" in om)
check('pinta recosteo/cuadra', 'Recosteo S' in om and "'cuadra'" in om)
check('pinta cascada/compras/acta',
      'Cascada ' in om and 'Compras raras ' in om and 'Acta ' in om)
check('disparo tras fila Kardex', 'window.omniCompletar7(p.id, idx)' in om)
check('omni dif uds con signo', "('uds ' + (difU >= 0 ? '+' : '') + omniFmt(difU))" in om)
check('omni causa pura', 'valor_inconsistente && !a.stock_inconsistente && !a.costo_inconsistente' in om)
check('kardex Uds junto a Dif', 'Uds:' in kx and 'difUds' in kx)
check('omni fila envuelve', "classList.remove('truncate')" in om and 'whitespace-normal' in om)
check('omni reintento unico', 'omniCompletar7(pid, idx, 1)' in om and '!intento' in om)

print('fails:', len(fails))
sys.exit(1 if fails else 0)
