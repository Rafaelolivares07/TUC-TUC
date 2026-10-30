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
            'titulo': 'Portal Corporativo',
            'modulo': 'General',
            'icono': '🏢',
            'url': '/portal',
            'keywords': ['portal', 'portada', 'buscar', 'buscador', 'lanzador']
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
            'titulo': 'Tesorería: Desembolsos y Recaudos',
            'modulo': 'Contabilidad > Tesorería',
            'icono': '🏛️',
            'url': f'/contabilidad/{nid}?tab=desembolsos',
            'keywords': ['gastos', 'desembolsos', 'recaudos', 'caja menor', 'pagos', 'egresos', 'salidas de dinero', 'compras gastos']
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
            'url': f'/inventario/{nid}?tab=entradas',
            'keywords': ['entradas de almacen', 'compras', 'factura de compra', 'recepcion insumos', 'remision', 'ingreso stock']
        },
        {
            'titulo': 'Órdenes de Producción y Fabricación',
            'modulo': 'Inventario > Producción',
            'icono': '⚙️',
            'url': f'/inventario/{nid}?tab=produccion',
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
            'titulo': 'Kardex (Trazabilidad y Movimientos)',
            'modulo': 'Inventario > Auditoría',
            'icono': '📈',
            'url': f'/inventario/{nid}?tab=kardex',
            'keywords': ['kardex', 'movimientos de inventario', 'entradas salidas', 'costo promedio ponderado', 'trazabilidad stock', 'historial']
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
            'titulo': 'Ventas y Costos de Inventario',
            'modulo': 'Inventario > Rentabilidad',
            'icono': '💹',
            'url': f'/inventario/{nid}?tab=ventas_costos',
            'keywords': ['ventas costos', 'costo de ventas', 'margen de ganancia', 'utilidad bruta', 'rentabilidad productos', 'ventas/costos', 'costos']
        },
        {
            'titulo': 'Desembolsos y Gastos de Inventario',
            'modulo': 'Inventario > Pagos',
            'icono': '💸',
            'url': f'/inventario/{nid}?tab=desembolsos',
            'keywords': ['desembolsos', 'gastos inventario', 'pagos proveedores', 'egresos inventario']
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
                'Kardex (Trazabilidad y Movimientos)'
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
