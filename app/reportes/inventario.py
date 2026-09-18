"""
reportes/inventario.py — Reporte de rotación de inventario

Recibe datos crudos del DataLayer y calcula métricas de rotación,
tendencia y decisión por producto.

Tablas que necesita:
  - PRODUCTOS
  - PRODUCTO_INACTIVO
  - REG_PROD_SALDOS
  - PROD_FACT1  (ventas del período)
  - REG_PROD    (primera entrada por producto)
  - GRUPOS      (nombres de grupos)
"""

import datetime

NOMBRE    = 'Rotación de Inventario'
ID        = 'inventario'
CATEGORIA = 'Inventario'

FILTROS_UI = [
    {'id': 'empresa',   'label': 'Empresa',      'tipo': 'select',  'requerido': False},
    {'id': 'desde',     'label': 'Ventas desde', 'tipo': 'date',    'requerido': False},
    {'id': 'hasta',     'label': 'Ventas hasta', 'tipo': 'date',    'requerido': False},
    {'id': 'dias_min',  'label': 'Días stock mín','tipo': 'number', 'default': 30},
    {'id': 'dias_max',  'label': 'Días stock máx','tipo': 'number', 'default': 90},
]


def tablas_requeridas(filtros):
    """Retorna la lista de tablas que el DataLayer debe traer para este reporte."""
    empresa  = str(filtros.get('empresa', '') or '').strip().upper()
    desde    = filtros.get('desde', '')
    hasta    = filtros.get('hasta', '')

    filtro_emp_pf  = {'EMPRESA': empresa} if empresa else {}
    filtro_emp_rps = {}
    filtro_emp_pi  = {}
    filtro_emp_rp  = {}

    filtro_fecha_pf = {}
    if desde: filtro_fecha_pf['FECHAHORA'] = {}
    if desde: filtro_fecha_pf['FECHAHORA']['desde'] = desde
    if hasta:
        if 'FECHAHORA' not in filtro_fecha_pf: filtro_fecha_pf['FECHAHORA'] = {}
        filtro_fecha_pf['FECHAHORA']['hasta'] = hasta

    filtros_pf = {**filtro_emp_pf, **filtro_fecha_pf}

    return [
        {
            'tabla': 'PRODUCTOS',
            'campos': ['CODIGO', 'NOMBRE', 'GRUPO', 'UND_CONSUM'],
            'filtros': {}
        },
        {
            'tabla': 'PRODUCTO_INACTIVO',
            'campos': ['COD_EMP', 'COD_PRO'],
            'filtros': filtro_emp_pi
        },
        {
            'tabla': 'REG_PROD_SALDOS',
            'campos': ['COD_PRO', 'EMP', 'SAL_EXI', 'COS_UND_CO'],
            'filtros': filtro_emp_rps
        },
        {
            'tabla': 'PROD_FACT1',
            'campos': ['COD_PRO', 'FECHAHORA', 'CANTIDAD', 'EMPRESA'],
            'filtros': filtros_pf
        },
        {
            'tabla': 'REG_PROD',
            'campos': ['COD_PRO', 'LAP', 'CAN_ENT', 'EMP'],
            'filtros': filtro_emp_rp
        },
        {
            'tabla': 'GRUPOS',
            'campos': ['NUMERO', 'NOMBRE'],
            'filtros': {}
        },
    ]


def calcular(datos, filtros):
    """
    datos: dict retornado por DataLayer.leer()
    filtros: dict con empresa, desde, hasta, dias_min, dias_max
    retorna: list de filas con métricas
    """
    empresa  = str(filtros.get('empresa', '') or '').strip().upper()
    dias_min = int(filtros.get('dias_min', 30) or 30)
    dias_max = int(filtros.get('dias_max', 90) or 90)
    desde_s  = filtros.get('desde', '')
    hasta_s  = filtros.get('hasta', '')

    desde = datetime.date.fromisoformat(desde_s) if desde_s else None
    hasta = datetime.date.fromisoformat(hasta_s) if hasta_s else None
    longitud_periodo = (hasta - desde).days if (desde and hasta) else None
    now = datetime.datetime.now()

    # ── Grupos ────────────────────────────────────────────────────────────────
    grupos = {}
    for r in datos.get('GRUPOS', []):
        try:
            num = int(float(r.get('NUMERO', 0) or 0))
            grupos[num] = str(r.get('NOMBRE', '') or '').strip()
        except Exception:
            pass

    # ── Inactivos ─────────────────────────────────────────────────────────────
    inactivos = set()
    for r in datos.get('PRODUCTO_INACTIVO', []):
        cod_emp = str(r.get('COD_EMP', '') or '').strip().upper()
        if not empresa or cod_emp == empresa:
            cod = str(r.get('COD_PRO', '') or '').strip().upper()
            if cod:
                inactivos.add(cod)

    # ── Productos ─────────────────────────────────────────────────────────────
    prod_info = {}
    for r in datos.get('PRODUCTOS', []):
        cod = str(r.get('CODIGO', '') or '').strip().upper()
        if not cod:
            continue
        try:
            grp_int = int(float(r.get('GRUPO', 0) or 0))
        except Exception:
            grp_int = 0
        prod_info[cod] = {
            'nombre': str(r.get('NOMBRE', '') or '').strip(),
            'grupo':  grupos.get(grp_int, str(grp_int)),
            'und':    str(r.get('UND_CONSUM', '') or '').strip(),
        }

    # ── Saldos ────────────────────────────────────────────────────────────────
    saldos_emp  = {}
    costos_emp  = {}
    dup_conteo  = {}
    for r in datos.get('REG_PROD_SALDOS', []):
        cod = str(r.get('COD_PRO', '') or '').strip().upper()
        emp = str(r.get('EMP', '') or '').strip().upper()
        if not cod:
            continue
        if empresa and emp != empresa:
            continue
        sal = float(r.get('SAL_EXI', 0) or 0)
        cos = float(r.get('COS_UND_CO', 0) or 0)
        key = (cod, emp)
        if key in saldos_emp:
            dup_conteo[key] = dup_conteo.get(key, 1) + 1
        saldos_emp[key] = sal
        if 0 < cos < 1e9:
            costos_emp[key] = cos

    saldos_total     = {}
    valores_emp      = {}
    codigos_inconsis = set()
    empresas_por_cod = {}
    for (cod, emp), sal in saldos_emp.items():
        saldos_total[cod] = saldos_total.get(cod, 0.0) + sal
        empresas_por_cod.setdefault(cod, []).append(emp)
    for (cod, emp), cos in costos_emp.items():
        sal = saldos_emp.get((cod, emp), 0.0)
        valores_emp[cod] = valores_emp.get(cod, 0.0) + sal * cos
    for (cod, emp) in dup_conteo:
        codigos_inconsis.add(cod)
    codigos_multi_emp = {cod for cod, emps in empresas_por_cod.items() if len(emps) > 2}
    productos_empresa = set(saldos_total.keys())

    # ── Ventas ────────────────────────────────────────────────────────────────
    ventas_dict = {}
    for r in datos.get('PROD_FACT1', []):
        cod = str(r.get('COD_PRO', '') or '').strip().upper()
        if not cod:
            continue
        emp_r = str(r.get('EMPRESA', '') or '').strip().upper()
        if empresa and emp_r[:len(empresa)] != empresa:
            continue
        fecha_s = r.get('FECHAHORA')
        if not fecha_s:
            continue
        try:
            lap = datetime.datetime.fromisoformat(str(fecha_s))
        except Exception:
            continue
        can_sal = float(r.get('CANTIDAD', 0) or 0)
        ventas_dict.setdefault(cod, []).append((lap, can_sal))

    # ── Primera entrada ───────────────────────────────────────────────────────
    entradas_min = {}
    for r in datos.get('REG_PROD', []):
        cod = str(r.get('COD_PRO', '') or '').strip().upper()
        if not cod:
            continue
        emp_r = str(r.get('EMP', '') or '').strip().upper()
        if empresa and emp_r[:2] != empresa[:2]:
            continue
        can_ent = float(r.get('CAN_ENT', 0) or 0)
        if can_ent == 0:
            continue
        fecha_s = r.get('LAP')
        if not fecha_s:
            continue
        try:
            lap = datetime.datetime.fromisoformat(str(fecha_s))
        except Exception:
            continue
        if cod not in entradas_min or lap < entradas_min[cod]:
            entradas_min[cod] = lap

    # ── Métricas ──────────────────────────────────────────────────────────────
    todos_empresa   = productos_empresa & prod_info.keys()
    codigos_activos = set()
    for cod in todos_empresa:
        if cod in inactivos:
            if saldos_total.get(cod, 0.0) != 0.0:
                codigos_activos.add(cod)
        else:
            codigos_activos.add(cod)

    rows = []
    for cod in codigos_activos:
        info        = prod_info[cod]
        saldo       = round(saldos_total.get(cod, 0.0), 4)
        valor_saldo = round(valores_emp.get(cod, 0.0), 2)
        costo_und   = round(valor_saldo / saldo, 4) if saldo != 0 else 0.0

        primera_e = entradas_min.get(cod)
        v_list    = ventas_dict.get(cod, [])
        n_ventas  = len(v_list)

        if v_list:
            v_list_s      = sorted(v_list, key=lambda x: x[0], reverse=True)
            ultima_v      = v_list_s[0][0]
            total_vendido = sum(v[1] for v in v_list)
        else:
            v_list_s      = []
            ultima_v      = None
            total_vendido = 0.0

        dias_sin_venta = round((now - ultima_v).total_seconds() / 86400, 1) if ultima_v else None
        if longitud_periodo:
            dias_periodo = float(longitud_periodo)
        else:
            dias_periodo = round((now - primera_e).total_seconds() / 86400, 1) if primera_e else None

        prom_cant_venta = round(total_vendido / n_ventas, 4) if n_ventas > 0 else 0.0
        dias_prom       = round(dias_periodo / n_ventas, 1) if (dias_periodo and n_ventas > 0) else 0.0
        cant_prom_dia   = (prom_cant_venta / dias_prom) if dias_prom > 0 else 0.0

        dias_para_vender = None
        años_para_vender = None
        if prom_cant_venta > 0 and dias_prom > 0:
            dias_para_vender = round((saldo / prom_cant_venta) * dias_prom, 1)
            años_para_vender = round(dias_para_vender / 365, 2)

        stock_min = round(dias_min * cant_prom_dia)
        stock_max = round(dias_max * cant_prom_dia)
        saldo_int = round(saldo)

        if saldo < 0:
            decision = 'AJUSTAR INVENTARIO'
        elif n_ventas == 0 and saldo > 0 and primera_e:
            decision = f'{int(dias_periodo or 0)} DIAS DE NO VENDIDO'
        elif not primera_e and n_ventas == 0:
            decision = 'ITEM SIN REGISTROS'
        elif saldo >= 0 and cant_prom_dia > 0:
            if saldo_int < stock_min:
                decision = f'COMPRAR YA MINIMO.. {stock_min - saldo_int}'
            elif saldo_int > stock_max:
                decision = f'EXCESO INVENTARIO.. {saldo_int - stock_max}'
            elif saldo_int < stock_max:
                decision = f'COMPRAR MAXIMO.. {stock_max - saldo_int}'
            else:
                decision = 'STOCK OK'
        else:
            decision = ''

        tendencia = ''
        if n_ventas > 1 and total_vendido > 0:
            if n_ventas > 4:
                top_n, ref = max(1, int(n_ventas * 0.20)), 20.0
            elif n_ventas == 4:
                top_n, ref = 1, 25.0
            elif n_ventas == 3:
                top_n, ref = 1, 33.33
            else:
                top_n, ref = 1, 50.0
            cant_tend = sum(v[1] for v in v_list_s[:top_n])
            if cant_tend > 0:
                porcen = (cant_tend / total_vendido) * 100
                if porcen > ref + 0.9:
                    tendencia = f'SUBE.. {round(porcen - ref, 2)}%'
                elif (ref - porcen) > 0.9:
                    tendencia = f'BAJA.. {round(ref - porcen, 2)}%'
                else:
                    tendencia = 'ESTABLE'

        rows.append({
            'codigo':           cod,
            'nombre':           info['nombre'],
            'grupo':            info['grupo'],
            'und':              info['und'],
            'saldo':            saldo,
            'valor_saldo':      valor_saldo,
            'costo_und':        costo_und,
            'n_ventas':         n_ventas,
            'ultima_venta':     ultima_v.strftime('%Y-%m-%d') if ultima_v else '',
            'dias_sin_venta':   dias_sin_venta,
            'prom_cant_venta':  round(prom_cant_venta, 2),
            'dias_prom':        dias_prom,
            'dias_para_vender': dias_para_vender,
            'años_para_vender': años_para_vender,
            'stock_min':        stock_min,
            'stock_max':        stock_max,
            'tendencia':        tendencia,
            'decision':         decision,
            'inactivo':         cod in inactivos,
            'inconsistente':    cod in codigos_inconsis,
            'multi_emp':        cod in codigos_multi_emp,
        })

    rows.sort(key=lambda r: (-r['n_ventas'], r['dias_prom'] or 0))
    return rows
