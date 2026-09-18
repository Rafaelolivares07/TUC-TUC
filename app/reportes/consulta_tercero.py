"""reportes/consulta_tercero.py -- REG_CTAS agrupado por cuenta para un tercero dado."""

NOMBRE    = 'Consulta por Tercero'
ID        = 'consulta_tercero'
CATEGORIA = 'Contabilidad'

EXCEL_COLS = [
    ('cuenta',     'Cuenta'),
    ('cuenta_nom', 'Nombre Cuenta'),
    ('tot_deb',    'Débito'),
    ('tot_cre',    'Crédito'),
    ('neto',       'Neto'),
]

FILTROS_UI = [
    {'id': 'tercero', 'label': 'Tercero',   'tipo': 'text',        'requerido': True},
    {'id': 'empresa', 'label': 'Empresa',   'tipo': 'select',      'requerido': False},
    {'id': 'desde',   'label': 'Desde',     'tipo': 'date',        'requerido': True},
    {'id': 'hasta',   'label': 'Hasta',     'tipo': 'date',        'requerido': True},
    {'id': 'tipos',   'label': 'Tipos doc', 'tipo': 'multiselect', 'requerido': False},
]


def tablas_requeridas(filtros):
    if filtros.get('tipos_init'):
        return [{'tabla': 'TIPO_DOC', 'campos': ['CODIGO', 'NOMBRE'], 'filtros': {}}]

    if filtros.get('terceros_buscar'):
        return [{'tabla': 'TERCEROS', 'campos': ['COD_TER', 'NOMBRE', 'IDENTIFICA', 'NIT'], 'filtros': {}}]

    empresa = str(filtros.get('empresa', '') or '').strip().upper()
    desde   = filtros.get('desde', '')
    hasta   = filtros.get('hasta', '')

    def a_lapso(f):
        return f.replace('-', '') if f else ''

    filtros_rc = {}
    if empresa:
        filtros_rc['EMPRESA'] = empresa
    if desde or hasta:
        filtros_rc['LAPSO'] = {}
        if desde: filtros_rc['LAPSO']['desde'] = a_lapso(desde)
        if hasta: filtros_rc['LAPSO']['hasta'] = a_lapso(hasta)

    return [
        {
            'tabla':   'REG_CTAS',
            'campos':  ['TERCERO', 'TOT_DEB', 'TOT_CRE', 'EMPRESA', 'LAPSO', 'CUENTA', 'TIPO'],
            'filtros': filtros_rc,
        },
        {
            'tabla':   'TERCEROS',
            'campos':  ['COD_TER', 'NOMBRE', 'IDENTIFICA', 'NIT'],
            'filtros': {},
        },
        {
            'tabla':   'CUENTAS',
            'campos':  ['CODIGO', 'NOMBRE'],
            'filtros': {},
        },
    ]


def calcular(datos, filtros):
    if filtros.get('terceros_buscar'):
        q = str(filtros.get('q', '') or '').strip().upper()
        resultados = []
        for r in datos.get('TERCEROS', []):
            cod  = str(r.get('COD_TER',    '') or '').strip()
            nom  = str(r.get('NOMBRE',     '') or '').strip()
            idf  = str(r.get('IDENTIFICA', '') or '').strip()
            nit  = str(r.get('NIT',        '') or '').strip()
            if not cod or not nom:
                continue
            if q in nom.upper() or q in idf.upper() or q in nit.upper() or q in cod.upper():
                resultados.append({'cod_ter': cod, 'nombre': nom, 'nit': idf or nit})
            if len(resultados) >= 15:
                break
        resultados.sort(key=lambda x: x['nombre'])
        return resultados

    if filtros.get('tipos_init'):
        tipos = []
        for r in datos.get('TIPO_DOC', []):
            cod = str(r.get('CODIGO', '') or '').strip()
            nom = str(r.get('NOMBRE', '') or '').strip()
            if cod:
                tipos.append({'codigo': cod, 'nombre': nom or cod})
        tipos.sort(key=lambda x: x['codigo'])
        return tipos

    # ── Resolver tercero → conjunto de COD_TER internos ──────────────────────
    # El usuario puede ingresar: NIT, código interno, o fragmento de nombre.
    # TERCERO en REG_CTAS almacena el COD_TER (código numérico interno).
    busqueda = str(filtros.get('tercero', '') or '').strip().upper()

    tercero_rows = datos.get('TERCEROS', [])
    codigos_match = set()

    for r in tercero_rows:
        cod        = str(r.get('COD_TER',    '') or '').strip()
        nombre     = str(r.get('NOMBRE',     '') or '').strip()
        identifica = str(r.get('IDENTIFICA', '') or '').strip()
        nit        = str(r.get('NIT',        '') or '').strip()

        if not cod:
            continue

        # Coincidencia exacta por código interno, NIT o identificación
        if busqueda in (cod, nit.upper(), identifica.upper()):
            codigos_match.add(cod)
            continue

        # Coincidencia parcial por nombre (mínimo 3 chars para evitar falsos positivos)
        if len(busqueda) >= 3 and busqueda in nombre.upper():
            codigos_match.add(cod)

    # Si no encontró en TERCEROS, intentar como código directo (el usuario sabe el código)
    if not codigos_match and busqueda:
        codigos_match.add(busqueda)

    # ── Filtro por tipos de documento ─────────────────────────────────────────
    tipos_sel = filtros.get('tipos', [])
    if isinstance(tipos_sel, str):
        tipos_sel = [tipos_sel] if tipos_sel else []
    tipos_sel = {t.upper().strip() for t in tipos_sel if t}

    # ── Lookup nombres de cuenta ──────────────────────────────────────────────
    cuentas_nom = {
        str(r.get('CODIGO', '') or '').strip(): str(r.get('NOMBRE', '') or '').strip()
        for r in datos.get('CUENTAS', [])
        if str(r.get('CODIGO', '') or '').strip()
    }

    # ── Acumular débito/crédito por cuenta ───────────────────────────────────
    acum = {}
    for r in datos.get('REG_CTAS', []):
        cod_ter = str(r.get('TERCERO', '') or '').strip()
        if cod_ter not in codigos_match:
            continue

        if tipos_sel:
            tipo = str(r.get('TIPO', '') or '').strip().upper()
            if tipo not in tipos_sel:
                continue

        cuenta = str(r.get('CUENTA', '') or '').strip()
        if not cuenta:
            continue

        deb = float(r.get('TOT_DEB', 0) or 0)
        cre = float(r.get('TOT_CRE', 0) or 0)
        if cuenta not in acum:
            acum[cuenta] = {'tot_deb': 0.0, 'tot_cre': 0.0}
        acum[cuenta]['tot_deb'] += deb
        acum[cuenta]['tot_cre'] += cre

    rows = []
    for cuenta, d in acum.items():
        neto = d['tot_deb'] - d['tot_cre']
        rows.append({
            'cuenta':     cuenta,
            'cuenta_nom': cuentas_nom.get(cuenta, ''),
            'tot_deb':    round(d['tot_deb'], 2),
            'tot_cre':    round(d['tot_cre'], 2),
            'neto':       round(neto, 2),
        })

    rows.sort(key=lambda r: r['cuenta'])
    return rows


def generar_excel(rows, filtros, fuente, cliente_id):
    from reportes._excel_utils import generar_excel as _gen
    # Si el HTML envió el texto visible del campo tercero, usarlo en el encabezado
    filtros_display = dict(filtros)
    td = filtros_display.pop('tercero_display', '').strip()
    if td:
        filtros_display['tercero'] = td
    return _gen(NOMBRE, FILTROS_UI, EXCEL_COLS, rows, filtros_display, fuente, cliente_id)
