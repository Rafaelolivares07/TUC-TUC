"""reportes/reg_ctas.py -- REG_CTAS detallado: movimientos individuales con filtros cuenta/tercero/empresa/lapso."""

NOMBRE    = 'Movimientos REG_CTAS'
ID        = 'reg_ctas'
CATEGORIA = 'Contabilidad'

EXCEL_COLS = [
    ('consecutivo', '#'),
    ('fecha',       'Fecha'),
    ('lapso',       'Lapso'),
    ('tipo',        'Tipo'),
    ('tipo_nom',    'Descripción Tipo'),
    ('documento',   'Documento'),
    ('cuenta',      'Cuenta'),
    ('cuenta_nom',  'Nombre Cuenta'),
    ('nit',         'NIT'),
    ('tercero_nom', 'Tercero'),
    ('debito',      'Débito'),
    ('credito',     'Crédito'),
    ('saldo_acum',  'Saldo'),
    ('detalle',     'Detalle'),
    ('anulado',     'Anulado'),
    ('empresa',     'Empresa'),
]

FILTROS_UI = [
    {'id': 'empresa', 'label': 'Empresa',  'tipo': 'select', 'requerido': False},
    {'id': 'cuenta',  'label': 'Cuenta',   'tipo': 'text',   'requerido': False},
    {'id': 'tercero', 'label': 'Tercero',  'tipo': 'text',   'requerido': False},
    {'id': 'desde',   'label': 'Desde',    'tipo': 'date',   'requerido': True},
    {'id': 'hasta',   'label': 'Hasta',    'tipo': 'date',   'requerido': True},
]


def _fmt_lapso(v):
    s = str(v or '').strip().replace('-', '')
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _fmt_id(v):
    """Convierte campo numérico (float) a string limpio. TERCERO, USUARIO, etc. son tipo N en DBF."""
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

    if filtros.get('cuenta_buscar'):
        return [{'tabla': 'CUENTAS', 'campos': ['CODIGO', 'NOMBRE'], 'filtros': {}}]

    if filtros.get('terceros_buscar'):
        return [{'tabla': 'TERCEROS', 'campos': ['COD_TER', 'NOMBRE', 'IDENTIFICA', 'NIT'], 'filtros': {}}]

    empresa = str(filtros.get('empresa', '') or '').strip().upper()
    desde   = filtros.get('desde', '')
    hasta   = filtros.get('hasta', '')
    cuenta  = str(filtros.get('cuenta',  '') or '').strip()
    tercero = str(filtros.get('tercero', '') or '').strip()

    def a_lapso(f):
        return f.replace('-', '') if f else ''

    filtros_rc = {}
    if empresa:
        filtros_rc['EMPRESA'] = empresa
    if cuenta:
        filtros_rc['CUENTA'] = cuenta
    # TERCERO nunca va al pre-filtro DBF (N-field: falla con NITs con guión)
    if desde or hasta:
        filtros_rc['LAPSO'] = {}
        if desde: filtros_rc['LAPSO']['desde'] = a_lapso(desde)
        if hasta: filtros_rc['LAPSO']['hasta'] = a_lapso(hasta)

    tablas = [
        {
            'tabla':  'REG_CTAS',
            'campos': ['CONSECUTIV', 'FECHAHORA', 'LAPSO', 'TIPO', 'DOCUMENTO',
                       'CUENTA', 'TERCERO', 'TOT_DEB', 'TOT_CRE', 'VALOR',
                       'DETALLE_CT', 'ANULADO', 'EMPRESA'],
            'filtros': filtros_rc,
        },
    ]

    # Para saldo_inicial: cargar REG_CTAS anterior a 'desde'
    if desde and filtros.get('incluir_saldo_inicial', True):
        filtros_si = {}
        if empresa:
            filtros_si['EMPRESA'] = empresa
        if cuenta:
            filtros_si['CUENTA'] = cuenta
        lapso_hasta = a_lapso(desde)
        # Calcular día anterior para excluir el día 'desde'
        try:
            y, m, d = int(lapso_hasta[:4]), int(lapso_hasta[4:6]), int(lapso_hasta[6:8])
            import datetime
            ant = datetime.date(y, m, d) - datetime.timedelta(days=1)
            lapso_hasta = ant.strftime('%Y%m%d')
        except Exception:
            pass
        filtros_si['LAPSO'] = {'hasta': lapso_hasta}
        tablas.append({
            'tabla':   'REG_CTAS',
            'alias':   'REG_CTAS_SALDO',
            'campos':  ['CUENTA', 'LAPSO', 'TOT_DEB', 'TOT_CRE', 'EMPRESA', 'TERCERO'],
            'filtros': filtros_si,
        })

    tablas.extend([
        {
            'tabla':   'TERCEROS',
            'campos':  ['COD_TER', 'NOMBRE', 'IDENTIFICA'],
            'filtros': {},
        },
        {
            'tabla':   'CUENTAS',
            'campos':  ['CODIGO', 'NOMBRE'],
            'filtros': {},
        },
        {
            'tabla':   'TIPO_DOC',
            'campos':  ['CODIGO', 'NOMBRE'],
            'filtros': {},
        },
    ])
    return tablas


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

    if filtros.get('cuenta_buscar'):
        q = str(filtros.get('q', '') or '').strip().upper()
        resultados = []
        for r in datos.get('CUENTAS', []):
            cod = str(r.get('CODIGO', '') or '').strip()
            nom = str(r.get('NOMBRE', '') or '').strip()
            if not cod:
                continue
            if q in cod.upper() or q in nom.upper():
                resultados.append({'codigo': cod, 'nombre': nom})
            if len(resultados) >= 15:
                break
        resultados.sort(key=lambda x: x['codigo'])
        return resultados

    if filtros.get('terceros_buscar'):
        q = str(filtros.get('q', '') or '').strip().upper()
        resultados = []
        for r in datos.get('TERCEROS', []):
            cod  = _fmt_id(r.get('COD_TER', ''))
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

    # ── Resolver filtro de tercero → conjunto de COD_TER ─────────────────────
    busqueda_ter = str(filtros.get('tercero', '') or '').strip().upper()
    codigos_match = None  # None = sin filtro (muestra todo)
    if busqueda_ter:
        codigos_match = set()
        for r in datos.get('TERCEROS', []):
            cod        = _fmt_id(r.get('COD_TER', ''))
            nombre     = str(r.get('NOMBRE',     '') or '').strip().upper()
            identifica = str(r.get('IDENTIFICA', '') or '').strip()
            nit        = str(r.get('NIT',        '') or '').strip()
            if not cod:
                continue
            if busqueda_ter in (cod, nit.upper(), identifica.upper()):
                codigos_match.add(cod)
                continue
            if len(busqueda_ter) >= 3 and busqueda_ter in nombre:
                codigos_match.add(cod)
        if not codigos_match:
            codigos_match.add(busqueda_ter)

    terceros = {}
    for r in datos.get('TERCEROS', []):
        raw_cod = r.get('COD_TER')
        k1 = _fmt_id(raw_cod)
        info = {
            'nombre':         str(r.get('NOMBRE',     '') or '').strip(),
            'identificacion': str(r.get('IDENTIFICA', '') or r.get('NIT', '') or '').strip(),
        }
        if k1:
            terceros[k1] = info
        try:
            k2 = str(int(float(raw_cod)))
            terceros[k2] = info
        except Exception:
            pass

    cuentas_nom = {
        str(r.get('CODIGO', '') or '').strip(): str(r.get('NOMBRE', '') or '').strip()
        for r in datos.get('CUENTAS', [])
        if str(r.get('CODIGO', '') or '').strip()
    }

    tipos = {}
    for r in datos.get('TIPO_DOC', []):
        cod = str(r.get('CODIGO', '') or '').strip()
        nom = str(r.get('NOMBRE', '') or '').strip()
        if cod:
            tipos[cod] = nom
            tipos[cod.zfill(3)] = nom
            tipos[cod.lstrip('0')] = nom

    rows = []
    for r in datos.get('REG_CTAS', []):
        raw_t = r.get('TERCERO')
        cod_ter = _fmt_id(raw_t)
        if codigos_match is not None and cod_ter not in codigos_match:
            try:
                if str(int(float(raw_t))) not in codigos_match:
                    continue
            except Exception:
                continue
        tipo    = str(r.get('TIPO', '') or '').strip()
        cuenta  = str(r.get('CUENTA', '') or '').strip()
        ter     = terceros.get(cod_ter)
        if not ter:
            try:
                ter = terceros.get(str(int(float(raw_t))), {})
            except Exception:
                ter = {}
        if not ter:
            ter = {}
        
        tipo_display = tipos.get(tipo) or tipos.get(tipo.zfill(3)) or tipos.get(tipo.lstrip('0')) or tipo
        
        rows.append({
            'consecutivo': str(r.get('CONSECUTIV', '') or '').strip(),
            'fecha':       str(r.get('FECHAHORA',  '') or '')[:10],
            'lapso':       _fmt_lapso(r.get('LAPSO', '')),
            'tipo':        tipo,
            'tipo_nom':    tipo_display,
            'documento':   str(r.get('DOCUMENTO',  '') or '').strip(),
            'cuenta':      cuenta,
            'cuenta_nom':  cuentas_nom.get(cuenta, ''),
            'nit':         ter.get('identificacion', ''),
            'tercero_nom': ter.get('nombre', ''),
            'debito':      round(float(r.get('TOT_DEB', 0) or 0), 2),
            'credito':     round(float(r.get('TOT_CRE', 0) or 0), 2),
            'detalle':     str(r.get('DETALLE_CT', '') or '').strip(),
            'anulado':     bool(r.get('ANULADO', False)),
            'empresa':     str(r.get('EMPRESA',  '') or '').strip(),
        })

    rows.sort(key=lambda r: (r['lapso'], r['fecha'], r['consecutivo']))

    saldo_inicial = 0.0
    for r in datos.get('REG_CTAS_SALDO', []):
        if codigos_match is not None:
            raw_t = r.get('TERCERO')
            cod_ter = _fmt_id(raw_t)
            if cod_ter not in codigos_match:
                try:
                    if str(int(float(raw_t))) not in codigos_match:
                        continue
                except Exception:
                    continue
        saldo_inicial += float(r.get('TOT_DEB', 0) or 0)
        saldo_inicial -= float(r.get('TOT_CRE', 0) or 0)
    saldo_inicial = round(saldo_inicial, 2)

    acumulado = saldo_inicial
    for r in rows:
        acumulado += (r['debito'] - r['credito'])
        r['saldo_acum'] = round(acumulado, 2)

    rows.insert(0, {'_saldo_inicial': saldo_inicial})
    return rows


def generar_excel(rows, filtros, fuente, cliente_id):
    data_rows = [r for r in rows if '_saldo_inicial' not in r]
    from reportes._excel_utils import generar_excel as _gen
    return _gen(NOMBRE, FILTROS_UI, EXCEL_COLS, data_rows, filtros, fuente, cliente_id)
