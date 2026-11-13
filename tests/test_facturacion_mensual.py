# -*- coding: utf-8 -*-
"""Facturacion mensual recurrente Lopez (03/11).
Motor dia 1 + salto 5-15 + imagen + mensaje Don Jesus.
Uso:  python tests/test_facturacion_mensual.py   (desde raiz TucTucV2)
"""
import os
import sys
from datetime import datetime

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from app.blueprints import facturacion_mensual as fm  # noqa: E402

BOG = fm.BOGOTA

# mes vencido
check('vencido nov->oct', fm._mes_vencido(datetime(2026, 11, 3, 10, tzinfo=BOG)) == (10, 2026))
check('vencido ene->dic-prev', fm._mes_vencido(datetime(2026, 1, 1, 6, tzinfo=BOG)) == (12, 2025))
check('vencido mar->feb', fm._mes_vencido(datetime(2026, 3, 15, 20, tzinfo=BOG)) == (2, 2026))

# saludo dias/tardes
check('saludo manana', fm._saludo(8) == 'buenos días')
check('saludo 11 manana', fm._saludo(11) == 'buenos días')
check('saludo 12 tardes', fm._saludo(12) == 'buenas tardes')
check('saludo noche tardes', fm._saludo(23) == 'buenas tardes')

# mensaje whatsapp
m = fm._mensaje_whatsapp('https://admin.tuc-tuc.co/f/ABC', datetime(2026, 11, 3, 10, tzinfo=BOG))
check('msg Don Jesus', 'Don Jesus' in m, m)
check('msg dias', 'buenos días' in m, m)
check('msg Octubre 2026', 'Octubre 2026' in m, m)
check('msg trae link', 'https://admin.tuc-tuc.co/f/ABC' in m, m)
mt = fm._mensaje_whatsapp('L', datetime(2026, 11, 3, 15, tzinfo=BOG))
check('msg tardes pm', 'muy buenas tardes' in mt, mt)

# wa url + telefono
check('tel wa solo digitos', fm._telefono_wa() == '19142747117', fm._telefono_wa())
check('url wa directa', fm._url_wa('hola').startswith('https://wa.me/19142747117?text='))

# formato numero
check('formato 500000', fm._formato_numero(500000) == '$500.000', fm._formato_numero(500000))
check('formato 0', fm._formato_numero(0) == '$0')
check('formato 50000', fm._formato_numero(50000) == '$50.000')

# salto
check('rango salto 5-15', fm.SALTO_MIN == 5 and fm.SALTO_MAX == 15)
SRC = open(os.path.join(ROOT, 'app', 'blueprints', 'facturacion_mensual.py'), encoding='utf-8').read()
check('salto usa constantes', 'random.randint(SALTO_MIN, SALTO_MAX)' in SRC)
check('candado FOR UPDATE', 'FOR UPDATE' in SRC)
check('token asegura columnas', SRC.count('_asegurar_columnas(conn)') >= 2,
      str(SRC.count('_asegurar_columnas(conn)')))
check('arranque 1768', 'CONTADOR_ARRANQUE = 1768' in SRC)

# columnas _asegurar
for col in ('terceros ADD COLUMN IF NOT EXISTS documento',
            'terceros ADD COLUMN IF NOT EXISTS contacto',
            'pedidos ADD COLUMN IF NOT EXISTS numero',
            'pedidos ADD COLUMN IF NOT EXISTS tipo_documento_id',
            'pedidos ADD COLUMN IF NOT EXISTS token_publico'):
    check('col ' + col.split()[-1], col in SRC)

# rutas + scheduler + registro
check('ruta generar', "/api/facturacion-mensual/generar" in SRC)
check('ruta estado', "/api/facturacion-mensual/estado" in SRC)
check('ruta /f/ publica', "'/f/<token>'" in SRC)
check('ruta imagen png', 'imagen.png' in SRC)
SCH = open(os.path.join(ROOT, 'app', 'scheduler.py'), encoding='utf-8').read()
check('job scheduler', "id='facturacion_mensual'" in SCH)
INI = open(os.path.join(ROOT, 'app', '__init__.py'), encoding='utf-8').read()
check('blueprint registrado', 'facturacion_mensual_bp' in INI and INI.count('facturacion_mensual_bp') >= 2)
TPL = open(os.path.join(ROOT, 'templates', 'factura_mensual.html'), encoding='utf-8').read()
check('og:image factura', 'og:image' in TPL and 'imagen.png' in SRC)

# render real PNG + muestra para Rafa
muestra = {'numero': 1777, 'total': 500000, 'mes': 'Octubre', 'anio': 2026,
           'fecha': fm._ahora_bogota().isoformat(), 'token': 'muestra'}
check('hora Bogota explicita', 'ahora.replace(tzinfo=None)' in SRC)
png = fm._render_imagen(muestra)
check('png magic', png[:8] == b'\x89PNG\r\n\x1a\n')
check('png tamano util', len(png) > 10000, str(len(png)))
from PIL import Image as _Im
import io as _io
img = _Im.open(_io.BytesIO(png))
check('png ancho 720', img.size[0] == 720, str(img.size))
check('png legible alto', img.size[1] > 600, str(img.size))
check('logo real (no respaldo)', img.getpixel((360, 100)) != (178, 34, 34))
try:
    with open(os.path.join(ROOT, 'factura_muestra.png'), 'wb') as fh:
        fh.write(png)
    print('muestra: factura_muestra.png')
except OSError:
    with open(os.path.join(ROOT, 'factura_muestra_v2.png'), 'wb') as fh:
        fh.write(png)
    print('muestra: factura_muestra_v2.png (v1 bloqueada)')

# festivos USA + corrimiento dia habil
from datetime import date as _date
F26 = fm._festivos_usa(2026)
check('accion gracias 26/11', _date(2026, 11, 26) in F26)
check('navidad 25/12', _date(2026, 12, 25) in F26)
check('4 julio sab->vie 3', _date(2026, 7, 3) in F26)
check('memorial 25/05', _date(2026, 5, 25) in F26)
check('mlk 19/01', _date(2026, 1, 19) in F26)
check('trabajo 07/09', _date(2026, 9, 7) in F26)
check('nov26 dom->lun2', fm._fecha_generacion_mes(2026, 11) == _date(2026, 11, 2))
check('ene26 fiesta->vie2', fm._fecha_generacion_mes(2026, 1) == _date(2026, 1, 2))
check('jul26 miercoles-1', fm._fecha_generacion_mes(2026, 7) == _date(2026, 7, 1))
check('logo existe', os.path.exists(os.path.join(ROOT, 'static', 'facturacion_logo_administrator.png')))

# ajuste sin traslape nombre/valor
from PIL import ImageDraw as _Dr
_dd = _Dr.Draw(_Im.new('RGB', (720, 100), 'white'))
_vv = fm._formato_numero(500000)
_xv = 720 - 40 - _dd.textlength(_vv, font=fm._fuente(30, bold=True))
_fn, _tx = fm._ajustar_texto(_dd, 'ALOJAMIENTO DE DATOS', 150, _xv - 20)
check('ajuste sin traslape', _dd.textlength(_tx, font=_fn) <= (_xv - 20) - 150 + 0.5)
check('ajuste conserva texto', _tx == 'ALOJAMIENTO DE DATOS')
_fn2, _tx2 = fm._ajustar_texto(_dd, 'ALOJAMIENTO DE DATOS', 150, 300)
check('ajuste angosto cabe', _dd.textlength(_tx2, font=_fn2) <= 150 + 0.5)

print(f'--- {total[0] - len(fails)}/{total[0]} ---')
sys.exit(1 if fails else 0)
