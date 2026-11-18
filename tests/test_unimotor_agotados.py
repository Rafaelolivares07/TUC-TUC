"""Regression: unimotor de agotados (contrato FINAL 2026-11-18).

Sin framework: asserts planos + exit code, solo stdlib. Uso:
  C:\\Tools\\Python313\\python.exe tests/test_unimotor_agotados.py
Pin estatico sobre inventarios.py + compras.py + templates (sin BD/DOM):
  - un solo motor decide (veredicto binario + sin_historia)
  - invocadores llaman y presentan, jamas deciden
  - muertos: fijo silencioso, piso 1.0, defecto, dias-con-stock,
    cuenta propia de pantalla, sync promos con escritura, huerfano
Regla: demanda = todas las salidas, ventana trunca, denominador
calendario, tendencia reacciona, params solo de BD.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / 'app' / 'blueprints' / 'inventarios.py'
COMP = ROOT / 'app' / 'blueprints' / 'compras.py'
TPL = ROOT / 'templates' / 'inventario_admin.html'
CAT = ROOT / 'templates' / 'catalogo_productos.html'
ENT = ROOT / 'templates' / 'entradas.html'

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


inv = INV.read_text(encoding='utf-8')
comp = COMP.read_text(encoding='utf-8')
tpl = TPL.read_text(encoding='utf-8')


def cuerpo(src, inicio, siguiente):
    a = src.find(inicio)
    b = src.find(siguiente, a + 1) if a >= 0 else -1
    return src[a:b] if a >= 0 and b > a else ''


eng = cuerpo(inv, 'def _motor_evaluar(', '\ndef _verificar_alerta_stock_agotado(')
hook = cuerpo(inv, 'def _verificar_alerta_stock_agotado(', '\ndef _es_producto_preparado(')
upd = cuerpo(inv, 'def api_update_product_max_stock(', '\n@bp.route(')

check('motor existe', 'def _motor_evaluar(' in inv)
check('params demanda de BD', 'def _motor_params_demanda(' in inv
      and "'inventario_dias_historial'" in inv)
check('veredictos binarios', "'agotado'" in eng and "'sano'" in eng
      and "'sin_historia'" in eng)
check('motor ignora fijo', 'stock_minimo' not in eng)
check('muere piso 1.0', 'if stock_min_calculado <= 0.0001:' not in inv)
check('muere config vieja', 'def _obtener_config_stock_minimo' not in inv)
check('hook invoca motor',
      'v = _motor_evaluar(conn, negocio_id, producto_id, st_nuevo)' in hook)
vest = [l for l in inv.split('\n') if 'dias_defecto' in l]
check('defecto solo vestigio ensambles', len(vest) == 2
      and any("_param_int('dias_defecto'" in l for l in vest)
      and any("'dias_defecto': dias_defecto" in l for l in vest),
      str(len(vest)))
check('toggle muerto backend', 'usar_dias_con_stock' not in inv)
check('muere sync promos', 'candidatos_sync' not in inv
      and 'sincronizar_agotados_promo' not in inv)
check('pantalla invoca motor',
      'v = _motor_evaluar(conn, negocio_id, p_id, stock_actual)' in inv)
check('despacho invoca motor', '_vp = _motor_evaluar(' in inv)
check('endpoint dias sin fijo', 'stock_minimo' not in upd)
check('muere st_min', 'st_min' not in inv)
check('sin p_stock_min_fijo', 'p_stock_min_fijo' not in inv
      and 'stock_minimo_fijo' not in inv)
check('params nuevos api', "'inventario_growth_window'" in inv
      and "'inventario_max_growth'" in inv and "'inventario_min_growth'" in inv)

check('huerfano fuera',
      'def _estado_rotacion' not in comp
      and 'def construir_propuesta_rotacion' not in comp
      and 'def _mejor_cotizacion' not in comp
      and 'def _confianza' not in comp
      and 'def _alertas' not in comp
      and 'def _listar_cotizaciones' not in comp
      and 'def _tercero_por_nombre' not in comp
      and 'def _date_or_default' not in comp
      and 'def _decimal' not in comp
      and 'def _float' not in comp
      and 'def _txt' not in comp
      and 'def _ceil' not in comp)
check('vivo intacto', 'def api_ordenes_compra_crear' in comp
      and 'def _asegurar_tablas' in comp and "bp = Blueprint('compras'" in comp)

check('autosave historial',
      'onchange="guardarParametroNegocio(\'inventario_dias_historial\'' in tpl)
check('autosave growth-win',
      'onchange="guardarParametroNegocio(\'inventario_growth_window\'' in tpl)
check('autosave max-growth',
      'onchange="guardarParametroNegocio(\'inventario_max_growth\'' in tpl)
check('autosave min-growth',
      'onchange="guardarParametroNegocio(\'inventario_min_growth\'' in tpl)
check('toggle dias fuera', 'cfg-compras-usar-dias-con-stock' not in tpl)
check('label sin escritores', "getElementById('formula-dias-label')" not in tpl)
check('defecto compras fuera', 'cfg-compras-dias-defecto' not in tpl)
check('fijo modal fuera',
      'mp-stock-minimo' not in tpl
      and 'mp-stock-minimo' not in CAT.read_text(encoding='utf-8')
      and 'mp-stock-minimo' not in ENT.read_text(encoding='utf-8'))
check('loader params nuevos', "getElementById('cfg-compras-dias-historial')" in tpl
      and 'p.dias_historial' in tpl)

for p in (INV, COMP, TPL, CAT, ENT):
    raw = p.read_bytes()
    check(f'CRLF {p.name}',
          raw.count(b'\n') == raw.count(b'\r\n') and raw.count(b'\r\n') > 0)

print(f'--- {len(fails)} fallos ---')
sys.exit(1 if fails else 0)
