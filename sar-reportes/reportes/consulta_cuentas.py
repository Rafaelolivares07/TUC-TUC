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


def tablas_requeridas(filtros):
    empresa = str(filtros.get('empresa', '') or '').strip().upper()
    desde   = filtros.get('desde', '')
    hasta   = filtros.get('hasta', '')
    cuenta  = str(filtros.get('cuenta',  '') or '').strip()

    # LAPSO en REG_CTAS es periodo contable YYYYMM01
    # Convertir fecha ISO a LAPSO: 2026-01-15 → 20260101
    def a_lapso(fecha_iso):
        return fecha_iso[:7].replace('-', '') + '01' if fecha_iso else ''

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
            'campos':  ['TERCERO', 'DEBITO', 'CREDITO', 'EMPRESA', 'LAPSO', 'CUENTA'],
            'filtros': filtros_rc,
        },
        {
            'tabla':   'TERCEROS',
            'campos':  ['COD_TER', 'NOMBRE', 'IDENTIFICA'],
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

    acum = {}
    for r in datos.get('REG_CTAS', []):
        cod = str(r.get('TERCERO', '') or '').strip()
        if not cod:
            continue
        deb = float(r.get('DEBITO',  0) or 0)
        cre = float(r.get('CREDITO', 0) or 0)
        if cod not in acum:
            acum[cod] = {'tot_deb': 0.0, 'tot_cre': 0.0}
        acum[cod]['tot_deb'] += deb
        acum[cod]['tot_cre'] += cre

    rows = []
    for cod, d in acum.items():
        ter  = terceros.get(cod, {})
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
