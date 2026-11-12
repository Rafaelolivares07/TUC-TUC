# -*- coding: utf-8 -*-
"""Paso 1 auditor: filas con D/C totales + saldo diferencia; fusion gemelas.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_auditor_totales_paso1.py
Caso Rafa: FV-650 mostraba 882k facial en la fila y 1.13M en el documento;
en modo tercero salia dos veces (gemela contable sin fusionar por llave
int vs str). Ahora: una fila por documento con todos los D/C + saldo D-C.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.blueprints.inventarios as inv  # noqa: E402

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


# ---------- _clave_tipo_doc ----------
check('clave helper existe', hasattr(inv, '_clave_tipo_doc'))
if hasattr(inv, '_clave_tipo_doc'):
    BYC = {'factura_de_venta': 6}
    BYN = {'factura de venta': 6}
    k = inv._clave_tipo_doc
    check('clave id manda', k(6, 'x', BYC, BYN) == 6)
    check('clave codigo resuelve', k(None, 'FACTURA_DE_VENTA', BYC, BYN) == 6)
    check('clave nombre resuelve', k(None, 'Factura de Venta', BYC, BYN) == 6)
    check('clave texto libre', k(None, 'otro', BYC, BYN) == 'otro')
    check('clave vacio', k(None, None, BYC, BYN) == '')

# ---------- _audit_montos_dc ----------
m = inv._audit_montos_dc
check('dc par explicito crudo',
      m({'total_debitos': 1138516.10, 'total_creditos': 1138516.10, 'origen': 'ambos'})
      == (1138516.10, 1138516.10))
check('dc cero no se espeja',
      m({'total_debitos': 0, 'total_creditos': 5780.18, 'origen': 'ambos'})
      == (0, 5780.18),
      repr(m({'total_debitos': 0, 'total_creditos': 5780.18, 'origen': 'ambos'})))
check('dc saldos se espeja',
      m({'total_debitos': 0, 'total_creditos': 100.0, 'origen': 'saldos'})
      == (100.0, 100.0))
check('dc facial intacto', m({'total_pedidos': 882000.0}) == (882000.0, 882000.0))

# ---------- _audit_saldo ----------
check('saldo helper existe', hasattr(inv, '_audit_saldo'))
if hasattr(inv, '_audit_saldo'):
    s = inv._audit_saldo
    check('saldo ignora cartera',
          s({'saldo_pendiente': 500.0, 'total_debitos': 100.0, 'total_creditos': 100.0})
          == 0.0)
    check('saldo diferencia',
          s({'total_debitos': 100.0, 'total_creditos': 90.0}) == 10.0)
    check('saldo cuadra cero',
          s({'total_debitos': 882000.0, 'total_creditos': 882000.0}) == 0.0)

# ---------- pines backend ----------
PY = (ROOT / 'app' / 'blueprints' / 'inventarios.py').read_text(encoding='utf-8')


def _fn(name):
    ini = PY.find('def %s(' % name)
    fin = PY.find('\ndef ', ini + 10)
    return PY[ini:fin] if ini >= 0 and fin > ini else ''


FN_T = _fn('api_mantenimiento_documentos_tercero')
FN_R = _fn('api_mantenimiento_documentos_recientes')
check('tercero: mapas id', 'types_id_by_code' in FN_T and 'types_id_by_name' in FN_T)
check('tercero: 4 ramas usan clave', FN_T.count('_clave_tipo_doc(') >= 4,
      str(FN_T.count('_clave_tipo_doc(')))
check('tercero: contable fusiona D/C',
      "'total_debitos'] = float(r['total_debitos']" in FN_T
      and "'total_creditos'] = float(r['total_creditos']" in FN_T)
check('recientes: suma creditos',
      'AS total_creditos' in FN_R and "WHEN mc.tipo IN ('credito', 'C')" in FN_R)
check('recientes: acumula grupos',
      ".get('total_debitos') or 0) + float(r['total_debitos']" in FN_R)
check('reparo: resuelve tercero',
      '_tercero_del_comprobante(conn, negocio_id, comprobante_id)' in PY)
check('reparo: imputa tercero',
      '_backfill_tercero_voucher(conn, negocio_id, comprobante_id, tercero_doc)' in PY)

# ---------- pines template ----------
TPL = (ROOT / 'templates' / 'auditor_documentos.html').read_text(encoding='utf-8')
_mi = TPL.find('function montosDC(')
_mf = TPL.find('\n    function ', _mi + 10)
FN_M = TPL[_mi:_mf] if _mi >= 0 and _mf > _mi else ''
check('tpl: crudo salvo saldos', "doc.origen === 'saldos'" in FN_M)
check('tpl: helper saldoDoc', 'function saldoDoc(' in TPL)
check('tpl: fila usa saldoDoc', 'let saldoVal = saldoDoc(doc);' in TPL)
check('tpl: pie usa saldoDoc', 'totS += saldoDoc(x);' in TPL)
check('tpl: orden usa saldoDoc', '[saldoDoc(d),' in TPL)
check('tpl: fuera badge cartera', "getElementById('tabla-badge-saldo-tercero')" not in TPL)
check('tpl: fuera saldo panel', "getElementById('det-doc-saldo-badge')" not in TPL)
check('tpl: cero cartera', 'saldo_pendiente' not in TPL)

# ---------- py_compile ----------
r = subprocess.run([sys.executable, '-m', 'py_compile',
                    str(ROOT / 'app' / 'blueprints' / 'inventarios.py')],
                   capture_output=True, text=True, timeout=120)
check('py_compile inventarios.py', r.returncode == 0, (r.stderr or '')[:200])

print(f'{total[0] - len(fails)}/{total[0]} checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
