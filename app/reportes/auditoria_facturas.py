"""reportes/auditoria_facturas.py — Auditoría de Facturas y Asientos Contables con Detección de Faltantes e Inconsistencias."""

import datetime
import io
import re

NOMBRE    = 'Auditoría de Documentos de Interfase'
ID        = 'auditoria_facturas'
CATEGORIA = 'Contabilidad'

FILTROS_UI = [
    {'id': 'empresa',     'label': 'Empresa',           'tipo': 'select', 'requerido': False},
    {'id': 'tipo_doc',    'label': 'Tipo de Documento', 'tipo': 'select', 'requerido': False},
    {'id': 'desde',       'label': 'Fecha Desde',       'tipo': 'date',   'requerido': False},
    {'id': 'hasta',       'label': 'Fecha Hasta',       'tipo': 'date',   'requerido': False},
    {'id': 'desde_num',   'label': 'Consecutivo Desde', 'tipo': 'text',   'requerido': False},
    {'id': 'hasta_num',   'label': 'Consecutivo Hasta', 'tipo': 'text',   'requerido': False},
    {'id': 'solo_inconsistencias', 'label': 'Solo Inconsistencias', 'tipo': 'checkbox', 'requerido': False},
]

EXCEL_COLS = [
    ('documento',        'Factura / Documento'),
    ('tipo',             'Tipo Doc'),
    ('fecha',            'Fecha'),
    ('lapso',            'Lapso'),
    ('tercero',          'NIT / Identificación'),
    ('tercero_nom',      'Nombre Tercero / Cliente'),
    ('total_debito',     'Total Débito'),
    ('total_credito',    'Total Crédito'),
    ('diferencia',       'Diferencia'),
    ('estado',           'Estado Auditoría'),
    ('inconsistencias_s','Detalle Inconsistencias'),
    ('num_lineas',       'Nº Asientos'),
    ('empresa',          'Empresa'),
]


def _fmt_lapso(v):
    s = str(v or '').strip().replace('-', '')
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _fmt_id(v):
    if v is None or v == '':
        return ''
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


def _extraer_numero(s):
    """Extrae el número entero de un documento tipo 'FV1045' o '1045'."""
    s_clean = str(s or '').strip()
    match = re.search(r'\d+', s_clean)
    if match:
        try:
            return int(match.group())
        except Exception:
            return None
    return None


def tablas_requeridas(filtros):
    if filtros.get('catalogos_init'):
        return [
            {'tabla': 'EMPRESAS', 'campos': ['COD_EMP', 'NOM_EMP', 'NIT'], 'filtros': {}},
            {'tabla': 'TIPO_DOC', 'campos': ['CODIGO', 'NOMBRE'], 'filtros': {}},
            {'tabla': 'CUENTAS',  'campos': ['CODIGO', 'NOMBRE', 'TIPO'], 'filtros': {}},
            {'tabla': 'allegra_config', 'campos': ['EMPRESA', 'TIP_DOC', 'NUM_INICIO'], 'filtros': {}},
            {'tabla': 'alegra_tiposdoc', 'campos': ['EMPRESA', 'TIP_ADMIN', 'TIP_ALEGRA'], 'filtros': {}},
        ]

    empresa  = str(filtros.get('empresa', '') or '').strip().upper()
    tipo_doc = str(filtros.get('tipo_doc', '') or '').strip().upper()
    desde    = filtros.get('desde', '')
    hasta    = filtros.get('hasta', '')

    filtros_rc = {}
    if empresa:
        filtros_rc['EMPRESA'] = empresa
    if tipo_doc:
        filtros_rc['TIPO'] = tipo_doc
    elif empresa == '02':
        filtros_rc['TIPO'] = '030'
    elif empresa == 'LP':
        filtros_rc['TIPO'] = '029'

    if desde or hasta:
        filtros_rc['FECHAHORA'] = {}
        if desde: filtros_rc['FECHAHORA']['desde'] = desde
        if hasta: filtros_rc['FECHAHORA']['hasta'] = hasta
        filtros_rc['LAPSO'] = {}
        if desde: filtros_rc['LAPSO']['desde'] = desde
        if hasta: filtros_rc['LAPSO']['hasta'] = hasta

    return [
        {
            'tabla':  'REG_CTAS',
            'campos': ['CONSECUTIV', 'FECHAHORA', 'LAPSO', 'TIPO', 'DOCUMENTO',
                       'CUENTA', 'TERCERO', 'TOT_DEB', 'TOT_CRE', 'VALOR',
                       'DETALLE_CT', 'ANULADO', 'EMPRESA'],
            'filtros': filtros_rc,
        },
        {
            'tabla':   'TIPO_DOC',
            'campos':  ['CODIGO', 'NOMBRE'],
            'filtros': {},
        },
        {
            'tabla':   'CUENTAS',
            'campos':  ['CODIGO', 'NOMBRE', 'TIPO'],
            'filtros': {},
        },
        {
            'tabla':   'allegra_config',
            'campos':  ['EMPRESA', 'TIP_DOC', 'NUM_INICIO'],
            'filtros': {},
        },
        {
            'tabla':   'alegra_tiposdoc',
            'campos':  ['EMPRESA', 'TIP_ADMIN', 'TIP_ALEGRA'],
            'filtros': {},
        },
    ]


def calcular(datos, filtros):
    # 1. Mapeo de catálogos
    cuentas_map = {}
    for r in datos.get('CUENTAS', []):
        c = str(r.get('CODIGO', '') or '').strip()
        if c:
            cuentas_map[c] = str(r.get('NOMBRE', '') or '').strip()

    tipos_map = {}
    for r in datos.get('TIPO_DOC', []):
        t = str(r.get('CODIGO', '') or '').strip().upper()
        if t:
            tipos_map[t] = str(r.get('NOMBRE', '') or '').strip()

    # Mapeo de Terceros resueltos por lote
    terceros_map = dict(datos.get('TERCEROS_MAP', {}) or {})
    if 'TERCEROS' in datos and isinstance(datos['TERCEROS'], list):
        for t in datos['TERCEROS']:
            c = str(t.get('COD_TER', '') or '').strip()
            if c:
                terceros_map[c] = {
                    'nombre': str(t.get('NOMBRE', '') or '').strip(),
                    'nit': str(t.get('IDENTIFICA') or t.get('NIT') or '').strip()
                }

    # Tipos configurados en interfases
    interfaz_tipos = set()
    for r in datos.get('allegra_config', []):
        t = str(r.get('TIP_DOC', '') or '').strip().upper()
        if t:
            interfaz_tipos.add(t)
    for r in datos.get('alegra_tiposdoc', []):
        t = str(r.get('TIP_ADMIN', '') or '').strip().upper()
        if t:
            interfaz_tipos.add(t)
    if not interfaz_tipos:
        interfaz_tipos = {'030', '029'}

    # 2. Agrupación por Documento/Factura
    raw_rc = datos.get('REG_CTAS', [])
    tipo_filtro_exacto = str(filtros.get('tipo_doc', '') or '').strip().upper()
    grupos = {}

    for r in raw_rc:
        emp = str(r.get('EMPRESA', '') or '').strip().upper()
        tipo = str(r.get('TIPO', '') or '').strip().upper()
        
        if tipo_filtro_exacto:
            if tipo != tipo_filtro_exacto:
                continue
        else:
            if tipo not in interfaz_tipos:
                continue

        doc = str(r.get('DOCUMENTO', '') or '').strip()
        consec = _fmt_id(r.get('CONSECUTIV'))

        # Llave única por documento dentro de empresa y tipo
        clave_doc = doc if doc else f"CONSEC-{consec}"
        grupo_key = (emp, tipo, clave_doc)

        if grupo_key not in grupos:
            grupos[grupo_key] = {
                'empresa':   emp,
                'tipo':      tipo,
                'tipo_nom':  tipos_map.get(tipo, tipo),
                'documento': clave_doc,
                'consecutivo_reg': consec,
                'asientos':  [],
            }

        detalle = str(r.get('DETALLE_CT', '') or '').strip()
        cod_ter = _fmt_id(r.get('TERCERO'))
        ter_info = terceros_map.get(cod_ter, {}) if cod_ter else {}
        nom_ter = ter_info.get('nombre') or (f"Tercero {cod_ter}" if cod_ter else '—')
        nit_ter = ter_info.get('nit') or cod_ter

        cuenta_cod = str(r.get('CUENTA', '') or '').strip()
        cuenta_nom = cuentas_map.get(cuenta_cod, '')

        deb = float(r.get('TOT_DEB', 0) or 0)
        cre = float(r.get('TOT_CRE', 0) or 0)
        anulado = bool(r.get('ANULADO', False))
        fec = r.get('FECHAHORA')
        lapso = _fmt_lapso(r.get('LAPSO'))

        fecha_str = ''
        if fec:
            if isinstance(fec, datetime.datetime):
                fecha_str = fec.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(fec, str):
                fecha_str = fec[:19].replace('T', ' ')

        asiento = {
            'consecutivo': consec,
            'cuenta':      cuenta_cod,
            'cuenta_nom':  cuenta_nom,
            'tercero':     cod_ter,
            'tercero_nom': nom_ter,
            'nit':         nit_ter,
            'debito':      round(deb, 2),
            'credito':     round(cre, 2),
            'detalle':     detalle,
            'anulado':     anulado,
            'fecha':       fecha_str,
            'lapso':       lapso,
        }
        grupos[grupo_key]['asientos'].append(asiento)

    # 3. Análisis de Auditoría por Factura
    facturas = []
    numeros_encontrados = {}  # { (emp, tipo): [num, ...] }

    for (emp, tipo, doc), g in grupos.items():
        asientos = g['asientos']
        total_deb = round(sum(a['debito'] for a in asientos), 2)
        total_cre = round(sum(a['credito'] for a in asientos), 2)
        diferencia = round(total_deb - total_cre, 2)
        esta_cuadrada = abs(diferencia) < 0.01

        terceros_distintos = {}
        for a in asientos:
            if a['tercero']:
                terceros_distintos[a['tercero']] = a['tercero_nom'] or a['tercero']

        lapsos_distintos = {a['lapso'] for a in asientos if a['lapso']}
        fechas_distintas = {a['fecha'][:10] for a in asientos if a['fecha']}
        anulados_count = sum(1 for a in asientos if a['anulado'])
        es_anulada = anulados_count > 0 and (anulados_count == len(asientos))

        # Diagnóstico de inconsistencias
        inconsistencias = []
        if not esta_cuadrada and not es_anulada:
            inconsistencias.append(f"Descuadre Contable: Débito (${total_deb:,.2f}) != Crédito (${total_cre:,.2f}) — Dif: ${diferencia:,.2f}")

        if len(terceros_distintos) > 1:
            ter_list_str = ', '.join(f"{k} ({v})" for k, v in list(terceros_distintos.items())[:3])
            inconsistencias.append(f"Terceros Heterogéneos: La factura contiene asientos con distintos terceros: {ter_list_str}")

        if len(lapsos_distintos) > 1:
            inconsistencias.append(f"Lapsos Discordantes: Asientos con diferentes lapsos: {', '.join(sorted(lapsos_distintos))}")

        if len(asientos) == 1 and not es_anulada:
            inconsistencias.append("Asiento Incompleto: La factura tiene una sola línea contable (falta contrapartida)")

        # Determinar estado
        if es_anulada:
            estado = 'ANULADA'
        elif not esta_cuadrada:
            estado = 'DESCUADRADA'
        elif len(terceros_distintos) > 1:
            estado = 'TERCERO_MULTIPLE'
        elif len(lapsos_distintos) > 1:
            estado = 'FECHA_DISCORDANTE'
        else:
            estado = 'CUADRADA'

        # Tercero y fecha representativos
        primer_asiento = asientos[0] if asientos else {}
        ter_rep = primer_asiento.get('tercero', '')
        ter_nom_rep = primer_asiento.get('tercero_nom', '')
        ter_nit_rep = primer_asiento.get('nit', '')
        fecha_rep = primer_asiento.get('fecha', '')
        lapso_rep = primer_asiento.get('lapso', '')

        # Guardar número numérico para análisis de faltantes
        num_val = _extraer_numero(doc)
        if num_val is not None:
            serie_key = (emp, tipo)
            if serie_key not in numeros_encontrados:
                numeros_encontrados[serie_key] = []
            numeros_encontrados[serie_key].append(num_val)

        facturas.append({
            'empresa':           emp,
            'tipo':              tipo,
            'tipo_nom':          g['tipo_nom'],
            'documento':         doc,
            'num_val':           num_val,
            'fecha':             fecha_rep,
            'lapso':             lapso_rep,
            'tercero':           ter_nit_rep or ter_rep,
            'tercero_cod':       ter_rep,
            'tercero_nom':       ter_nom_rep,
            'total_debito':      total_deb,
            'total_credito':     total_cre,
            'diferencia':        diferencia,
            'esta_cuadrada':     esta_cuadrada,
            'estado':            estado,
            'inconsistencias':   inconsistencias,
            'inconsistencias_s': ' | '.join(inconsistencias),
            'num_lineas':        len(asientos),
            'es_faltante':       False,
            'asientos':          asientos,
        })

    # 4. Detección de Huecos / Consecutivos Faltantes
    desde_num_filtro = _extraer_numero(filtros.get('desde_num'))
    hasta_num_filtro = _extraer_numero(filtros.get('hasta_num'))

    faltantes_insertados = []
    for serie_key, nums in numeros_encontrados.items():
        if not nums:
            continue
        emp_s, tipo_s = serie_key
        tipo_nom_s = tipos_map.get(tipo_s, tipo_s)
        nums_set = set(nums)

        min_n = desde_num_filtro if desde_num_filtro is not None else min(nums)
        max_n = hasta_num_filtro if hasta_num_filtro is not None else max(nums)

        # Si el rango es razonable (< 20,000 números para evitar desbordar memoria)
        if 0 <= (max_n - min_n) <= 20000:
            for n in range(min_n, max_n + 1):
                if n not in nums_set:
                    faltantes_insertados.append({
                        'empresa':           emp_s,
                        'tipo':              tipo_s,
                        'tipo_nom':          tipo_nom_s,
                        'documento':         str(n),
                        'num_val':           n,
                        'fecha':             '',
                        'lapso':             '',
                        'tercero':           '',
                        'tercero_cod':       '',
                        'tercero_nom':       '(No registrado en REG_CTAS)',
                        'total_debito':      0.0,
                        'total_credito':     0.0,
                        'diferencia':        0.0,
                        'esta_cuadrada':     False,
                        'estado':            'FALTANTE',
                        'inconsistencias':   ['Consecutivo Faltante: No existe registro contable para este número correlativo'],
                        'inconsistencias_s': 'Consecutivo Faltante: No existe registro contable para este número correlativo',
                        'num_lineas':        0,
                        'es_faltante':       True,
                        'asientos':          [],
                    })

    todas_facturas = facturas + faltantes_insertados

    # 5. Filtrado por número de consecutivo si se especificó
    if desde_num_filtro is not None:
        todas_facturas = [f for f in todas_facturas if f['num_val'] is None or f['num_val'] >= desde_num_filtro]
    if hasta_num_filtro is not None:
        todas_facturas = [f for f in todas_facturas if f['num_val'] is None or f['num_val'] <= hasta_num_filtro]

    # Filtrar solo inconsistencias si se pidió
    solo_inc = filtros.get('solo_inconsistencias')
    if solo_inc and str(solo_inc).lower() in ('true', '1', 'on', 'yes'):
        todas_facturas = [f for f in todas_facturas if f['estado'] != 'CUADRADA']

    # Ordenar por número de documento / fecha
    todas_facturas.sort(key=lambda f: (
        f['empresa'],
        f['tipo'],
        f['num_val'] if f['num_val'] is not None else 999999999,
        f['documento']
    ))

    return todas_facturas


def generar_excel(rows, filtros, fuente, cliente_id):
    """Genera archivo Excel formateado profesionalmente con resumen de auditoría y detalle de asientos."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Auditoría Facturas"
    ws.views.sheetView[0].showGridLines = True

    # Paleta de colores
    NAVY_FILL   = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    GRAY_FILL   = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    RED_FILL    = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    ORANGE_FILL = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
    GREEN_FILL  = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    YELLOW_FILL = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")

    BORDER_THIN = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Título y Metadata
    ws.merge_cells('A1:L1')
    ws['A1'] = "AUDITORÍA DE FACTURAS Y MOVIMIENTOS CONTABLES"
    ws['A1'].font = Font(name='Calibri', size=16, bold=True, color='1E3A8A')
    ws['A1'].alignment = Alignment(vertical='center')

    subtitulo = f"Generado: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | Fuente: {fuente.upper()} ({cliente_id or 'Local'})"
    ws.merge_cells('A2:L2')
    ws['A2'] = subtitulo
    ws['A2'].font = Font(name='Calibri', size=10, italic=True, color='64748B')

    # Métricas Resumen
    total_fac   = len(rows)
    cuadradas   = sum(1 for r in rows if r['estado'] == 'CUADRADA')
    descuadre   = sum(1 for r in rows if r['estado'] == 'DESCUADRADA')
    faltantes   = sum(1 for r in rows if r['estado'] == 'FALTANTE')
    otros_inc   = sum(1 for r in rows if r['estado'] in ('TERCERO_MULTIPLE', 'FECHA_DISCORDANTE'))

    ws['A4'] = "Total Facturas:"; ws['B4'] = total_fac; ws['A4'].font = Font(bold=True)
    ws['D4'] = "Cuadradas:";      ws['E4'] = cuadradas; ws['D4'].font = Font(bold=True, color='16A34A')
    ws['G4'] = "Descuadradas:";  ws['H4'] = descuadre; ws['G4'].font = Font(bold=True, color='DC2626')
    ws['J4'] = "Faltantes:";     ws['K4'] = faltantes; ws['J4'].font = Font(bold=True, color='D97706')

    # Encabezados
    headers = [
        "Factura", "Tipo", "Fecha", "Lapso", "NIT / Cédula", "Cliente / Tercero",
        "Total Débito", "Total Crédito", "Diferencia", "Estado", "Diagnóstico / Inconsistencias", "Asientos"
    ]
    row_num = 6
    for col_num, h in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=col_num, value=h)
        cell.font = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
        cell.fill = NAVY_FILL
        cell.alignment = Alignment(horizontal='center' if col_num in (1,2,3,4,10,12) else 'left', vertical='center')

    # Filas de Datos
    row_num = 7
    for f in rows:
        st = f['estado']
        fill_color = None
        if st == 'DESCUADRADA':
            fill_color = RED_FILL
        elif st == 'FALTANTE':
            fill_color = ORANGE_FILL
        elif st in ('TERCERO_MULTIPLE', 'FECHA_DISCORDANTE'):
            fill_color = YELLOW_FILL
        elif st == 'CUADRADA':
            fill_color = GREEN_FILL

        ws.cell(row=row_num, column=1, value=f['documento']).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=2, value=f['tipo']).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=3, value=f['fecha']).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=4, value=f['lapso']).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=5, value=f['tercero']).alignment = Alignment(horizontal='left')
        ws.cell(row=row_num, column=6, value=f['tercero_nom']).alignment = Alignment(horizontal='left')
        
        c_deb = ws.cell(row=row_num, column=7, value=f['total_debito'])
        c_deb.number_format = '"$"#,##0.00'
        c_cre = ws.cell(row=row_num, column=8, value=f['total_credito'])
        c_cre.number_format = '"$"#,##0.00'
        c_dif = ws.cell(row=row_num, column=9, value=f['diferencia'])
        c_dif.number_format = '"$"#,##0.00'
        
        c_st = ws.cell(row=row_num, column=10, value=st)
        c_st.alignment = Alignment(horizontal='center')
        if fill_color:
            c_st.fill = fill_color
            c_st.font = Font(bold=True)

        ws.cell(row=row_num, column=11, value=f['inconsistencias_s']).alignment = Alignment(horizontal='left')
        ws.cell(row=row_num, column=12, value=f['num_lineas']).alignment = Alignment(horizontal='center')

        for c in range(1, 13):
            ws.cell(row=row_num, column=c).border = BORDER_THIN
            ws.cell(row=row_num, column=c).font = Font(name='Calibri', size=9)
            if fill_color and c in (1, 9, 10):
                ws.cell(row=row_num, column=c).fill = fill_color

        row_num += 1

    # Ajuste automático de anchos de columna
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            if cell.row < 4:
                continue
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 11), 55)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
