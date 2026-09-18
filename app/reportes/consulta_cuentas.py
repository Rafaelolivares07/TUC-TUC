"""reportes/consulta_cuentas.py — REG_CTAS agrupado por tercero con débito/crédito/neto."""

NOMBRE    = 'Consulta de Cuentas'
ID        = 'consulta_cuentas'
CATEGORIA = 'Contabilidad'

FILTROS_UI = [
    {'id': 'empresa', 'label': 'Empresa',  'tipo': 'select',  'requerido': False},
    {'id': 'cuenta',  'label': 'Cuenta',   'tipo': 'text',    'requerido': True},
    {'id': 'desde',   'label': 'Desde',    'tipo': 'date',    'requerido': True},
    {'id': 'hasta',   'label': 'Hasta',    'tipo': 'date',    'requerido': True},
]


def _fmt_id(v):
    if v is None or v == '':
        return ''
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


def tablas_requeridas(filtros):
    if filtros.get('catalogos_init'):
        return [
            {'tabla': 'EMPRESAS', 'campos': ['COD_EMP', 'NOM_EMP', 'NIT'], 'filtros': {}},
            {'tabla': 'CUENTAS', 'campos': ['CODIGO', 'NOMBRE'], 'filtros': {}},
        ]

    empresa = str(filtros.get('empresa', '') or '').strip().upper()
    desde   = filtros.get('desde', '')
    hasta   = filtros.get('hasta', '')
    cuenta  = str(filtros.get('cuenta',  '') or '').strip()

    def a_lapso(fecha_iso):
        return fecha_iso.replace('-', '') if fecha_iso else ''

    filtros_rc = {}
    if empresa:
        filtros_rc['EMPRESA'] = empresa
    if cuenta:
        filtros_rc['CUENTA'] = cuenta
    if desde or hasta:
        filtros_rc['LAPSO'] = {}
        if desde: filtros_rc['LAPSO']['desde'] = a_lapso(desde)
        if hasta: filtros_rc['LAPSO']['hasta'] = a_lapso(hasta)

    return [
        {
            'tabla':   'REG_CTAS',
            'campos':  ['TERCERO', 'TOT_DEB', 'TOT_CRE', 'EMPRESA', 'LAPSO', 'CUENTA'],
            'filtros': filtros_rc,
        },
        {
            'tabla':   'TERCEROS',
            'campos':  ['COD_TER', 'NOMBRE', 'IDENTIFICA'],
            'filtros': {},
        },
    ]


def calcular(datos, filtros):
    if filtros.get('catalogos_init'):
        emps = []
        for r in datos.get('EMPRESAS', []):
            cod = str(r.get('COD_EMP', '') or '').strip()
            if cod:
                emps.append({
                    'codigo': cod,
                    'nombre': str(r.get('NOM_EMP', '') or '').strip(),
                    'nit': str(r.get('NIT', '') or '').strip()
                })
        ctas = []
        for r in datos.get('CUENTAS', []):
            cod = str(r.get('CODIGO', '') or '').strip()
            if cod:
                ctas.append({
                    'codigo': cod,
                    'nombre': str(r.get('NOMBRE', '') or '').strip()
                })
        ctas.sort(key=lambda x: x['codigo'])
        return {'empresas': emps, 'cuentas': ctas}

    terceros = {}
    for r in datos.get('TERCEROS', []):
        raw_cod = r.get('COD_TER')
        k1 = _fmt_id(raw_cod)
        info = {
            'nombre':         str(r.get('NOMBRE',     '') or '').strip(),
            'identificacion': str(r.get('IDENTIFICA', '') or '').strip(),
        }
        if k1:
            terceros[k1] = info
        try:
            k2 = str(int(float(raw_cod)))
            terceros[k2] = info
        except Exception:
            pass

    acum = {}
    for r in datos.get('REG_CTAS', []):
        raw_t = r.get('TERCERO')
        cod = _fmt_id(raw_t)
        if not cod:
            continue
        deb = float(r.get('TOT_DEB', 0) or 0)
        cre = float(r.get('TOT_CRE', 0) or 0)
        if cod not in acum:
            acum[cod] = {'tot_deb': 0.0, 'tot_cre': 0.0, 'raw': raw_t}
        acum[cod]['tot_deb'] += deb
        acum[cod]['tot_cre'] += cre

    rows = []
    for cod, d in acum.items():
        ter = terceros.get(cod)
        if not ter and 'raw' in d:
            try:
                ter = terceros.get(str(int(float(d['raw']))), {})
            except Exception:
                ter = {}
        if not ter:
            ter = {}

        neto = d['tot_deb'] - d['tot_cre']
        rows.append({
            'codigo':         cod,
            'identificacion': ter.get('identificacion', ''),
            'nombre':         ter.get('nombre', cod),
            'tot_deb':        round(d['tot_deb'], 2),
            'tot_cre':        round(d['tot_cre'], 2),
            'neto':           round(neto, 2),
        })

    rows = [r for r in rows if r['nombre']]
    rows.sort(key=lambda r: r['nombre'])
    return rows
