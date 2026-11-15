"""Regression: recosteo informa items afectados (padres) con boton por item.

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_recosteo_afectados.py
Backend (inspect, sin BD): helper _productos_padre + 'afectados' en
  recosteo/ejecutar, entrada (retro+modif) y cambiar-fecha.
Frontend (estatico): informe muestra afectados con boton Recostear en
  kardex/admin/entradas; save entrada y cambiar-fecha abren el modal.
Regla: recostear un insumo NO arrastra padres (sin cascada); se informa
  y cada padre se recostea puntual a pedido con un boton.
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.blueprints import inventarios as INV  # noqa: E402

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


# 1-2) helper padres
check('helper _productos_padre existe', hasattr(INV, '_productos_padre'))
SRC_H = inspect.getsource(INV._productos_padre) if hasattr(INV, '_productos_padre') else ''
check('helper lee tarjeta_estandar por componente',
      'tarjeta_estandar' in SRC_H and 'componente_id' in SRC_H)

# 3) ejecutar adjunta afectados por detalle
SRC_EJ = inspect.getsource(INV.api_ejecutar_recosteo)
check("ejecutar adjunta 'afectados'", "'afectados'" in SRC_EJ)

# 4-5) entrada retro+modif adjuntan afectados + metricas reales
SRC_REG = inspect.getsource(INV._registrar_entrada_inventario)
check('entrada adjunta afectados x2 (retro+modif)', SRC_REG.count("'afectados'") == 2)
check('entrada pasa metricas reales x2', SRC_REG.count("'costo_final': res_p.get('costo_final')") == 2)

# 6) cambiar-fecha retorna detalle con afectados
SRC_CF = inspect.getsource(INV.api_cambiar_fecha_documento_inventario)
check('cambiar-fecha retorna productos_detalle', "'productos_detalle'" in SRC_CF)

# 7-8) kardex: card + boton por item
KJ = (ROOT / 'templates' / 'partials' / 'kardex_js.html').read_text(encoding='utf-8')
check('kardex card muestra afectados', 'afectadosHtml' in KJ)
check('kardex boton recostea item', 'function recostearAfectado' in KJ
      and 'recosteo/ejecutar' in KJ.split('function recostearAfectado')[1][:800])

# 9) admin espejo
AD = (ROOT / 'templates' / 'inventario_admin.html').read_text(encoding='utf-8')
check('admin espejo muestra afectados', 'afectadosHtml' in AD and 'function recostearAfectado' in AD)

# 10-11) entradas: informe + save abre modal
EN = (ROOT / 'templates' / 'entradas.html').read_text(encoding='utf-8')
check('entradas tiene informe+boton',
      'function mostrarInformeRecosteo' in EN and 'function recostearAfectado' in EN)
check('entradas save abre modal con afectados',
      'mostrarInformeRecosteo({' in EN and 'recosteo_automatico' in EN)

# 12) cambiar-fecha abre modal
_i_cf = KJ.find('Documento actualizado. ${d.productos_recosteados}')
_seg_cf = KJ[_i_cf:_i_cf + 1200] if _i_cf > 0 else ''
check('cambiar-fecha abre modal', 'mostrarInformeRecosteo' in _seg_cf and 'd.productos_detalle' in _seg_cf)

# 13) mantenimiento retorna detalle con afectados
SRC_MT = inspect.getsource(INV.api_modificar_documento_mantenimiento)
check('mantenimiento retorna productos_detalle', "'productos_detalle'" in SRC_MT)

# 14-15) auditoria nueva
AUD = (ROOT / 'templates' / 'auditor_documentos.html').read_text(encoding='utf-8')
check('auditor nuevo tiene informe+boton',
      'function mostrarInformeRecosteo' in AUD and 'function recostearAfectado' in AUD)
check('auditor nuevo abre modal', 'mostrarInformeRecosteo({' in AUD and 'data.productos_detalle' in AUD)

# 16-17) mantenimiento viejo
MAN = (ROOT / 'templates' / 'mantenimiento_admin.html').read_text(encoding='utf-8')
check('mant viejo tiene informe+boton',
      'function mostrarInformeRecosteo' in MAN and 'function recostearAfectado' in MAN)
check('mant viejo abre modal', 'mostrarInformeRecosteo({' in MAN and 'data.productos_detalle' in MAN)

# 18-19) fisico modal completo
FIS = (ROOT / 'templates' / 'inventario_fisico.html').read_text(encoding='utf-8')
check('fisico tiene informe+boton',
      'function mostrarInformeRecosteo' in FIS and 'function recostearAfectado' in FIS)
check('fisico abre modal', 'mostrarInformeRecosteo({' in FIS)

N = 19
print(f'{N - len(fails)}/{N} checks, {len(fails)} fallos')
sys.exit(1 if fails else 0)
