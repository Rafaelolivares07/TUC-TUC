# -*- coding: utf-8 -*-
"""Auditor MODO TERCERO: incluye documentos contables (10/11).

Caso Rafa: /auditor-documentos/59?tercero_id=113 (NAPOLEON. RULLIER) salia
vacio porque documentos-tercero solo miraba inventario + pedidos + saldos,
y la actividad de Napoleon vive en contabilidad (CxP 6.960.000 ctas 22/23,
RELACION DE DESEMBOLSOS #45). Cuarta capa: movimientos_contables agrupados
por documento, misma forma de fila que las otras capas.
Uso: python tests/test_auditor_tercero_contable.py (raiz TucTucV2)
"""
import os
import subprocess
import sys

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = open(os.path.join(ROOT, 'app', 'blueprints', 'inventarios.py'), encoding='utf-8').read()

_ini = PY.find('def api_mantenimiento_documentos_tercero(')
_fin = PY.find('\ndef ', _ini + 10)
FN = PY[_ini:_fin] if _ini >= 0 and _fin > _ini else ''
check('existe api documentos-tercero', bool(FN))

# 1. Cuarta capa contable dentro de la funcion
check('capa: FROM movimientos_contables', 'FROM movimientos_contables' in FN)
check('capa: filtra tercero_id', 'tercero_id = %s' in FN.replace('mc.tercero_id = %s', 'tercero_id = %s'))
check('capa: filtra negocio_id', 'mc.negocio_id = %s' in FN)
check('capa: agrupa por documento', 'GROUP BY' in FN.split('FROM movimientos_contables', 1)[1] if 'FROM movimientos_contables' in FN else False)

# 2. Misma forma de fila que las otras capas
check('fila: origen contable', "'origen': 'contable'" in FN)
_seg = FN.split("'origen': 'contable'", 1)[1][:600] if "'origen': 'contable'" in FN else ''
check('fila: trae total', "'total': float" in _seg)
check('fila: trae saldo_pendiente', "'saldo_pendiente': float" in _seg)
check('fila: nombre tipo puro', '_nombre_tipo_doc(' in FN and FN.rfind('_nombre_tipo_doc(') > FN.find('FROM movimientos_contables'))
check('fila: numero puro', '_num_documento_limpio(' in FN and FN.rfind('_num_documento_limpio(') > FN.find('FROM movimientos_contables'))

# 3. No pisa capas previas (dedupe por misma llave)
_ded = FN.split("'origen': 'contable'", 1)[0][-600:] if "'origen': 'contable'" in FN else ''
check('dedupe: respeta consolidado previo', 'if key in consolidated:' in _ded and 'continue' in _ded)

# 4. Saldo desde saldos por documento (misma JOIN que inventario)
check('saldo: join saldo_por_documentos', FN.count('saldo_por_documentos') >= 3)

# 5. py_compile del blueprint
r = subprocess.run([sys.executable, '-m', 'py_compile',
                    os.path.join(ROOT, 'app', 'blueprints', 'inventarios.py')],
                   capture_output=True, text=True, timeout=120)
check('py_compile inventarios.py', r.returncode == 0, (r.stderr or '')[:200])

print(f'--- {total[0] - len(fails)}/{total[0]} OK ---')
sys.exit(1 if fails else 0)
