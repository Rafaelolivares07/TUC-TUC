"""reportes/reg_ctas.py — REG_CTAS detallado: movimientos individuales con filtros cuenta/tercero/empresa/lapso."""

NOMBRE    = 'Movimientos REG_CTAS'
ID        = 'reg_ctas'
CATEGORIA = 'Contabilidad'

FILTROS_UI = [
    {'id': 'empresa', 'label': 'Empresa',  'tipo': 'select', 'requerido': False},
    {'id': 'cuenta',  'label': 'Cuenta',   'tipo': 'text',   'requerido': False},
    {'id': 'tercero', 'label': 'Tercero',  'tipo': 'text',   'requerido': False},
    {'id': 'desde',   'label': 'Desde',    'tipo': 'date',   'requerido': True},
    {'id': 'hasta',   'label': 'Hasta',    'tipo': 'date',   'requerido': True},
]


def tablas_requeridas(filtros):
    empresa = str(filtros.get('empresa', '') or '').strip().upper()
    desde   = filtros.get('desde', '')
    hasta   = filtros.get('hasta', '')
    cuenta  = str(filtros.get('cuenta',  '') or '').strip()
    tercero = str(filtros.get('tercero', '') or '').strip()

    def a_lapso(fecha_iso):
        return fecha_iso[:7].replace('-', '') + '01' if fecha_iso else ''

    filtros_rc = {}
    if empresa:
        filtros_rc['EMPRESA'] = empresa
    if cuenta:
        filtros_rc['CUENTA'] = cuenta
    if tercero:
        filtros_rc['TERCERO'] = tercero
    if desde or hasta:
        filtros_rc['LAPSO'] = {}
        if desde: filtros_rc['LAPSO']['desde'] = a_lapso(desde)
        if hasta: filtros_rc['LAPSO']['hasta'] = a_lapso(hasta)

    return [
        {
            'tabla':  'REG_CTAS',
            'campos': ['CONSECUTIV', 'FECHAHORA', 'LAPSO', 'TIPO_DOC', 'DOCUMENTO',
                       'CUENTA', 'TERCERO', 'DEBITO', 'CREDITO', 'DETALLE',
                       'ANULADO', 'EMPRESA'],
            'filtros': filtros_rc,
        },
        {
            'tabla':   'TERCEROS',
            'campos':  ['COD_TER', 'NOMBRE', 'IDENTIFICA'],
            'filtros': {},
        },
        {
            'tabla':   'TIPO_DOC',
            'campos':  ['TIPO', 'DESCRIPCION'],
            'filtros': {},
        },
    ]


def calcular(datos, filtros):
    terceros = {
        str(r.get('COD_TER', '') or '').strip(): {
            'nombre':         str(r.get('NOMBRE',     '') or '').strip(),
            'identificacion': str(r.get('IDENTIFICA', '') or '').strip(),
        }
        for r in datos.get('TERCEROS', [])
        if str(r.get('COD_TER', '') or '').strip()
    }

    tipos = {
        str(r.get('TIPO', '') or '').strip(): str(r.get('DESCRIPCION', '') or '').strip()
        for r in datos.get('TIPO_DOC', [])
        if str(r.get('TIPO', '') or '').strip()
    }

    rows = []
    for r in datos.get('REG_CTAS', []):
        cod_ter = str(r.get('TERCERO',   '') or '').strip()
        tipo    = str(r.get('TIPO_DOC',  '') or '').strip()
        cuenta  = str(r.get('CUENTA',    '') or '').strip()
        ter     = terceros.get(cod_ter, {})
        rows.append({
            'consecutivo': str(r.get('CONSECUTIV', '') or '').strip(),
            'fecha':       str(r.get('FECHAHORA',  '') or '')[:10],
            'lapso':       str(r.get('LAPSO',      '') or '').strip(),
            'tipo':        tipo,
            'tipo_nom':    tipos.get(tipo, ''),
            'documento':   str(r.get('DOCUMENTO',  '') or '').strip(),
            'cuenta':      cuenta,
            'nit':         ter.get('identificacion', ''),
            'tercero':     cod_ter,
            'tercero_nom': ter.get('nombre', ''),
            'debito':      round(float(r.get('DEBITO',  0) or 0), 2),
            'credito':     round(float(r.get('CREDITO', 0) or 0), 2),
            'detalle':     str(r.get('DETALLE',  '') or '').strip(),
            'anulado':     bool(r.get('ANULADO', False)),
            'empresa':     str(r.get('EMPRESA',  '') or '').strip(),
        })

    rows.sort(key=lambda r: (r['lapso'], r['fecha'], r['consecutivo']))
    return rows
