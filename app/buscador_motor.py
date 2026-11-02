# app/buscador_motor.py
# Motor omnibox unificado de rutas, pestanas y manuales de ayuda para TUC TUC V2

import os
import re
import unicodedata

def quitar_tildes(texto):
    if not texto:
        return ""
    texto_str = str(texto)
    return ''.join(c for c in unicodedata.normalize('NFD', texto_str) if unicodedata.category(c) != 'Mn').lower().strip()

def slugify(text):
    text = quitar_tildes(text)
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text).strip('-')

MANUALES_MAPA = {
    'contabilidad': ('contabilidad_usuario.md', 'Contabilidad', '📒'),
    'tienda': ('tienda_usuario.md', 'Tienda y Ventas', '🛒'),
    'restaurante': ('restaurante_usuario.md', 'Restaurante y Mesas', '🍽️'),
    'domotica': ('domotica_usuario.md', 'Domótica y Control', '💡'),
    'asistencia-remota': ('asistencia_remota_usuario.md', 'Asistencia Remota', '🖥️'),
    'alegra': ('alegra_usuario.md', 'Integración Alegra', '⚡'),
    'vendedor': ('vendedor_manual.md', 'Vendedor y Pedidos', '🛵'),
}

_CACHE_MANUALES = None

def _cargar_indice_manuales():
    global _CACHE_MANUALES
    if _CACHE_MANUALES is not None:
        return _CACHE_MANUALES

    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'manuales')
    if not os.path.exists(docs_dir):
        # Fallback si no existe en docs/manuales
        docs_dir = os.path.join(os.path.dirname(__file__), 'docs', 'manuales')
    
    secciones = []
    if not os.path.exists(docs_dir):
        _CACHE_MANUALES = []
        return _CACHE_MANUALES

    for slug, (archivo, nombre_manual, icono) in MANUALES_MAPA.items():
        filepath = os.path.join(docs_dir, archivo)
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            continue
            
        for i, line in enumerate(lines):
            m = re.match(r'^(#{1,3})\s+(.+)', line.strip())
            if not m:
                continue
            titulo = m.group(2).strip()
            if m.group(1) == '#' and 'Manual de Usuario' in titulo:
                continue
                
            anchor = slugify(titulo)
            preview = ''
            for j in range(i + 1, min(i + 6, len(lines))):
                next_l = lines[j].strip()
                if next_l and not next_l.startswith('#') and not next_l.startswith('---'):
                    clean_p = re.sub(r'[*_`\[\]]', '', next_l)
                    preview = clean_p[:130] + ('...' if len(clean_p) > 130 else '')
                    break
                    
            secciones.append({
                'titulo': titulo,
                'manual': nombre_manual,
                'icono': '📖',
                'resumen': preview or 'Ver detalle y pasos en el manual',
                'url': f'/docs/{slug}#{anchor}',
                'busqueda': f"{quitar_tildes(titulo)} {quitar_tildes(nombre_manual)} {quitar_tildes(preview)}"
            })

    _CACHE_MANUALES = secciones
    return _CACHE_MANUALES

def invalidar_cache_manuales():
    global _CACHE_MANUALES
    _CACHE_MANUALES = None

def _obtener_catalogo_base(negocio_id=None, slug=None):
    nid = str(negocio_id) if negocio_id else '1'
    s_slug = slug or 'mi-negocio'

    return [
        # ── PANTALLAS PRINCIPALES Y GLOBALES ──────────────────────────
        {
            'titulo': 'Inicio / Menú Principal',
            'modulo': 'General',
            'icono': '🏠',
            'url': '/inicio',
            'keywords': ['inicio', 'dashboard', 'panel', 'home', 'herramientas', 'menu principal', 'accesos']
        },
        {
            'titulo': 'Desk',
            'modulo': 'General',
            'icono': '🏢',
            'url': '/portal',
            'keywords': ['desk', 'portal', 'portada', 'buscar', 'buscador', 'lanzador']
        },
        {
            'titulo': 'Kardex',
            'modulo': 'Inventario',
            'icono': '\U0001F4E6',
            'url': f'https://{s_slug}.tuc-tuc.co/kardex' if slug else f'/inventario/{nid}/kardex',
            'keywords': ['kardex', 'movimientos', 'existencias', 'saldos', 'entradas', 'salidas']
        },
        {
            'titulo': 'Contabilidad — General',
            'modulo': 'Contabilidad',
            'icono': '📒',
            'url': f'/contabilidad/{nid}',
            'keywords': ['contabilidad', 'contable', 'finanzas', 'cuentas', 'asientos', 'balance']
        },
        {
            'titulo': 'Inventario — General',
            'modulo': 'Inventario',
            'icono': '📦',
            'url': f'/inventario/{nid}',
            'keywords': ['inventario', 'stock', 'almacen', 'existencias', 'bodega', 'productos']
        },
        {
            'titulo': 'Caja POS / Terminal de Ventas',
            'modulo': 'Ventas',
            'icono': '🛒',
            'url': f'/tienda/{s_slug}/caja' if slug else '/caja',
            'keywords': ['caja', 'pos', 'vender', 'cobrar', 'facturar', 'punto de venta', 'ticket', 'arqueo']
        },
        {
            'titulo': 'Mantenimiento de Negocio',
            'modulo': 'Mantenimiento',
            'icono': '🛠️',
            'url': f'/admin/mantenimiento/{nid}',
            'keywords': ['mantenimiento negocio', 'herramientas', 'reparar', 'depurar', 'auditoria', 'utilidades']
        },

        # ── PESTAÑAS CONTABILIDAD (EXHAUSTIVO 18/18) ───────────────────
        {
            'titulo': 'Plan Único de Cuentas (PUC)',
            'modulo': 'Contabilidad > Cuentas',
            'icono': '📋',
            'url': f'/contabilidad/{nid}?tab=puc',
            'keywords': ['puc', 'plan de cuentas', 'catalogo de cuentas', 'adoptar cuenta', 'codigo contable', 'subcuenta']
        },
        {
            'titulo': 'Tipos de Documento Contable',
            'modulo': 'Contabilidad > Configuración',
            'icono': '📄',
            'url': f'/contabilidad/{nid}?tab=tipos',
            'keywords': ['tipos documento', 'comprobante de ingreso', 'comprobante de egreso', 'facturas compra', 'nota contable', 'consecutivos']
        },
        {
            'titulo': 'Parametrización de Asientos',
            'modulo': 'Contabilidad > Reglas',
            'icono': '⚙️',
            'url': f'/contabilidad/{nid}?tab=params',
            'keywords': ['parametrizacion', 'moldes', 'reglas contables', 'debitos creditos', 'automatizacion asientos', 'partida doble', 'plantillas contables']
        },
        {
            'titulo': 'Métodos de Pago',
            'modulo': 'Contabilidad / Tienda',
            'icono': '💳',
            'url': f'/contabilidad/{nid}?tab=pago_metodos',
            'keywords': ['metodos de pago', 'formas de pago', 'tarjeta', 'nequi', 'daviplata', 'transferencia', 'efectivo', 'bancos']
        },
        {
            'titulo': 'Tesorería: Pagos, Desembolsos y Recaudos',
            'modulo': 'Contabilidad > Tesorería',
            'icono': '🏛️',
            'url': f'/tesoreria/{nid}',
            'keywords': ['tesoreria', 'tesorería', 'gastos', 'desembolsos', 'recaudos', 'caja menor', 'pagos', 'egresos', 'salidas de dinero', 'compras gastos', 'pagos proveedores']
        },
        {
            'titulo': 'Amortizaciones de Gastos y Préstamos',
            'modulo': 'Contabilidad > Finanzas',
            'icono': '⏳',
            'url': f'/contabilidad/{nid}?tab=amortizaciones',
            'keywords': ['amortizaciones', 'diferidos', 'prestamos', 'cuotas', 'seguros anticipados', 'tablas amortizacion']
        },
        {
            'titulo': 'Estado de Resultados (PyG)',
            'modulo': 'Contabilidad > Informes',
            'icono': '📊',
            'url': f'/contabilidad/{nid}?tab=estado_resultados',
            'keywords': ['estado de resultados', 'pyg', 'perdidas y ganancias', 'utilidad', 'ingresos vs gastos', 'rentabilidad', 'ejercicio']
        },
        {
            'titulo': 'Punto de Equilibrio',
            'modulo': 'Contabilidad > Informes',
            'icono': '🎯',
            'url': f'/contabilidad/{nid}?tab=punto_equilibrio',
            'keywords': ['punto de equilibrio', 'costos fijos', 'costos variables', 'margen de contribucion', 'ventas minimas', 'meta ventas']
        },
        {
            'titulo': 'Grupos de Inventario Contables',
            'modulo': 'Contabilidad > Grupos Inv.',
            'icono': '🗂️',
            'url': f'/contabilidad/{nid}?tab=grupos',
            'keywords': ['grupos inventario', 'grupos contables', 'cuentas inventario', 'clasificacion contable']
        },
        {
            'titulo': 'Comprobante Manual (Crear / Editar)',
            'modulo': 'Contabilidad > Asientos',
            'icono': '✏️',
            'url': f'/contabilidad/{nid}?tab=manual',
            'keywords': ['comprobante manual', 'nuevo comprobante', 'crear asiento', 'nota contable manual', 'asiento ajuste']
        },
        {
            'titulo': 'Comprobantes Generados (Histórico)',
            'modulo': 'Contabilidad > Asientos',
            'icono': '📚',
            'url': f'/contabilidad/{nid}?tab=comps',
            'keywords': ['comprobantes', 'asientos contables', 'historico contable', 'buscar comprobante', 'libro diario', 'movimientos contables']
        },
        {
            'titulo': 'Programaciones Contables Recurrentes',
            'modulo': 'Contabilidad > Automatización',
            'icono': '⏱️',
            'url': f'/contabilidad/{nid}?tab=progs',
            'keywords': ['programaciones', 'asientos programados', 'recurrentes', 'asientos automaticos', 'periodicos']
        },
        {
            'titulo': 'Consulta de Movimientos (Libro Mayor)',
            'modulo': 'Contabilidad > Informes',
            'icono': '🔍',
            'url': f'/contabilidad/{nid}?tab=consulta',
            'keywords': ['consulta movimientos', 'libro mayor', 'auxiliar contable', 'movimientos cuenta', 'extracto cuenta', 'tercero cuenta']
        },
        {
            'titulo': 'Balance y Cierre de Periodo',
            'modulo': 'Contabilidad > Cierre',
            'icono': '⚖️',
            'url': f'/contabilidad/{nid}?tab=balance',
            'keywords': ['balance', 'balance de prueba', 'cierre contable', 'cierre de mes', 'cierre anual', 'saldos cuentas']
        },
        {
            'titulo': 'Reclasificaciones Contables',
            'modulo': 'Contabilidad > Ajustes',
            'icono': '🔀',
            'url': f'/contabilidad/{nid}?tab=reclasificaciones',
            'keywords': ['reclasificaciones', 'reclasificar', 'corregir cuenta', 'mover asiento', 'ajuste contable']
        },
        {
            'titulo': 'Reporte de Saldos por Documento',
            'modulo': 'Contabilidad > Cartera',
            'icono': '📊',
            'url': f'/admin/saldos-documentos/{nid}',
            'keywords': ['saldos por documento', 'cartera', 'cuentas por pagar', 'cuentas por cobrar', 'facturas pendientes', 'cxp', 'cxc']
        },
        {
            'titulo': 'Conciliación de Cuentas y Bancos',
            'modulo': 'Contabilidad > Bancos',
            'icono': '⚖️',
            'url': f'/admin/conciliacion-disponible/{nid}',
            'keywords': ['conciliacion bancaria', 'conciliar disponible', 'extracto bancario', 'banco vs libros', 'saldo real', 'disponible']
        },

        # ── PESTAÑAS INVENTARIO (EXHAUSTIVO 17/17) ─────────────────────
        {
            'titulo': 'Catálogo de Productos e Insumos',
            'modulo': 'Inventario > Catálogo',
            'icono': '📋',
            'url': f'/inventario/{nid}?tab=productos',
            'keywords': ['productos', 'insumos', 'precios', 'categorias', 'codigo de barras', 'barcode', 'costo unitario', 'catalogo']
        },
        {
            'titulo': 'Tarjetas Estándar (Fórmulas y Recetas)',
            'modulo': 'Inventario > Producción',
            'icono': '🧾',
            'url': f'/inventario/{nid}?tab=tarjetas',
            'keywords': ['tarjetas estandar', 'recetas', 'formulas', 'ingredientes', 'porciones', 'costo receta', 'ficha tecnica']
        },
        {
            'titulo': 'Entradas de Almacén (Compras y Facturas)',
            'modulo': 'Inventario > Movimientos',
            'icono': '📥',
            'url': f'/entradas/{nid}',
            'keywords': ['entradas de almacen', 'compras', 'factura de compra', 'recepcion insumos', 'remision', 'ingreso stock']
        },
        {
            'titulo': 'Órdenes de Producción y Fabricación',
            'modulo': 'Inventario > Producción',
            'icono': '⚙️',
            'url': f'/produccion/{nid}',
            'keywords': ['produccion', 'orden de produccion', 'fabricacion', 'lote', 'transformacion', 'cocina']
        },
        {
            'titulo': 'Sugerencias de Compras (Reabastecimiento)',
            'modulo': 'Inventario > Compras',
            'icono': '🛒',
            'url': f'/inventario/{nid}?tab=compras_sugerencias',
            'keywords': ['sugerencias compras', 'reabastecer', 'punto de reorden', 'stock minimo', 'faltantes', 'pedir insumos', 'sugerir compras']
        },
        {
            'titulo': 'Cotizaciones de Proveedores',
            'modulo': 'Inventario > Compras',
            'icono': '📋',
            'url': f'/inventario/{nid}?tab=cotizaciones',
            'keywords': ['cotizaciones', 'cotizar', 'comparar proveedores', 'precios proveedor', 'solicitud de precio']
        },
        {
            'titulo': 'Traslados entre Bodegas o Sedes',
            'modulo': 'Inventario > Movimientos',
            'icono': '🔄',
            'url': f'/inventario/{nid}?tab=traslados',
            'keywords': ['traslados', 'mover stock', 'enviar a otra bodega', 'transferencia entre sedes', 'remision interna', 'traspasos']
        },
        {
            'titulo': 'Ensambles de Productos',
            'modulo': 'Inventario > Producción',
            'icono': '🧩',
            'url': f'/inventario/{nid}?tab=ensambles',
            'keywords': ['ensambles', 'combos', 'armar paquetes', 'desarmar', 'kits', 'ensamblar']
        },
        {
            'titulo': 'Ensambles Históricos',
            'modulo': 'Inventario > Producción',
            'icono': '📦',
            'url': f'/inventario/{nid}?tab=ensambles_historicos',
            'keywords': ['ensambles historicos', 'historico ensambles', 'registros ensambles', 'combos armados']
        },
                {
            'titulo': 'Ventas y Costos (Margen de Contribución)',
            'modulo': 'Comercial > Rentabilidad',
            'icono': '📊',
            'url': f'/ventas-costos/{nid}',
            'keywords': ['ventas costos', 'costo de ventas', 'margen de ganancia', 'utilidad bruta', 'rentabilidad productos', 'ventas/costos', 'costos']
        },
        {
            'titulo': 'Tesorería y Desembolsos de Inventario',
            'modulo': 'Inventario > Pagos',
            'icono': '💸',
            'url': f'/tesoreria/{nid}',
            'keywords': ['tesoreria', 'tesorería', 'desembolsos', 'gastos inventario', 'pagos proveedores', 'egresos inventario', 'pagos']
        },
        {
            'titulo': 'Estado de Resultados de Inventario',
            'modulo': 'Inventario > Informes',
            'icono': '📊',
            'url': f'/inventario/{nid}?tab=estado_resultados',
            'keywords': ['estado de resultados inventario', 'pyg inventario', 'utilidad inventario', 'ganancias']
        },
        {
            'titulo': 'Recosteo y Auditoría de Inventario',
            'modulo': 'Inventario > Auditoría',
            'icono': '🔍',
            'url': f'/inventario/{nid}?tab=recosteo',
            'keywords': ['recosteo', 'auditoria inventario', 'corregir costo promedio', 'descuadres de costo', 'recalcular costos']
        },
        {
            'titulo': 'Libro de Actas de Inventario',
            'modulo': 'Inventario > Actas',
            'icono': '📋',
            'url': f'/inventario/{nid}?tab=actas_inventario',
            'keywords': ['libro de actas', 'actas inventario', 'firmas actas', 'registro legal', 'acta conteo']
        },
        {
            'titulo': 'Inventario Físico (Conteo y Ajuste)',
            'modulo': 'Inventario > Ajustes',
            'icono': '📋',
            'url': f'/admin/inventario-fisico/{nid}',
            'keywords': ['inventario fisico', 'conteo fisico', 'toma de inventario', 'sobrantes faltantes', 'ajuste de inventario', 'conteo manual']
        },
        {
            'titulo': 'Inventario Físico Distribuido (Móvil / Tablet)',
            'modulo': 'Inventario > Ajustes',
            'icono': '🔄',
            'url': f'/admin/inventario-distribuido/{nid}',
            'keywords': ['inventario distribuido', 'conteo por zonas', 'conteo con celulares', 'varios contadores', 'tablet']
        },

        # ── HERRAMIENTAS DE MANTENIMIENTO ─────────────────────────────
        {
            'titulo': 'Auditoría de Documentos (Mantenimiento)',
            'modulo': 'Mantenimiento > Auditoría',
            'icono': '🔍',
            'url': f'/admin/mantenimiento/{nid}?tool=auditor-documentos',
            'keywords': ['auditoria documentos', 'buscar documento', 'anular documento', 'factura proveedor', 'factura venta', 'descuadres', 'cruces']
        },
        {
            'titulo': 'Unificación de Terceros (Mantenimiento)',
            'modulo': 'Mantenimiento > Terceros',
            'icono': '👥',
            'url': f'/admin/mantenimiento/{nid}?tool=unificar-terceros',
            'keywords': ['unificar terceros', 'fusionar clientes', 'proveedores duplicados', 'limpiar terceros', 'duplicados']
        },

        # ── HERRAMIENTAS ADMINISTRATIVAS GLOBALES ─────────────────────
        {
            'titulo': 'Catálogo Técnico de Pantallas',
            'modulo': 'Administración',
            'icono': '🖥️',
            'url': '/admin/pantallas-catalogo',
            'keywords': ['pantallas catalogo', 'modulos', 'endpoints', 'permisos', 'vistas']
        },
        {
            'titulo': 'Configuración de Negocio',
            'modulo': 'Administración',
            'icono': '⚙️',
            'url': '/admin/negocio-config',
            'keywords': ['configuracion negocio', 'logo', 'razon social', 'nit', 'datos empresa', 'horarios']
        },
        {
            'titulo': 'Gestión de Permisos y Colaboradores',
            'modulo': 'Administración',
            'icono': '👥',
            'url': '/admin/permisos',
            'keywords': ['permisos', 'usuarios', 'colaboradores', 'roles', 'accesos', 'empleados']
        },
        {
            'titulo': 'Mantenimiento del Sistema (Global)',
            'modulo': 'Administración',
            'icono': '🔧',
            'url': '/admin/mantenimiento',
            'keywords': ['mantenimiento', 'logs', 'git', 'version', 'diagnostico', 'base de datos']
        }
    ]

def buscar_omni(q, negocio_id=None, slug=None):
    q_limpio = (q or '').strip()
    q_norm = quitar_tildes(q_limpio)
    
    rutas_base = _obtener_catalogo_base(negocio_id=negocio_id, slug=slug)
    secciones_manuales = _cargar_indice_manuales()

    if not q_norm:
        # Si la consulta está vacía, devuelve los accesos más populares / estándar
        rutas_sugeridas = [
            r for r in rutas_base if r['titulo'] in (
                'Caja POS / Terminal de Ventas',
                'Plan Único de Cuentas (PUC)',
                'Tesorería: Desembolsos y Recaudos',
                'Catálogo de Productos e Insumos',
                'Entradas de Almacén (Compras y Facturas)',
                'Kardex',
            )
        ]
        return {
            'ok': True,
            'q': '',
            'rutas': rutas_sugeridas,
            'ayuda': []
        }

    # 1. Búsqueda en Rutas y Pestañas
    resultados_rutas = []
    tokens = q_norm.split()

    for item in rutas_base:
        tit_norm = quitar_tildes(item['titulo'])
        mod_norm = quitar_tildes(item['modulo'])
        keys_norm = ' '.join(quitar_tildes(k) for k in item['keywords'])
        full_text = f"{tit_norm} {mod_norm} {keys_norm}"

        score = 0
        if q_norm == tit_norm:
            score += 100
        elif tit_norm.startswith(q_norm):
            score += 80
        elif q_norm in tit_norm:
            score += 50
        elif q_norm in mod_norm:
            score += 30
        elif any(q_norm in k for k in item['keywords']):
            score += 25
        elif all(t in full_text for t in tokens):
            score += 15

        if score > 0:
            item_copy = dict(item)
            item_copy['score'] = score
            resultados_rutas.append(item_copy)

    resultados_rutas.sort(key=lambda x: x['score'], reverse=True)

    # 2. Búsqueda en Manuales y Secciones de Ayuda
    resultados_ayuda = []
    for item in secciones_manuales:
        tit_norm = quitar_tildes(item['titulo'])
        full_text = item['busqueda']

        score = 0
        if q_norm in tit_norm:
            score += 40
        elif all(t in full_text for t in tokens):
            score += 20
        elif any(t in full_text for t in tokens):
            score += 10

        if score > 0:
            item_copy = dict(item)
            item_copy['score'] = score
            resultados_ayuda.append(item_copy)

    resultados_ayuda.sort(key=lambda x: x['score'], reverse=True)

    # Limpiar scores internos antes de responder
    for r in resultados_rutas:
        r.pop('score', None)
        r.pop('keywords', None)
    for a in resultados_ayuda:
        a.pop('score', None)
        a.pop('busqueda', None)

    return {
        'ok': True,
        'q': q_limpio,
        'rutas': resultados_rutas[:8],
        'ayuda': resultados_ayuda[:6]
    }
def buscar_datos_producto(conn, q, negocio_id, slug=None, limite=20):
    """Datos de producto para omni (scope negocio activo). Filas 1-10 + 12-14:
    saldo/precio/mov/editar/agotado/sobrestock/estado/fisico/urgente/margen/
    rankings/top + urls. Lista (max limite)."""
    q_limpio = (q or '').strip()
    if len(q_limpio) < 2 or not negocio_id:
        return []
    try:
        nid = int(negocio_id)
    except (TypeError, ValueError):
        return []
    like = '%' + q_limpio + '%'
    try:
        rows = conn.execute(
            """SELECT p.id, p.nombre, p.precio, p.costo, p.codigo_barra, p.disponible,
                      p.categoria, p.dias_max_stock, um.codigo AS unidad,
                      (EXISTS(SELECT 1 FROM pedido_items i WHERE i.producto_id = p.id)
                       OR EXISTS(SELECT 1 FROM items_pedido_tienda i WHERE i.producto_id = p.id)) AS vendido,
                      COALESCE((SELECT SUM(s.stock) FROM saldos_inventario s
                                WHERE s.negocio_id = p.negocio_id AND s.producto_id = p.id), 0) AS stock
               FROM productos p LEFT JOIN unidades_medida um ON um.id = p.unidad_medida_id
               WHERE p.negocio_id = %s
                 AND (p.nombre ILIKE %s OR COALESCE(p.codigo_barra, '') ILIKE %s)
               ORDER BY p.disponible DESC, (LOWER(p.nombre) = LOWER(%s)) DESC, p.nombre
               LIMIT 20""",
            (nid, like, like, q_limpio)).fetchall()
    except Exception:
        return []
    if not rows:
        return []
    _ql = q_limpio.lower()
    try:
        rows = sorted(rows, key=lambda _r: (not bool(_r.get('disponible')),
                                            ((_r.get('nombre') or '').lower() != _ql),
                                            (_r.get('nombre') or '').lower()))
    except Exception:
        pass
    ids = [r['id'] for r in rows]
    movs, alertas, provs, tops, rankv, v30, urg, rankm = {}, {}, {}, {}, {}, {}, {}, {}
    rankv_total, rankm_total = 0, 0
    try:
        for m in conn.execute(
                """SELECT DISTINCT ON (m.producto_id) m.producto_id, m.tipo, m.motivo,
                          m.cantidad, m.documento_numero AS doc,
                          TO_CHAR(m.created_at, 'YYYY-MM-DD') AS fecha
                   FROM movimientos_inventario m
                   WHERE m.producto_id = ANY(%s)
                   ORDER BY m.producto_id, m.id DESC""",
                (ids,)).fetchall():
            movs[m['producto_id']] = {'tipo': m['tipo'], 'motivo': m['motivo'],
                                      'cantidad': float(m['cantidad'] or 0),
                                      'doc': m['doc'], 'fecha': m['fecha']}
    except Exception:
        movs = {}
    try:
        for a in conn.execute(
                "SELECT producto_id, estado, cobertura_dias FROM inventario_alertas_agotados "
                "WHERE negocio_id = %s AND producto_id = ANY(%s)",
                (nid, ids)).fetchall():
            alertas[a['producto_id']] = a
    except Exception:
        alertas = {}
    try:
        for x in conn.execute(
                "SELECT DISTINCT ON (m.producto_id) m.producto_id, m.proveedor_nombre "
                "FROM movimientos_inventario m WHERE m.producto_id = ANY(%s) "
                "AND m.tipo = 'entrada' AND m.proveedor_nombre IS NOT NULL "
                "ORDER BY m.producto_id, m.id DESC",
                (ids,)).fetchall():
            provs[x['producto_id']] = x['proveedor_nombre']
    except Exception:
        provs = {}
    try:
        for rk in conn.execute(
                "WITH v AS ("
                "  SELECT i.producto_id, SUM(i.cantidad) AS cant"
                "  FROM pedido_items i JOIN pedidos p ON p.id = i.pedido_id"
                "  WHERE p.negocio_id = %s AND date_trunc('month', i.created_at) = date_trunc('month', NOW())"
                "  GROUP BY 1"
                "  UNION ALL "
                "  SELECT i.producto_id, SUM(i.cantidad)"
                "  FROM items_pedido_tienda i JOIN pedidos_tienda p ON p.id = i.pedido_id"
                "  JOIN tiendas t ON t.id = p.tienda_id"
                "  WHERE t.tercero_id = %s AND date_trunc('month', i.created_at) = date_trunc('month', NOW())"
                "  GROUP BY 1"
                "), tot AS (SELECT producto_id, SUM(cant) AS cant FROM v GROUP BY 1) "
                "SELECT producto_id, RANK() OVER (ORDER BY cant DESC) AS rk, COUNT(*) OVER () AS total FROM tot",
                (nid, nid)).fetchall():
            rankv[rk['producto_id']] = rk['rk']
            rankv_total = rk['total']
            if rk['rk'] <= 10:
                tops[rk['producto_id']] = rk['rk']
    except Exception:
        tops, rankv, rankv_total = {}, {}, 0
    try:
        for s in conn.execute(
                "/* ventas30 */ SELECT producto_id, SUM(cant) AS cant FROM ("
                "  SELECT i.producto_id, SUM(i.cantidad) AS cant"
                "  FROM pedido_items i JOIN pedidos p ON p.id = i.pedido_id"
                "  WHERE p.negocio_id = %s AND i.producto_id = ANY(%s) AND i.created_at >= NOW() - INTERVAL '30 days'"
                "  GROUP BY 1"
                "  UNION ALL "
                "  SELECT i.producto_id, SUM(i.cantidad)"
                "  FROM items_pedido_tienda i JOIN pedidos_tienda p ON p.id = i.pedido_id"
                "  JOIN tiendas t ON t.id = p.tienda_id"
                "  WHERE t.tercero_id = %s AND i.producto_id = ANY(%s) AND i.created_at >= NOW() - INTERVAL '30 days'"
                "  GROUP BY 1) x GROUP BY 1",
                (nid, ids, nid, ids)).fetchall():
            v30[s['producto_id']] = float(s['cant'] or 0)
    except Exception:
        v30 = {}
    try:
        for u in conn.execute(
                "/* urgencia */ SELECT producto_id, RANK() OVER (ORDER BY score DESC) AS rk FROM ("
                "  SELECT p.id AS producto_id,"
                "   (COALESCE((SELECT SUM(s2.stock) FROM saldos_inventario s2"
                "     WHERE s2.producto_id = p.id AND s2.negocio_id = p.negocio_id), 0)"
                "    * COALESCE(p.costo, p.precio, 0))"
                "   * (1 + (SELECT COUNT(*) FROM movimientos_inventario m"
                "     WHERE m.producto_id = p.id AND m.created_at >= NOW() - INTERVAL '30 days')) AS score"
                "  FROM productos p WHERE p.negocio_id = %s) t",
                (nid,)).fetchall():
            urg[u['producto_id']] = u['rk']
    except Exception:
        urg = {}
    try:
        for g in conn.execute(
                "/* rankmargen */ SELECT id AS producto_id,"
                " RANK() OVER (ORDER BY (precio - costo) / NULLIF(precio, 0) DESC) AS rk,"
                " COUNT(*) OVER () AS total FROM productos WHERE negocio_id = %s AND precio > 0",
                (nid,)).fetchall():
            rankm[g['producto_id']] = (g['rk'], g['total'])
    except Exception:
        rankm = {}

    out = []
    for r in rows[:limite]:
        precio = float(r['precio'] or 0)
        costo = float(r['costo'] or 0)
        stock = float(r['stock'] or 0)
        margen = round((precio - costo) / precio * 100, 1) if precio > 0 else None
        pid = r['id']
        kurl = (f'https://{slug}.tuc-tuc.co/kardex?producto_id={pid}' if slug
                else f'/inventario/{nid}/kardex?producto_id={pid}')
        al = alertas.get(pid) or {}
        v = v30.get(pid, 0)
        valor = stock * costo
        dmax = r['dias_max_stock'] if r['dias_max_stock'] else 15
        cob = round(stock / (v / 30), 1) if v > 0 else None
        sobre = bool(valor > 0 and (cob is None or cob > dmax))
        urg_rk = urg.get(pid)
        rm = rankm.get(pid)
        out.append({
            'id': pid,
            'nombre': r['nombre'],
            'stock': stock,
            'precio': precio,
            'costo': costo,
            'margen': margen,
            'codigo': r['codigo_barra'],
            'categoria': r['categoria'],
            'unidad': r['unidad'],
            'disponible': bool(r['disponible']),
            'vendido': bool(r['vendido']),
            'agotado': stock <= 0,
            'alerta': al.get('estado'),
            'cobertura': float(al['cobertura_dias']) if al.get('cobertura_dias') is not None else None,
            'proveedor': provs.get(pid),
            'top_rank': tops.get(pid),
            'rank_ventas': rankv.get(pid),
            'rank_ventas_total': rankv_total or None,
            'rank_margen': rm[0] if rm else None,
            'rank_margen_total': rm[1] if rm else None,
            'sobre': sobre,
            'cobertura_calc': cob,
            'dias_max': dmax,
            'urgente': bool(urg_rk is not None and urg_rk <= 10),
            'urg_rank': urg_rk,
            'ult_mov': movs.get(pid),
            'urls': {
                'kardex': kurl,
                'productos': f'/inventario/{nid}?tab=productos',
                'editar': f'/inventario/{nid}?tab=productos&editar_producto={pid}',
                'compras': f'/inventario/{nid}?tab=compras_sugerencias',
                'fisico': f'/admin/inventario-fisico/{nid}',
                'vcosto': f'/ventas-costos/{nid}',
                'toggle': f'/api/inventario/producto/{pid}/disponible',
            },
        })
    return out


def buscar_sueltos(conn, negocio_id, limite=10):
    """Reporte puntual: sueltos con movimiento y sin venta (scope negocio)."""
    if not negocio_id:
        return {'items': [], 'total': 0}
    try:
        nid = int(negocio_id)
    except (TypeError, ValueError):
        return {'items': [], 'total': 0}
    try:
        items = conn.execute(
            "SELECT p.id, p.nombre, "
            "(SELECT COUNT(*) FROM movimientos_inventario m WHERE m.producto_id = p.id) AS movs "
            "FROM productos p WHERE p.negocio_id = %s "
            "AND NOT EXISTS (SELECT 1 FROM tarjeta_estandar te WHERE te.producto_id = p.id) "
            "AND NOT EXISTS (SELECT 1 FROM tarjeta_estandar te WHERE te.componente_id = p.id) "
            "AND EXISTS (SELECT 1 FROM movimientos_inventario m WHERE m.producto_id = p.id) "
            "AND NOT EXISTS (SELECT 1 FROM pedido_items i WHERE i.producto_id = p.id) "
            "AND NOT EXISTS (SELECT 1 FROM items_pedido_tienda i WHERE i.producto_id = p.id) "
            "ORDER BY movs DESC LIMIT 10",
            (nid,)).fetchall()
        tot = conn.execute(
            "SELECT COUNT(*) AS total FROM productos p WHERE p.negocio_id = %s "
            "AND NOT EXISTS (SELECT 1 FROM tarjeta_estandar te WHERE te.producto_id = p.id) "
            "AND NOT EXISTS (SELECT 1 FROM tarjeta_estandar te WHERE te.componente_id = p.id) "
            "AND EXISTS (SELECT 1 FROM movimientos_inventario m WHERE m.producto_id = p.id) "
            "AND NOT EXISTS (SELECT 1 FROM pedido_items i WHERE i.producto_id = p.id) "
            "AND NOT EXISTS (SELECT 1 FROM items_pedido_tienda i WHERE i.producto_id = p.id)",
            (nid,)).fetchone()
        return {'items': [{'id': x['id'], 'nombre': x['nombre'], 'movs': int(x['movs'])} for x in items],
                'total': int((tot or {}).get('total') or 0)}
    except Exception:
        return {'items': [], 'total': 0}
