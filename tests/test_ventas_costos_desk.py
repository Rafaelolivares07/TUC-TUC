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

# 4. Horas opcionales (2026-11-22, pedido Rafa): el reporte acepta
# hora_desde/hora_hasta (HH:MM) sin volverse obligatorias. Vacias = dia
# completo, identico a hoy. Solo-hasta recorta el inicio, solo-desde el
# final; si desde > hasta se lee como ventana trasnoche (OR).
sys.path.insert(0, BASE)
from app.blueprints.inventarios import _query_reporte_ventas_costos, _validar_hora


class _FakeCur:
    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self):
        self.sql = ''
        self.params = ()

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = tuple(params)
        return _FakeCur()


def _corre(hd=None, hh=None):
    c = _FakeConn()
    _query_reporte_ventas_costos(c, 59, '2026-11-01', '2026-11-22',
                                 hora_desde=hd, hora_hasta=hh)
    return c


c0 = _corre()
check('sin horas: sql sin filtro hora', '::time' not in c0.sql)
check('sin horas: params intactos',
      list(c0.params) == [59, '2026-11-01', '2026-11-22', 59])

c1 = _corre(hd='11:00')
check('solo desde: cota inferior', '>= %s' in c1.sql and '11:00' in c1.params)
check('solo desde: un param mas', len(c1.params) == 5)

c2 = _corre(hh='15:00')
check('solo hasta: cota superior', '<= %s' in c2.sql and '15:00' in c2.params)
check('solo hasta: un param mas', len(c2.params) == 5)

c3 = _corre(hd='11:00', hh='15:00')
check('ambas: ventana diurna', '>= %s' in c3.sql and '<= %s' in c3.sql
      and 'OR COALESCE' not in c3.sql)

c4 = _corre(hd='18:00', hh='02:00')
check('trasnoche: OR', 'OR COALESCE' in c4.sql
      and '18:00' in c4.params and '02:00' in c4.params)

check('valida: vacio es None', _validar_hora('') is None and _validar_hora(None) is None)
check('valida: formato ok', _validar_hora('07:30') == '07:30')
for _mala in ('25:00', '11:60', '11', 'once', '7:3x'):
    try:
        _validar_hora(_mala)
        check('valida: rechaza %r' % _mala, False)
    except ValueError:
        check('valida: rechaza %r' % _mala, True)

# 5. Filtros de hora en la plantilla (opcionales, cableados a las 3 consultas)
i_hd = html.find('vc-hora-desde')
i_hh = html.find('vc-hora-hasta')
check('inputs hora existen', i_hd > 0 and i_hh > 0)
check('inputs hora type=time',
      'type="time"' in html[max(0, i_hd - 120):i_hd + 40]
      and 'type="time"' in html[max(0, i_hh - 120):i_hh + 40])
check('inputs hora sin required',
      'required' not in html[max(0, i_hd - 120):i_hd + 200]
      and 'required' not in html[max(0, i_hh - 120):i_hh + 200])
check('labels hora', 'Hora desde' in html and 'Hora hasta' in html)
_ini = html.find('function vcHorasQS(')
_fin = html.find('return qs;', _ini) if _ini >= 0 else -1
_qs = html[_ini:_fin] if _ini >= 0 and _fin > _ini else ''
check('helper horas definido', bool(_qs))
check('helper lee ambos inputs', 'vc-hora-desde' in _qs and 'vc-hora-hasta' in _qs)
check('helper usado en reporte+pdf+detalle', html.count('vcHorasQS()') >= 4)

print('fails:', len(fails))
sys.exit(1 if fails else 0)
