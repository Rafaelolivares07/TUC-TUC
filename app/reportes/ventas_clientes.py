"""reportes/ventas_clientes.py — Ventas agrupadas por cliente con puestos y participación."""

NOMBRE    = 'Ventas por Clientes'
ID        = 'ventas_clientes'
CATEGORIA = 'Ventas'

FILTROS_UI = [
    {'id': 'empresa', 'label': 'Empresa',  'tipo': 'select', 'requerido': False},
    {'id': 'desde',   'label': 'Desde',    'tipo': 'date',   'requerido': True},
    {'id': 'hasta',   'label': 'Hasta',    'tipo': 'date',   'requerido': True},
]


def tablas_requeridas(filtros):
    empresa = str(filtros.get('empresa', '') or '').strip().upper()
    desde   = filtros.get('desde', '')
    hasta   = filtros.get('hasta', '')
    filtros_pf = {}
    if empresa:
        filtros_pf['EMPRESA'] = empresa
    if desde or hasta:
        filtros_pf['FECHAHORA'] = {}
        if desde: filtros_pf['FECHAHORA']['desde'] = desde
        if hasta: filtros_pf['FECHAHORA']['hasta'] = hasta
    return [
        {
            'tabla': 'PROD_FACT1',
            'campos': ['CLIENTE', 'CANTIDAD', 'PRECIO', 'DESCUENTO', 'POR_IVA', 'EMPRESA', 'FECHAHORA'],
            'filtros': filtros_pf,
        },
        {
            'tabla': 'TERCEROS',
            'campos': ['COD_TER', 'NOMBRE', 'IDENTIFICA'],
            'filtros': {},
        },
    ]


def calcular(datos, filtros):
    terceros = {
        str(r.get('COD_TER', '') or '').strip(): {
            'nombre':         str(r.get('NOMBRE', '') or '').strip(),
            'identificacion': str(r.get('IDENTIFICA', '') or '').strip(),
        }
        for r in datos.get('TERCEROS', [])
        if str(r.get('COD_TER', '') or '').strip()
    }

    clientes = {}
    for r in datos.get('PROD_FACT1', []):
        cod = str(r.get('CLIENTE', '') or '').strip()
        if not cod or cod == '0':
            continue
        cantidad = float(r.get('CANTIDAD', 0) or 0)
        precio   = float(r.get('PRECIO',   0) or 0)
        descto   = float(r.get('DESCUENTO',0) or 0)
        por_iva  = float(r.get('POR_IVA',  0) or 0)
        subtotal = cantidad * precio - descto
        iva      = cantidad * precio * (por_iva / 100)
        if cod not in clientes:
            clientes[cod] = {'cantidad': 0.0, 'subtotal': 0.0, 'iva': 0.0}
        clientes[cod]['cantidad'] += cantidad
        clientes[cod]['subtotal'] += subtotal
        clientes[cod]['iva']      += iva

    rows = []
    for cod, d in clientes.items():
        ter = terceros.get(cod, {})
        rows.append({
            'codigo':         cod,
            'identificacion': ter.get('identificacion', ''),
            'nombre':         ter.get('nombre', cod),
            'cantidad':       round(d['cantidad'], 2),
            'subtotal':       round(d['subtotal'], 2),
            'iva':            round(d['iva'], 2),
        })
    rows = [r for r in rows if r['nombre']]

    total_cant = sum(r['cantidad'] for r in rows) or 1
    total_val  = sum(r['subtotal'] for r in rows) or 1

    rows.sort(key=lambda r: r['cantidad'], reverse=True)
    for i, r in enumerate(rows):
        r['puesto_cant'] = i + 1
        r['por_cant']    = round(r['cantidad'] / total_cant * 100, 2)

    puesto_val = {r['codigo']: i+1
                  for i, r in enumerate(sorted(rows, key=lambda r: r['subtotal'], reverse=True))}
    for r in rows:
        r['puesto_val'] = puesto_val[r['codigo']]
        r['por_val']    = round(r['subtotal'] / total_val * 100, 2)

    rows.sort(key=lambda r: r['nombre'])
    return rows
