# -*- coding: utf-8 -*-
"""Auditor documentos: D/C siempre, columna grabado, orden por columnas.

Caso Rafa 2026-11-11 (desk -> "documento"): la tabla solo mostraba debitos,
sin fechahora de grabado y sin reordenar.
1) montosDC espeja: un solo lado conocido se replica (el documento cuadra).
2) Backend expone grabado_en (MIN created_at fusionado) en ambos endpoints;
   front pinta columna Grabado junto a Fecha.
3) Headers ordenables: tercero ordena en cliente, general pide orden+dir.
Uso: python tests/test_auditor_orden_grabado.py (raiz TucTucV2)
"""
import os

fails = []
total = [0]


def check(nombre, cond):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre)
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = open(os.path.join(ROOT, 'app', 'blueprints', 'inventarios.py'), encoding='utf-8').read()
TPL = open(os.path.join(ROOT, 'templates', 'auditor_documentos.html'), encoding='utf-8').read()

_a0 = PY.find('def api_mantenimiento_documentos_tercero(')
_a1 = PY.find('def _num_documento_limpio(')
TER = PY[_a0:_a1] if _a0 >= 0 and _a1 > _a0 else ''
_r0 = PY.find('def api_mantenimiento_documentos_recientes(')
_r1 = PY.find('def api_mantenimiento_tipos_documentos(')
REC = PY[_r0:_r1] if _r0 >= 0 and _r1 > _r0 else ''

# 1. Espejo D/C en montosDC
_m = TPL.find('function montosDC(')
_mont = TPL[_m:_m + 1500] if _m >= 0 else ''
check('front montosDC espeja lados', 'Espejo' in _mont
      and 'if (!d && c) d = c' in _mont and 'if (!c && d) c = d' in _mont)

# 2. Grabado backend + front
check('recientes inv trae grabado', 'MIN(mi.created_at)' in REC)
check('recientes cont trae grabado', 'MIN(mc.created_at)' in REC)
check('recientes expone grabado_en', "'grabado_en'" in REC)
check('tercero expone grabado_en', "'grabado_en'" in TER)
check('front helper fechahora', 'function formatearFechahoraLocal(' in TPL)
_fh = TPL.find('id="aud-tabla-tbody"')
_head = TPL[:_fh] if _fh >= 0 else ''
check('th Grabado junto a Fecha',
      _head.find('>Fecha <') >= 0 and _head.find('Grabado') > _head.find('>Fecha <')
      and _head.find('Grabado') < _head.find('>Documento <'))
check('fila pinta grabado', 'formatearFechahoraLocal(doc.grabado_en)' in TPL)
check('colspans a 8', TPL.count('colspan="8"') >= 4)
check('footer colspan 4', 'colspan="4"' in TPL)

# 3. Ordenamiento
check('headers con data-orden', TPL.count('data-orden=') >= 6)
check('front ordenarPor existe', 'function ordenarPor(' in TPL)
check('front orden cliente tercero', 'function ordenarDocsCliente(' in TPL)
check('general envia orden+dir', "orden" in TPL and "appState.orden" in TPL)
check('recientes acepta orden+dir',
      "request.args.get('orden'" in REC and "request.args.get('dir'" in REC)
check('recientes valida orden', '_ORDENES_AUD' in REC or 'orden not in' in REC)
check('recientes helper montos py', '_audit_montos_dc' in PY)

# 4. Valor facial + saldo D-C (reporte Rafa 11/11: ventas mezclaban costo/precio)
check('ventas a valor facial',
      'if (tPed !== null) { d = Number(tPed); c = Number(tPed); }' in _mont)
check('sin mezcla costo/precio', 'd = Number(tInv); c = Number(tPed)' not in _mont)
check('saldo calculado D-C', 'let saldoVal = saldoDoc(doc);' in TPL and 'return (m.d || 0) - (m.c || 0);' in TPL)
check('footer suma diferencia', 'totS += saldoDoc(x);' in TPL and 'return (m.d || 0) - (m.c || 0);' in TPL)
check('py montos facial', 'd, c = t_ped, t_ped' in PY)

print(f'\n{total[0] - len(fails)}/{total[0]} OK' + (f'  FALLOS: {fails}' if fails else ''))
raise SystemExit(1 if fails else 0)
