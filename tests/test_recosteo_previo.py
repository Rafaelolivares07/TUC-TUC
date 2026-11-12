# -*- coding: utf-8 -*-
"""Recosteo previo al ajuste fisico (2026-11-12, pedido Rafa).

Antes de grabar un ajuste por conteo fisico se corre el recosteo del item
(base limpia) y se muestra al usuario. El post-recosteo existente se
conserva. Aplica a ambos llamadores del motor (fisico e inv-dist).
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
fs = io.open(BASE + '/templates/inventario_fisico.html', encoding='utf-8').read()

# 1. Motor: recosteo previo ANTES de leer el saldo
i_def = py.find('def registrar_conteo_fisico_unificado(')
i_pre = py.find("origen='previo_conteo_fisico'")
i_p1 = py.find('# 1. Obtener producto y saldo actual en la sede')
check('previo existe', i_pre > 0)
check('previo antes de leer saldo', 0 < i_def < i_pre < i_p1)
check('previo acotado a la sede', 'bodega=centro_utilidad_id' in py)

# 2. Resumen antes/despues hasta la respuesta
check('motor retorna recosteo_previo', '"recosteo_previo": recosteo_previo' in py)
check('resumen antes/despues', 'stock_antes' in py and 'costo_despues' in py)
check('guardar-item lo expone', "'recosteo_previo': res_ajuste" in py)

# 3. Post-recosteo conservado + UI lo muestra
check('post-recosteo intacto',
      '        _recostear_producto(conn, negocio_id, producto_id)\n' in py)
check('UI muestra recosteo previo',
      'recosteo_previo' in fs and 'Recosteo previo' in fs)

print('fails:', len(fails))
sys.exit(1 if fails else 0)
