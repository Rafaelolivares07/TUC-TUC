import urllib.parse
# app/buscador_motor.py
# Motor omnibox unificado de rutas, pestanas y manuales de ayuda para TUC TUC V2

import os
import re
import unicodedata
import json

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
            cuerpo = []
            for j in range(i + 1, len(lines)):
                next_l = lines[j].strip()
                if re.match(r'^#{1,3}\s+', next_l):
                    break
                if next_l and not next_l.startswith('---'):
                    cuerpo.append(re.sub(r'[*_`\[\]]', '', next_l))
            preview = ''
            if cuerpo:
                preview = cuerpo[0][:130] + ('...' if len(cuerpo[0]) > 130 else '')
            full_txt = ' '.join(cuerpo)[:3000]
                    
            secciones.append({
                'titulo': titulo,
                'manual': nombre_manual,
                'icono': '📖',
                'resumen': preview or 'Ver detalle y pasos en el manual',
                'url': f'/docs/{slug}#{anchor}',
                'slug': slug,
                'cuerpo_completo': full_txt,
                'busqueda': f"{quitar_tildes(titulo)} {quitar_tildes(nombre_manual)} {quitar_tildes(full_txt)}"
            })

    _CACHE_MANUALES = secciones
    return _CACHE_MANUALES

def invalidar_cache_manuales():
    global _CACHE_MANUALES
    _CACHE_MANUALES = None

_SUGERIDOS = {'caja_pos', 'conta_tab_puc', 'catalogo_productos', 'entradas', 'kardex'}

# Grants viejos -> fila semilla (endpoint legado, clave nueva).
_MIGRAR_GRANTS = (('tiendas.admin_caja', 'caja_pos'),)

_CATALOGO_PANTALLAS = [
    ('inicio', 'Inicio / Menú Principal', 'core.colaborador_inicio', '🏠', 'General', None, '/inicio', ['inicio', 'dashboard', 'panel', 'home', 'herramientas', 'menu principal', 'accesos'], 10, True),
    ('portal', 'Desk', 'core.colaborador_portal', '🏢', 'General', None, '/portal', ['desk', 'portal', 'portada', 'buscar', 'buscador', 'lanzador'], 20, True),
    ('agenda', 'Agenda', 'agenda.agenda', '🗓️', 'General', None, '/agenda', ['agenda', 'tareas', 'pendientes', 'recordatorios', 'por hacer', 'lista de tareas'], 30, True),
    ('caja_pos', 'Caja POS / Terminal de Ventas', 'tiendas.tienda_caja', '🛒', 'Ventas', None, '/tienda/{slug}/caja', ['caja', 'pos', 'vender', 'cobrar', 'facturar', 'punto de venta', 'ticket', 'arqueo'], 40, True),
    ('mi_tienda', 'Mi Tienda (Dashboard)', 'tiendas.mi_tienda', '🏪', 'Ventas', None, '/mi-tienda/{slug}', ['mi tienda', 'panel tienda', 'administrar tienda', 'catalogo tienda', 'pauta', 'pedidos tienda', 'visitantes'], 50, True),
    ('mi_restaurante', 'Mi Restaurante (Dashboard)', 'restaurantes.mi_restaurante', '🍽️', 'Ventas', None, '/mi-restaurante/{slug}', ['mi restaurante', 'panel restaurante', 'mesas', 'cuentas', 'menu del dia', 'catalogo restaurante'], 60, True),
    ('mesero', 'Mesero (Toma de pedidos)', 'restaurantes.restaurante_mesero', '🧾', 'Ventas', None, '/r/{slug}/mesero', ['mesero', 'tomar pedido', 'pedido mesa', 'orden mesa'], 70, True),
    ('cocina', 'Cocina (Comandas)', 'restaurantes.restaurante_cocina', '👨\u200d🍳', 'Ventas', None, '/r/{slug}/cocina', ['cocina', 'comandas', 'pedidos cocina', 'preparacion'], 80, True),
    ('metodos_pago', 'Métodos de pago (Tienda)', 'tiendas.admin_tienda_metodos_pago', '💳', 'Ventas', None, '/admin/tienda/{slug}/metodos-pago', ['metodos de pago tienda', 'formas de pago', 'nequi', 'daviplata', 'transferencia'], 90, True),
    ('inventario', 'Inventario — General', 'inventarios.admin_inventario', '📦', 'Inventario', None, '/inventario/{nid}', ['inventario', 'stock', 'almacen', 'existencias', 'bodega', 'productos'], 100, True),
    ('kardex', 'Kardex', 'inventarios.kardex_standalone', '📦', 'Inventario', None, None, ['kardex', 'movimientos', 'existencias', 'saldos', 'entradas', 'salidas'], 110, True),
    ('catalogo_productos', 'Catálogo de Productos e Insumos', 'inventarios.catalogo_productos_standalone', '📋', 'Inventario', None, '/catalogo-productos/{nid}', ['productos', 'insumos', 'catalogo', 'catálogo', 'catalogo de productos', 'precios', 'categorias', 'codigo de barras', 'barcode', 'costo unitario', 'recetas', 'ficha tecnica'], 120, True),
    ('entradas', 'Entradas de Almacén (Compras y Facturas)', 'inventarios.entradas_standalone', '📥', 'Inventario', None, '/entradas/{nid}', ['entradas de almacen', 'compras', 'factura de compra', 'recepcion insumos', 'remision', 'ingreso stock'], 130, True),
    ('produccion', 'Órdenes de Producción y Fabricación', 'inventarios.produccion_standalone', '⚙️', 'Inventario', None, '/produccion/{nid}', ['produccion', 'orden de produccion', 'fabricacion', 'lote', 'transformacion', 'cocina'], 140, True),
    ('ventas_costos', 'Ventas y Costos (Margen de Contribución)', 'inventarios.ventas_costos_standalone', '📊', 'Comercial', None, '/ventas-costos/{nid}', ['ventas costos', 'costo de ventas', 'margen de ganancia', 'utilidad bruta', 'rentabilidad productos', 'ventas/costos', 'costos'], 150, True),
    ('inventario_fisico', 'Inventario Físico (Conteo y Ajuste)', 'inventarios.admin_inventario_fisico', '📋', 'Inventario', None, '/admin/inventario-fisico/{nid}', ['inventario fisico', 'conteo fisico', 'toma de inventario', 'sobrantes faltantes', 'ajuste de inventario', 'conteo manual'], 160, True),
    ('inventario_distribuido', 'Inventario Físico Distribuido (Móvil / Tablet)', 'inventarios.admin_inventario_distribuido', '🔄', 'Inventario', None, '/admin/inventario-distribuido/{nid}', ['inventario distribuido', 'conteo por zonas', 'conteo con celulares', 'varios contadores', 'tablet'], 170, True),
    ('contabilidad', 'Contabilidad — General', 'contabilidad.admin_contabilidad', '📒', 'Contabilidad', None, '/contabilidad/{nid}', ['contabilidad', 'contable', 'finanzas', 'cuentas', 'asientos', 'balance'], 180, True),
    ('tesoreria', 'Tesorería: Pagos, Desembolsos y Recaudos', 'contabilidad.tesoreria_standalone', '🏛️', 'Contabilidad', None, '/tesoreria/{nid}', ['tesoreria', 'tesorería', 'gastos', 'desembolsos', 'recaudos', 'caja menor', 'pagos', 'egresos', 'salidas de dinero', 'compras gastos', 'pagos proveedores', 'gastos inventario', 'egresos inventario'], 190, True),
    ('saldos_documentos', 'Reporte de Saldos por Documento', 'contabilidad.admin_saldos_documentos', '📊', 'Contabilidad', None, '/admin/saldos-documentos/{nid}', ['saldos por documento', 'cartera', 'cuentas por pagar', 'cuentas por cobrar', 'facturas pendientes', 'cxp', 'cxc'], 200, True),
    ('conciliacion', 'Conciliación de Cuentas y Bancos', 'contabilidad.admin_conciliacion_disponible', '⚖️', 'Contabilidad', None, '/admin/conciliacion-disponible/{nid}', ['conciliacion bancaria', 'conciliar disponible', 'extracto bancario', 'banco vs libros', 'saldo real', 'disponible'], 210, True),
    ('mant_negocio', 'Mantenimiento de Negocio', 'inventarios.admin_negocio_mantenimiento', '🛠️', 'Mantenimiento', None, '/admin/mantenimiento/{nid}', ['mantenimiento negocio', 'herramientas', 'reparar', 'depurar', 'auditoria', 'utilidades'], 220, True),
    ('auditor_documentos', 'Auditoría de Documentos (Nueva versión)', 'inventarios.auditor_documentos_standalone', '🔍', 'Mantenimiento', None, '/auditor-documentos/{nid}', ['auditoria documentos', 'auditoria de documentos', 'auditor documentos', 'buscar documento', 'anular documento', 'factura proveedor', 'factura venta', 'descuadres', 'kardex auditoria', 'desk', 'nueva version'], 225, True),
    ('mant_global', 'Mantenimiento del Sistema (Global)', 'core.admin_mantenimiento', '🔧', 'Administración', None, '/admin/mantenimiento', ['mantenimiento', 'logs', 'git', 'version', 'diagnostico', 'base de datos'], 230, True),
    ('gestion_permisos', 'Gestión de Permisos y Colaboradores', 'core.core_gestion_permisos', '👥', 'Administración', None, '/admin/permisos', ['permisos', 'usuarios', 'colaboradores', 'roles', 'accesos', 'empleados'], 240, True),
    ('pantallas_catalogo', 'Catálogo Técnico de Pantallas', 'core.core_pantallas_catalogo', '🖥️', 'Administración', None, '/admin/pantallas-catalogo', ['pantallas catalogo', 'modulos', 'endpoints', 'permisos', 'vistas'], 250, True),
    ('negocio_config', 'Configuración de Negocio', 'negocios.admin_config_negocio', '⚙️', 'Administración', None, '/admin/negocio/{nid}/config', ['configuracion negocio', 'logo', 'razon social', 'nit', 'datos empresa', 'horarios'], 260, True),
    ('conta_tab_puc', 'Plan Único de Cuentas (PUC)', 'contabilidad.admin_contabilidad', '📋', 'Contabilidad > Cuentas', 'tab=puc', '/contabilidad/{nid}?tab=puc', ['puc', 'plan de cuentas', 'catalogo de cuentas', 'adoptar cuenta', 'codigo contable', 'subcuenta'], 1010, False),
    ('conta_tab_tipos', 'Tipos de Documento Contable', 'contabilidad.admin_contabilidad', '📄', 'Contabilidad > Configuración', 'tab=tipos', '/contabilidad/{nid}?tab=tipos', ['tipos documento', 'comprobante de ingreso', 'comprobante de egreso', 'facturas compra', 'nota contable', 'consecutivos'], 1020, False),
    ('conta_tab_params', 'Parametrización de Asientos', 'contabilidad.admin_contabilidad', '⚙️', 'Contabilidad > Reglas', 'tab=params', '/contabilidad/{nid}?tab=params', ['parametrizacion', 'moldes', 'reglas contables', 'debitos creditos', 'automatizacion asientos', 'partida doble', 'plantillas contables'], 1030, False),
    ('conta_tab_pago', 'Métodos de Pago', 'contabilidad.admin_contabilidad', '💳', 'Contabilidad / Tienda', 'tab=pago_metodos', '/contabilidad/{nid}?tab=pago_metodos', ['metodos de pago', 'formas de pago', 'tarjeta', 'nequi', 'daviplata', 'transferencia', 'efectivo', 'bancos'], 1040, False),
    ('conta_tab_amort', 'Amortizaciones de Gastos y Préstamos', 'contabilidad.admin_contabilidad', '⏳', 'Contabilidad > Finanzas', 'tab=amortizaciones', '/contabilidad/{nid}?tab=amortizaciones', ['amortizaciones', 'diferidos', 'prestamos', 'cuotas', 'seguros anticipados', 'tablas amortizacion'], 1050, False),
    ('conta_tab_pyg', 'Estado de Resultados (PyG)', 'contabilidad.admin_contabilidad', '📊', 'Contabilidad > Informes', 'tab=estado_resultados', '/contabilidad/{nid}?tab=estado_resultados', ['estado de resultados', 'pyg', 'perdidas y ganancias', 'utilidad', 'ingresos vs gastos', 'rentabilidad', 'ejercicio'], 1060, False),
    ('conta_tab_equilibrio', 'Punto de Equilibrio', 'contabilidad.admin_contabilidad', '🎯', 'Contabilidad > Informes', 'tab=punto_equilibrio', '/contabilidad/{nid}?tab=punto_equilibrio', ['punto de equilibrio', 'costos fijos', 'costos variables', 'margen de contribucion', 'ventas minimas', 'meta ventas'], 1070, False),
    ('conta_tab_grupos', 'Grupos de Inventario Contables', 'contabilidad.admin_contabilidad', '🗂️', 'Contabilidad > Grupos Inv.', 'tab=grupos', '/contabilidad/{nid}?tab=grupos', ['grupos inventario', 'grupos contables', 'cuentas inventario', 'clasificacion contable'], 1080, False),
    ('conta_tab_manual', 'Comprobante Manual (Crear / Editar)', 'contabilidad.admin_contabilidad', '✏️', 'Contabilidad > Asientos', 'tab=manual', '/contabilidad/{nid}?tab=manual', ['comprobante manual', 'nuevo comprobante', 'crear asiento', 'nota contable manual', 'asiento ajuste'], 1090, False),
    ('conta_tab_comps', 'Comprobantes Generados (Histórico)', 'contabilidad.admin_contabilidad', '📚', 'Contabilidad > Asientos', 'tab=comps', '/contabilidad/{nid}?tab=comps', ['comprobantes', 'asientos contables', 'historico contable', 'buscar comprobante', 'libro diario', 'movimientos contables'], 1100, False),
    ('conta_tab_progs', 'Programaciones Contables Recurrentes', 'contabilidad.admin_contabilidad', '⏱️', 'Contabilidad > Automatización', 'tab=progs', '/contabilidad/{nid}?tab=progs', ['programaciones', 'asientos programados', 'recurrentes', 'asientos automaticos', 'periodicos'], 1110, False),
    ('conta_tab_consulta', 'Consulta de Movimientos (Libro Mayor)', 'contabilidad.admin_contabilidad', '🔍', 'Contabilidad > Informes', 'tab=consulta', '/contabilidad/{nid}?tab=consulta', ['consulta movimientos', 'libro mayor', 'auxiliar contable', 'movimientos cuenta', 'extracto cuenta', 'tercero cuenta'], 1120, False),
    ('conta_tab_balance', 'Balance y Cierre de Periodo', 'contabilidad.admin_contabilidad', '⚖️', 'Contabilidad > Cierre', 'tab=balance', '/contabilidad/{nid}?tab=balance', ['balance', 'balance de prueba', 'cierre contable', 'cierre de mes', 'cierre anual', 'saldos cuentas'], 1130, False),
    ('conta_tab_reclas', 'Reclasificaciones Contables', 'contabilidad.admin_contabilidad', '🔀', 'Contabilidad > Ajustes', 'tab=reclasificaciones', '/contabilidad/{nid}?tab=reclasificaciones', ['reclasificaciones', 'reclasificar', 'corregir cuenta', 'mover asiento', 'ajuste contable'], 1140, False),
    ('inv_tab_tarjetas', 'Tarjetas Estándar (Fórmulas y Recetas)', 'inventarios.admin_inventario', '🧾', 'Inventario > Producción', 'tab=tarjetas', '/inventario/{nid}?tab=tarjetas', ['tarjetas estandar', 'recetas', 'formulas', 'ingredientes', 'porciones', 'costo receta', 'ficha tecnica'], 1150, False),
    ('inv_tab_compras', 'Sugerencias de Compras (Reabastecimiento)', 'inventarios.admin_inventario', '🛒', 'Inventario > Compras', 'tab=compras_sugerencias', '/inventario/{nid}?tab=compras_sugerencias', ['sugerencias compras', 'reabastecer', 'punto de reorden', 'stock minimo', 'faltantes', 'pedir insumos', 'sugerir compras'], 1160, False),
    ('inv_tab_cotiz', 'Cotizaciones de Proveedores', 'inventarios.admin_inventario', '📋', 'Inventario > Compras', 'tab=cotizaciones', '/inventario/{nid}?tab=cotizaciones', ['cotizaciones', 'cotizar', 'comparar proveedores', 'precios proveedor', 'solicitud de precio'], 1170, False),
    ('inv_tab_traslados', 'Traslados entre Bodegas o Sedes', 'inventarios.admin_inventario', '🔄', 'Inventario > Movimientos', 'tab=traslados', '/inventario/{nid}?tab=traslados', ['traslados', 'mover stock', 'enviar a otra bodega', 'transferencia entre sedes', 'remision interna', 'traspasos'], 1180, False),
    ('inv_tab_ensambles', 'Ensambles de Productos', 'inventarios.admin_inventario', '🧩', 'Inventario > Producción', 'tab=ensambles', '/inventario/{nid}?tab=ensambles', ['ensambles', 'combos', 'armar paquetes', 'desarmar', 'kits', 'ensamblar'], 1190, False),
    ('inv_tab_enshist', 'Ensambles Históricos', 'inventarios.admin_inventario', '📦', 'Inventario > Producción', 'tab=ensambles_historicos', '/inventario/{nid}?tab=ensambles_historicos', ['ensambles historicos', 'historico ensambles', 'registros ensambles', 'combos armados'], 1200, False),
    ('inv_tab_eres', 'Estado de Resultados de Inventario', 'inventarios.admin_inventario', '📊', 'Inventario > Informes', 'tab=estado_resultados', '/inventario/{nid}?tab=estado_resultados', ['estado de resultados inventario', 'pyg inventario', 'utilidad inventario', 'ganancias'], 1210, False),
    ('inv_tab_recosteo', 'Recosteo y Auditoría de Inventario', 'inventarios.admin_inventario', '🔍', 'Inventario > Auditoría', 'tab=recosteo', '/inventario/{nid}?tab=recosteo', ['recosteo', 'auditoria inventario', 'corregir costo promedio', 'descuadres de costo', 'recalcular costos'], 1220, False),
    ('inv_tab_actas', 'Libro de Actas de Inventario', 'inventarios.admin_inventario', '📋', 'Inventario > Actas', 'tab=actas_inventario', '/inventario/{nid}?tab=actas_inventario', ['libro de actas', 'actas inventario', 'firmas actas', 'registro legal', 'acta conteo'], 1230, False),
    ('mant_tool_auditor', 'Auditoría de Documentos (Mantenimiento)', 'inventarios.admin_negocio_mantenimiento', '🔍', 'Mantenimiento > Auditoría', 'tool=auditor-documentos', '/admin/mantenimiento/{nid}?tool=auditor-documentos', ['auditoria documentos', 'buscar documento', 'anular documento', 'factura proveedor', 'factura venta', 'descuadres', 'cruces'], 1240, False),
    ('mant_tool_unificar', 'Unificación de Terceros (Mantenimiento)', 'inventarios.admin_negocio_mantenimiento', '👥', 'Mantenimiento > Terceros', 'tool=unificar-terceros', '/admin/mantenimiento/{nid}?tool=unificar-terceros', ['unificar terceros', 'fusionar clientes', 'proveedores duplicados', 'limpiar terceros', 'duplicados'], 1250, False),
    ('manual_contabilidad', 'Manual de Contabilidad', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=contabilidad', '/docs/contabilidad', ['manual', 'ayuda', 'contabilidad', 'guia contable', 'tutorial'], 300, True),
    ('manual_tienda', 'Manual de Tienda', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=tienda', '/docs/tienda', ['manual', 'ayuda', 'tienda', 'guia tienda', 'vender'], 310, True),
    ('manual_restaurante', 'Manual de Restaurante', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=restaurante', '/docs/restaurante', ['manual', 'ayuda', 'restaurante', 'mesas', 'guia restaurante'], 320, True),
    ('manual_domotica', 'Manual de Domótica', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=domotica', '/docs/domotica', ['manual', 'ayuda', 'domotica', 'dispositivos', 'control casa'], 330, True),
    ('manual_asistencia-remota', 'Manual de Asistencia Remota', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=asistencia-remota', '/docs/asistencia-remota', ['manual', 'ayuda', 'asistencia', 'soporte', 'remoto'], 340, True),
    ('manual_alegra', 'Manual de Alegra', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=alegra', '/docs/alegra', ['manual', 'ayuda', 'alegra', 'facturacion electronica', 'integracion'], 350, True),
    ('manual_vendedor', 'Manual de Vendedor', 'core.core_ver_manual', '📖', 'Manuales de ayuda', 'doc=vendedor', '/docs/vendedor', ['manual', 'ayuda', 'vendedor', 'pedidos', 'preventa'], 360, True),
]


def _filas_desde_semilla():
    """Filas dict desde la semilla en codigo (tests standalone)."""
    out = []
    for (_clave, _nombre, _ep, _icono, _mod, _q, _tpl, _kws, _ord, _ot) in _CATALOGO_PANTALLAS:
        out.append({'clave': _clave, 'nombre': _nombre, 'endpoint': _ep, 'icono': _icono,
                    'modulo': _mod, 'query': _q, 'url_tpl': _tpl,
                    'keywords': json.dumps(_kws, ensure_ascii=False),
                    'orden': _ord, 'otorgable': _ot, 'sugerido': _clave in _SUGERIDOS})
    return out


def _url_fila(fila, negocio_id, slug):
    """URL de una fila: plantilla, kardex, o resolver Flask."""
    tpl = (fila.get('url_tpl') or '').strip()
    if tpl and (('{nid}' in tpl and negocio_id is None) or ('{slug}' in tpl and not slug)):
        return '#'
    if tpl:
        try:
            return tpl.format(nid=negocio_id, slug=slug or '')
        except Exception:
            pass
    ep = fila.get('endpoint') or ''
    if ep == 'inventarios.kardex_standalone':
        if slug:
            return f'https://{slug}.tuc-tuc.co/kardex'
        return f'/inventario/{negocio_id}/kardex' if negocio_id is not None else '#'
    try:
        from flask import url_for
    except Exception:
        return '#'
    url = '#'
    for _kw in ({'negocio_id': negocio_id} if negocio_id is not None else {},
               {'tercero_id': negocio_id} if negocio_id is not None else {},
               {'slug': slug} if slug else {}, {}):
        try:
            url = url_for(ep, **_kw)
            break
        except Exception:
            continue
    if url != '#' and fila.get('query'):
        url += ('&' if '?' in url else '?') + fila['query']
    return url


_CACHE_CATALOGO = None


def _filas_catalogo(conn=None):
    """Filas del catalogo unico (cache en proceso; [] si no hay BD)."""
    global _CACHE_CATALOGO
    if _CACHE_CATALOGO is not None:
        return _CACHE_CATALOGO
    cerrar = False
    try:
        if conn is None:
            from .db import get_db_connection
            conn = get_db_connection()
            cerrar = True
        rows = conn.execute(
            "SELECT nombre, modulo, icono, endpoint, query, url_tpl, keywords, sugerido "
            "FROM pantallas ORDER BY orden, id").fetchall()
        _CACHE_CATALOGO = [dict(r) for r in rows]
    except Exception:
        _CACHE_CATALOGO = _CACHE_CATALOGO or []
    finally:
        if cerrar:
            try:
                conn.close()
            except Exception:
                pass
    return _CACHE_CATALOGO


def _obtener_catalogo_base(negocio_id=None, slug=None, otorgados=None, filas=None):
    """Entradas omni desde el catalogo unico. otorgados=None muestra todo."""
    out = []
    vistos = set()
    for r in (filas if filas is not None else _filas_catalogo()):
        if (r.get('modulo') or '') == 'Manuales de ayuda':
            continue  # omni los muestra como secciones de ayuda, no como rutas
        ep = r.get('endpoint') or ''
        _k = (ep, r.get('query') or '')
        if _k in vistos:
            continue
        vistos.add(_k)
        if otorgados is not None and ep not in otorgados:
            continue
        try:
            kws = json.loads(r.get('keywords') or '[]')
            if not isinstance(kws, list):
                kws = [kws]
        except Exception:
            kws = [r.get('keywords')] if r.get('keywords') else []
        out.append({
            'titulo': r.get('nombre') or '',
            'modulo': r.get('modulo') or 'General',
            'icono': r.get('icono') or '',
            'url': _url_fila(r, negocio_id, slug),
            'keywords': kws,
            'endpoint': ep,
            'sugerido': bool(r.get('sugerido')),
        })
    return out



def _obtener_mapa_tipos_doc(conn, negocio_id):
    """Mapea codigos internos y slugs de tipos de documento a sus nombres reales
    configurados por el usuario en tipos_documento_negocio.
    """
    mapa = {}
    if not negocio_id:
        return mapa
    try:
        rows = conn.execute(
            "SELECT codigo, nombre FROM tipos_documento_negocio WHERE negocio_id = %s",
            (negocio_id,)
        ).fetchall()
        for r in rows:
            cod = (r['codigo'] or '').strip()
            nom = (r['nombre'] or '').strip()
            if cod and nom:
                mapa[cod.lower()] = nom
                mapa[cod.upper()] = nom
                mapa[cod] = nom
                mapa[cod.replace('_', ' ').lower()] = nom
    except Exception:
        pass
    return mapa

def _formatear_nombre_doc(tipo_doc, mapa_docs):
    """Traduce un slug o codigo interno al nombre real del documento configurado
    por el negocio. Si no esta registrado, elimina guiones bajos y aplica formato legible.
    """
    if not tipo_doc:
        return 'Documento'
    t_clean = str(tipo_doc).strip()
    if t_clean in mapa_docs:
        return mapa_docs[t_clean]
    if t_clean.lower() in mapa_docs:
        return mapa_docs[t_clean.lower()]
    return t_clean.replace('_', ' ').strip().title()

def _extraer_fragmento_coincidente(texto, tokens, radio=55):
    """Extrae un extracto de texto centrado en la primera coincidencia de palabra."""
    if not texto or not tokens:
        return ''
    norm_txt = quitar_tildes(texto).lower()
    for t in tokens:
        if len(t) < 3:
            continue
        m = re.search(r'\b' + re.escape(t), norm_txt)
        if m:
            start = max(0, m.start() - radio)
            end = min(len(texto), m.end() + radio)
            while start > 0 and texto[start] not in ' .;,\n':
                start -= 1
            while end < len(texto) and texto[end] not in ' .;,\n':
                end += 1
            frag = texto[start:end].strip()
            if start > 0:
                frag = '...' + frag
            if end < len(texto):
                frag = frag + '...'
            return frag
    return ''

def buscar_omni(q, negocio_id=None, slug=None, otorgados=None, filas=None, manuales_otorgados=None, incluir_manuales=True):
    q_limpio = (q or '').strip()
    q_norm = quitar_tildes(q_limpio).lower()
    
    rutas_base = _obtener_catalogo_base(negocio_id=negocio_id, slug=slug, otorgados=otorgados, filas=filas)
    secciones_manuales = _cargar_indice_manuales() if incluir_manuales else []

    if not q_norm:
        # Sin consulta: sugeridos del catalogo (ya filtrados por otorgados)
        rutas_sugeridas = [r for r in rutas_base if r.get('sugerido')][:6]
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
        tit_norm = quitar_tildes(item['titulo']).lower()
        mod_norm = quitar_tildes(item['modulo']).lower()
        keys_norm = ' '.join(quitar_tildes(k).lower() for k in item['keywords'])
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
        elif any(q_norm in k.lower() for k in item['keywords']):
            score += 25
        elif all(t in full_text for t in tokens):
            score += 15

        if score > 0:
            item_copy = dict(item)
            item_copy['score'] = score
            resultados_rutas.append(item_copy)

    resultados_rutas.sort(key=lambda x: x['score'], reverse=True)

    # 2. Búsqueda en Manuales y Secciones de Ayuda (Con límites de palabra estrictos)
    resultados_ayuda = []
    if incluir_manuales:
        for item in secciones_manuales:
            if manuales_otorgados is not None and item.get('slug') not in manuales_otorgados:
                continue
            tit_norm = quitar_tildes(item['titulo']).lower()
            man_norm = quitar_tildes(item['manual']).lower()
            full_text = item['busqueda'].lower()

            score = 0
            if q_norm == tit_norm:
                score += 120
            elif tit_norm.startswith(q_norm):
                score += 90
            elif q_norm in tit_norm:
                score += 70
            elif q_norm in man_norm:
                score += 50
            else:
                # Coincidencias token a token exigiendo limites de palabra ()
                tokens_tit = [t for t in tokens if re.search(r'' + re.escape(t), tit_norm)]
                tokens_man = [t for t in tokens if re.search(r'' + re.escape(t), man_norm)]
                tokens_cuerpo = [t for t in tokens if re.search(r'' + re.escape(t), full_text)]

                if len(tokens) == 1:
                    t = tokens[0]
                    if t in tokens_tit:
                        score += 60
                    elif t in tokens_man:
                        score += 40
                    elif len(t) >= 3 and t in tokens_cuerpo:
                        score += 25
                else:
                    # Multi-token: Si todos los tokens coinciden como palabras en el contenido
                    if len(tokens_cuerpo) == len(tokens):
                        score += 45
                        if len(tokens_tit) > 0:
                            score += 25
                    elif len(tokens_tit) == len(tokens):
                        score += 70

            if score > 0:
                item_copy = dict(item)
                item_copy['score'] = score
                # Si coincidió en el cuerpo y no en el título, traer el fragmento del match
                if score < 70 and 'cuerpo_completo' in item:
                    frag = _extraer_fragmento_coincidente(item['cuerpo_completo'], tokens)
                    if frag:
                        item_copy['resumen'] = frag
                resultados_ayuda.append(item_copy)

        resultados_ayuda.sort(key=lambda x: x['score'], reverse=True)

    # Limpiar campos internos antes de responder
    for r in resultados_rutas:
        r.pop('score', None)
        r.pop('keywords', None)
    for a in resultados_ayuda:
        a.pop('score', None)
        a.pop('busqueda', None)
        a.pop('slug', None)
        a.pop('cuerpo_completo', None)

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
                      EXISTS(SELECT 1 FROM tarjeta_estandar te WHERE te.producto_id = p.id) AS es_receta,
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
        sql_v30 = """
            /* rotacion30 */
            WITH movs AS (
                SELECT producto_id, SUM(cantidad) AS cant
                FROM movimientos_inventario
                WHERE negocio_id = %s AND producto_id = ANY(%s) 
                  AND tipo = 'salida' 
                  AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY producto_id
            ),
            peds AS (
                SELECT i.producto_id, SUM(i.cantidad) AS cant
                FROM pedido_items i 
                JOIN pedidos p ON p.id = i.pedido_id
                WHERE p.negocio_id = %s AND i.producto_id = ANY(%s) 
                  AND i.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY i.producto_id
                UNION ALL
                SELECT i.producto_id, SUM(i.cantidad) AS cant
                FROM items_pedido_tienda i 
                JOIN pedidos_tienda p ON p.id = i.pedido_id
                JOIN tiendas t ON t.id = p.tienda_id
                WHERE t.tercero_id = %s AND i.producto_id = ANY(%s) 
                  AND i.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY i.producto_id
            ),
            peds_tot AS (
                SELECT producto_id, SUM(cant) AS cant FROM peds GROUP BY producto_id
            )
            SELECT u.id AS producto_id, 
                   GREATEST(COALESCE(m.cant, 0), COALESCE(pt.cant, 0)) AS cant
            FROM UNNEST(%s::int[]) AS u(id)
            LEFT JOIN movs m ON m.producto_id = u.id
            LEFT JOIN peds_tot pt ON pt.producto_id = u.id
        """
        for s in conn.execute(sql_v30, (nid, ids, nid, ids, nid, ids, ids)).fetchall():
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
        es_rec = bool(r.get('es_receta'))
        v = v30.get(pid, 0)
        valor = stock * costo
        dmax = r['dias_max_stock'] if r['dias_max_stock'] else 15
        cob = round(stock / (v / 30), 1) if (v > 0 and not es_rec) else None
        sobre = bool(not es_rec and valor > 0 and (cob is None or cob > dmax))
        agotado = bool(not es_rec and stock <= 0)
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
            'es_receta': es_rec,
            'ventas_30d': v,
            'agotado': agotado,
            'alerta': al.get('estado') if not es_rec else None,
            'cobertura': float(al['cobertura_dias']) if (not es_rec and al.get('cobertura_dias') is not None) else None,
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
                'productos': f'/catalogo-productos/{nid}',
                'editar': f'/catalogo-productos/{nid}?editar_producto={pid}',
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


def buscar_datos_terceros(conn, q, negocio_id, slug=None, limite=5):
    mapa_docs = _obtener_mapa_tipos_doc(conn, negocio_id)
    """Busca terceros y extrae su radiografia financiera y comercial completa:
    - Rol dinamico (Cliente, Proveedor, Mixto)
    - Cuentas por Cobrar con especificidad (saldo_por_documentos cobro) y saldo contable residual (13%)
    - Cuentas por Pagar con especificidad (saldo_por_documentos pago) y saldo contable residual (22%/23%)
    - Ventas historicas acumuladas (41%)
    - Pedidos pendientes / no facturados (intenciones de compra no cerradas)
    - Notas y observaciones asociadas
    """
    q_limpio = (q or '').strip()
    if len(q_limpio) < 2:
        return []
    try:
        nid = int(negocio_id) if negocio_id else None
    except (TypeError, ValueError):
        nid = None
    
    like = f"%{q_limpio}%"
    rows = []
    try:
        if nid:
            rows = conn.execute("""
                SELECT t.id, t.nombre, t.documento, t.telefono, t.direccion, t.tipo_tercero, t.contacto
                FROM terceros t
                WHERE (t.nombre ILIKE %s OR COALESCE(t.documento, '') ILIKE %s OR COALESCE(t.telefono, '') ILIKE %s)
                  AND (EXISTS (SELECT 1 FROM terceros_negocios tn WHERE tn.tercero_id = t.id AND tn.negocio_id = %s)
                       OR EXISTS (SELECT 1 FROM movimientos_contables mc WHERE mc.tercero_id = t.id AND mc.negocio_id = %s)
                       OR EXISTS (SELECT 1 FROM saldo_por_documentos spd WHERE spd.tercero_id = t.id AND spd.negocio_id = %s)
                       OR EXISTS (SELECT 1 FROM pedidos ped WHERE (ped.id_tercero = t.id OR ped.cliente_id = t.id) AND ped.negocio_id = %s)
                       OR t.tipo_tercero = 'admin')
                ORDER BY (LOWER(t.nombre) = LOWER(%s)) DESC, t.nombre ASC
                LIMIT %s
            """, (like, like, like, nid, nid, nid, nid, q_limpio, limite)).fetchall()
        
        if not rows:
            rows = conn.execute("""
                SELECT t.id, t.nombre, t.documento, t.telefono, t.direccion, t.tipo_tercero, t.contacto
                FROM terceros t
                WHERE (t.nombre ILIKE %s OR COALESCE(t.documento, '') ILIKE %s OR COALESCE(t.telefono, '') ILIKE %s)
                ORDER BY (LOWER(t.nombre) = LOWER(%s)) DESC, t.nombre ASC
                LIMIT %s
            """, (like, like, like, q_limpio, limite)).fetchall()
    except Exception:
        rows = []

    if not rows:
        return []

    terceros_out = []
    for t in rows:
        tid = t['id']
        t_nombre = t['nombre'] or 'Sin nombre'

        # A) Cuentas por Cobrar (CxC):
        docs_cxc = []
        total_cxc_docs = 0.0
        try:
            sql_cxc = """
                SELECT s.id, s.numero_documento, s.monto_original, s.saldo, s.tipo_documento, 
                       TO_CHAR(COALESCE(s.fecha_hora, s.created_at), 'YYYY-MM-DD') AS fecha,
                       s.notas, c.codigo AS cuenta_codigo
                FROM saldo_por_documentos s
                LEFT JOIN cuentas_puc c ON c.id = s.cuenta_id
                WHERE s.tercero_id = %s AND s.saldo > 0
                  AND (c.codigo LIKE '13%' OR s.tipo_documento ILIKE '%cobro%' OR s.tipo_documento ILIKE '%factura%')
            """
            params_cxc = [tid]
            if nid:
                sql_cxc += " AND s.negocio_id = %s"
                params_cxc.append(nid)
            sql_cxc += " ORDER BY s.id DESC LIMIT 5"

            r_cxc = conn.execute(sql_cxc, tuple(params_cxc)).fetchall()
            for d in r_cxc:
                sp = float(d['saldo'] or 0)
                total_cxc_docs += sp
                docs_cxc.append({
                    'id': d['id'],
                    'numero': f"{_formatear_nombre_doc(d.get('tipo_documento'), mapa_docs)} #{d['numero_documento']}" if d.get('numero_documento') else f"{_formatear_nombre_doc(d.get('tipo_documento'), mapa_docs)} #{d['id']}",
                    'total': float(d['monto_original'] or 0),
                    'saldo': sp,
                    'fecha': d['fecha'],
                    'vencimiento': None,
                    'notas': d['notas'] or '',
                    'url': f"/admin/saldos-documentos/{nid or 0}?tercero_id={tid}&doc_id={d['id']}"
                })
        except Exception:
            docs_cxc = []

        saldo_conta_13 = 0.0
        try:
            sql_13 = """
                SELECT COALESCE(SUM(CASE WHEN tipo = 'debito' THEN monto ELSE -monto END), 0) AS saldo
                FROM movimientos_contables
                WHERE tercero_id = %s AND LEFT(cuenta, 2) = '13'
            """
            p_13 = [tid]
            if nid:
                sql_13 += " AND negocio_id = %s"
                p_13.append(nid)
            r13 = conn.execute(sql_13, tuple(p_13)).fetchone()
            if r13:
                saldo_conta_13 = float(r13['saldo'] or 0)
        except Exception:
            saldo_conta_13 = 0.0

        cxc_adicional = max(0.0, round(saldo_conta_13 - total_cxc_docs, 2)) if total_cxc_docs > 0 else max(0.0, round(saldo_conta_13, 2))

        # B) Cuentas por Pagar (CxP):
        docs_cxp = []
        total_cxp_docs = 0.0
        try:
            sql_cxp = """
                SELECT s.id, s.numero_documento, s.monto_original, s.saldo, s.tipo_documento, 
                       TO_CHAR(COALESCE(s.fecha_hora, s.created_at), 'YYYY-MM-DD') AS fecha,
                       s.notas, c.codigo AS cuenta_codigo
                FROM saldo_por_documentos s
                LEFT JOIN cuentas_puc c ON c.id = s.cuenta_id
                WHERE s.tercero_id = %s AND s.saldo > 0
                  AND (c.codigo LIKE '22%' OR c.codigo LIKE '23%' OR s.tipo_documento ILIKE '%pago%' OR s.tipo_documento ILIKE '%egreso%' OR s.tipo_documento ILIKE '%cuenta%pagar%')
            """
            params_cxp = [tid]
            if nid:
                sql_cxp += " AND s.negocio_id = %s"
                params_cxp.append(nid)
            sql_cxp += " ORDER BY s.id DESC LIMIT 5"

            r_cxp = conn.execute(sql_cxp, tuple(params_cxp)).fetchall()
            for d in r_cxp:
                sp = float(d['saldo'] or 0)
                total_cxp_docs += sp
                docs_cxp.append({
                    'id': d['id'],
                    'numero': f"{_formatear_nombre_doc(d.get('tipo_documento'), mapa_docs)} #{d['numero_documento']}" if d.get('numero_documento') else f"{_formatear_nombre_doc(d.get('tipo_documento'), mapa_docs)} #{d['id']}",
                    'total': float(d['monto_original'] or 0),
                    'saldo': sp,
                    'fecha': d['fecha'],
                    'vencimiento': None,
                    'notas': d['notas'] or '',
                    'url': f"/tesoreria/{nid or 0}?tercero_id={tid}&doc_id={d['id']}"
                })
        except Exception:
            docs_cxp = []

        saldo_conta_22_23 = 0.0
        try:
            sql_22 = """
                SELECT COALESCE(SUM(CASE WHEN tipo = 'credito' THEN monto ELSE -monto END), 0) AS saldo
                FROM movimientos_contables
                WHERE tercero_id = %s AND (LEFT(cuenta, 2) = '22' OR LEFT(cuenta, 2) = '23')
            """
            p_22 = [tid]
            if nid:
                sql_22 += " AND negocio_id = %s"
                p_22.append(nid)
            r22 = conn.execute(sql_22, tuple(p_22)).fetchone()
            if r22:
                saldo_conta_22_23 = float(r22['saldo'] or 0)
        except Exception:
            saldo_conta_22_23 = 0.0

        cxp_adicional = max(0.0, round(saldo_conta_22_23 - total_cxp_docs, 2)) if total_cxp_docs > 0 else max(0.0, round(saldo_conta_22_23, 2))

        # C) Ventas Facturadas (Clase 41):
        ventas_total = 0.0
        ventas_cant = 0
        ultima_venta = None
        try:
            sql_v = """
                SELECT COALESCE(SUM(monto), 0) AS total, COUNT(DISTINCT comprobante_id) AS cant,
                       TO_CHAR(MAX(fecha), 'YYYY-MM-DD') AS ult
                FROM movimientos_contables
                WHERE tercero_id = %s AND LEFT(cuenta, 2) = '41' AND tipo = 'credito'
            """
            p_v = [tid]
            if nid:
                sql_v += " AND negocio_id = %s"
                p_v.append(nid)
            rv = conn.execute(sql_v, tuple(p_v)).fetchone()
            if rv:
                ventas_total = float(rv['total'] or 0)
                ventas_cant = int(rv['cant'] or 0)
                ultima_venta = rv['ult']
        except Exception:
            pass

        # D) Pedidos e Intenciones de Compra No Facturados:
        pedidos_pendientes = []
        total_pedidos_pend = 0.0
        try:
            sql_p = """
                SELECT id, total, estado, TO_CHAR(created_at, 'YYYY-MM-DD') AS fecha, notas
                FROM pedidos
                WHERE (id_tercero = %s OR cliente_id = %s OR nombre_cliente ILIKE %s)
                  AND (numero_documento IS NULL OR TRIM(numero_documento) = '')
                  AND LOWER(COALESCE(estado, '')) NOT IN ('facturado', 'completado', 'entregado', 'finalizado', 'anulado', 'pagado')
            """
            p_p = [tid, tid, t_nombre]
            if nid:
                sql_p += " AND negocio_id = %s"
                p_p.append(nid)
            sql_p += " ORDER BY id DESC LIMIT 5"

            rp = conn.execute(sql_p, tuple(p_p)).fetchall()
            for p in rp:
                tot_p = float(p['total'] or 0)
                total_pedidos_pend += tot_p
                pedidos_pendientes.append({
                    'id': p['id'],
                    'total': tot_p,
                    'estado': p['estado'] or 'pendiente',
                    'fecha': p['fecha'],
                    'notas': p['notas'] or '',
                    'url': f"/ventas-costos/{nid or 0}?pedido_id={p['id']}"
                })
        except Exception:
            pass

        # E) Notas registradas vinculadas a este tercero:
        notas_tercero = []
        try:
            sql_nt1 = "SELECT numero_documento AS origen, notas, tipo_documento FROM saldo_por_documentos WHERE tercero_id = %s AND notas IS NOT NULL AND TRIM(notas) <> ''"
            p_nt1 = [tid]
            if nid:
                sql_nt1 += " AND negocio_id = %s"
                p_nt1.append(nid)
            sql_nt1 += " LIMIT 3"
            for nd in conn.execute(sql_nt1, tuple(p_nt1)).fetchall():
                notas_tercero.append({
                    'origen': f"Cartera Doc #{nd['origen'] or ''}",
                    'nota': nd['notas']
                })

            sql_nt2 = "SELECT id AS origen, notas, estado FROM pedidos WHERE (id_tercero = %s OR cliente_id = %s OR nombre_cliente ILIKE %s) AND notas IS NOT NULL AND TRIM(notas) <> ''"
            p_nt2 = [tid, tid, t_nombre]
            if nid:
                sql_nt2 += " AND negocio_id = %s"
                p_nt2.append(nid)
            sql_nt2 += " LIMIT 3"
            for np in conn.execute(sql_nt2, tuple(p_nt2)).fetchall():
                notas_tercero.append({
                    'origen': f"Pedido #{np['origen']} ({np['estado']})",
                    'nota': np['notas']
                })
        except Exception:
            pass

        # E2) Movimientos Contables Generales y Cuentas Vinculadas a este Tercero:
        cuentas_vinculadas = []
        gastos_total = 0.0
        ultimos_movs_tercero = []
        try:
            sql_cg = """
                SELECT mc.cuenta, COALESCE(c.nombre, 'Sin nombre') AS cuenta_nombre,
                       COUNT(*) AS total_movs,
                       SUM(CASE WHEN mc.tipo = 'debito' THEN mc.monto ELSE 0 END) AS debs,
                       SUM(CASE WHEN mc.tipo = 'credito' THEN mc.monto ELSE 0 END) AS creds,
                       SUM(mc.monto) AS total_acumulado
                FROM movimientos_contables mc
                LEFT JOIN cuentas_puc c ON c.codigo = mc.cuenta
                WHERE mc.tercero_id = %s
            """
            p_cg = [tid]
            if nid:
                sql_cg += " AND mc.negocio_id = %s"
                p_cg.append(nid)
            sql_cg += " GROUP BY mc.cuenta, c.nombre ORDER BY total_acumulado DESC LIMIT 5"
            
            r_cg = conn.execute(sql_cg, tuple(p_cg)).fetchall()
            for cg in r_cg:
                c_cod = cg['cuenta'] or ''
                c_tot = float(cg['total_acumulado'] or 0)
                if c_cod.startswith(('5', '6')):
                    gastos_total += float(cg['debs'] or 0)
                cuentas_vinculadas.append({
                    'codigo': c_cod,
                    'nombre': cg['cuenta_nombre'],
                    'movs': int(cg['total_movs'] or 0),
                    'total': c_tot,
                    'url': f"/contabilidad/{nid or 0}?tab=consulta&tercero_id={tid}&tercero_nombre={urllib.parse.quote(t_nombre)}&cuenta={c_cod}&desde=2026-01-01"
                })

            sql_um = """
                SELECT mc.id, TO_CHAR(mc.fecha, 'YYYY-MM-DD') AS fecha, mc.cuenta,
                       COALESCE(c.nombre, '') AS cuenta_nombre, mc.tipo, mc.monto,
                       mc.concepto, mc.tipo_documento, mc.numero_documento, mc.comprobante_id
                FROM movimientos_contables mc
                LEFT JOIN cuentas_puc c ON c.codigo = mc.cuenta
                WHERE mc.tercero_id = %s
            """
            p_um = [tid]
            if nid:
                sql_um += " AND mc.negocio_id = %s"
                p_um.append(nid)
            sql_um += " ORDER BY mc.fecha DESC, mc.id DESC LIMIT 5"
            
            r_um = conn.execute(sql_um, tuple(p_um)).fetchall()
            for um in r_um:
                ultimos_movs_tercero.append({
                    'id': um['id'],
                    'fecha': um['fecha'],
                    'tipo': um['tipo'],
                    'monto': float(um['monto'] or 0),
                    'concepto': (um['concepto'] or '').replace('\r', ' ').replace('\n', ' ').strip(),
                    'cuenta': f"{um['cuenta']} {um['cuenta_nombre']}".strip(),
                    'doc': f"{_formatear_nombre_doc(um.get('tipo_documento'), mapa_docs)} #{um.get('numero_documento') or um['id']}",
                    'comprobante_id': um['comprobante_id']
                })
        except Exception:
            pass

        # F) Deteccion de Rol:
        roles = []
        if total_cxc_docs > 0 or saldo_conta_13 > 0 or ventas_total > 0 or len(pedidos_pendientes) > 0:
            roles.append('Cliente')
        if total_cxp_docs > 0 or saldo_conta_22_23 > 0:
            roles.append('Proveedor')
        if not roles:
            t_tipo = t.get('tipo_tercero') or ''
            roles.append(t_tipo.capitalize() if t_tipo else 'Tercero')

        rol_str = ' / '.join(roles)

        terceros_out.append({
            'id': tid,
            'nombre': t_nombre,
            'negocio_id': nid,
            'identificacion': t.get('documento') or '',
            'telefono': t.get('telefono') or '',
            'email': '',
            'direccion': t.get('direccion') or '',
            'ciudad': '',
            'rol': rol_str,
            'es_cliente': 'Cliente' in roles,
            'es_proveedor': 'Proveedor' in roles,
            'cxc_total': round(total_cxc_docs + cxc_adicional, 2),
            'cxc_docs': docs_cxc,
            'cxc_adicional': cxc_adicional,
            'cxp_total': round(total_cxp_docs + cxp_adicional, 2),
            'cxp_docs': docs_cxp,
            'cxp_adicional': cxp_adicional,
            'ventas_total': ventas_total,
            'ventas_cant': ventas_cant,
            'ultima_venta': ultima_venta,
            'gastos_total': round(gastos_total, 2),
            'cuentas_vinculadas': cuentas_vinculadas,
            'ultimos_movimientos': ultimos_movs_tercero,
            'pedidos_pendientes': pedidos_pendientes,
            'pedidos_pendientes_total': round(total_pedidos_pend, 2),
            'notas': notas_tercero,
            'urls': {
                'saldos': f"/admin/saldos-documentos/{nid or 0}?tercero_id={tid}",
                'tesoreria': f"/tesoreria/{nid or 0}?tercero_id={tid}",
                'unificar': f"/admin/mantenimiento/{nid or 0}?tool=unificar-terceros&tercero_id={tid}",
                'contabilidad_cxp': f"/contabilidad/{nid or 0}?tab=consulta&tercero_id={tid}&tercero_nombre={urllib.parse.quote(t_nombre)}&cuenta=23&desde=2026-01-01",
                'contabilidad_cxc': f"/contabilidad/{nid or 0}?tab=consulta&tercero_id={tid}&tercero_nombre={urllib.parse.quote(t_nombre)}&cuenta=13&desde=2026-01-01",
                'contabilidad_ventas': f"/contabilidad/{nid or 0}?tab=consulta&tercero_id={tid}&tercero_nombre={urllib.parse.quote(t_nombre)}&cuenta=41&desde=2026-01-01"
            }
        })

    return terceros_out


def buscar_datos_notas(conn, q, negocio_id, limite=10):
    mapa_docs = _obtener_mapa_tipos_doc(conn, negocio_id)
    """Busqueda transversal de notas y observaciones en:
    1. Comprobantes contables / Desembolsos (comprobantes_contables.notas)
    2. Cartera / Documentos (saldo_por_documentos.notas)
    3. Pedidos (pedidos.notas)
    """
    q_limpio = (q or '').strip()
    if len(q_limpio) < 2:
        return []
    try:
        nid = int(negocio_id) if negocio_id else None
    except (TypeError, ValueError):
        nid = None
    
    like = f"%{q_limpio}%"
    notas_out = []

    # 1. Comprobantes contables / Desembolsos / Tesoreria
    try:
        # Solo notas humanas reales, excluyendo textos de sistema autogenerados como 'FACTURA_DE_VENTA'
        sql_comp = """
            SELECT id, numero_comprobante, tipo, TO_CHAR(fecha, 'YYYY-MM-DD') AS fecha,
                   descripcion, notas, total_debitos
            FROM comprobantes_contables
            WHERE notas IS NOT NULL AND TRIM(notas) <> ''
              AND notas ILIKE %s
              AND LOWER(TRIM(notas)) NOT IN ('factura_de_venta', 'factura de venta', 'asiento', 'comprobante', 'automatico')
        """
        p_comp = [like]
        if nid:
            sql_comp += " AND negocio_id = %s"
            p_comp.append(nid)
        sql_comp += " ORDER BY id DESC LIMIT 5"
        
        r_comp = conn.execute(sql_comp, tuple(p_comp)).fetchall()
        for c in r_comp:
            t_tipo = (c['tipo'] or '').upper()
            if 'VENTA' in t_tipo or 'FAC' in t_tipo:
                mod_label = 'Ventas / Facturación'
                ico = '🧾'
            elif 'EGRESO' in t_tipo or 'GASTO' in t_tipo or 'DESEMBOLSO' in t_tipo:
                mod_label = 'Tesorería / Desembolsos'
                ico = '💸'
            elif 'CAJA' in t_tipo or 'COBRO' in t_tipo:
                mod_label = 'Caja / Recaudos'
                ico = '🪙'
            elif 'PROD' in t_tipo:
                mod_label = 'Producción'
                ico = '⚙️'
            else:
                mod_label = 'Contabilidad'
                ico = '📄'

            texto_nota = c['notas'] or ''
            notas_out.append({
                'tipo': 'comprobante',
                'origen': f"Comprobante #{c['numero_comprobante'] or c['id']} ({c['tipo'] or 'Asiento'})",
                'modulo': mod_label,
                'icono': ico,
                'fecha': c['fecha'],
                'monto': float(c['total_debitos'] or 0),
                'extracto': texto_nota[:160] + ('...' if len(texto_nota) > 160 else ''),
                'url': f"/contabilidad/{nid or 0}?tab=comps&comp_id={c['id']}"
            })
    except Exception:
        pass

    # 2. Saldo por documentos (Cartera / CxP)
    try:
        sql_doc = """
            SELECT id, numero_documento, tipo_documento, TO_CHAR(COALESCE(fecha_hora, created_at), 'YYYY-MM-DD') AS fecha,
                   saldo, monto_original, notas
            FROM saldo_por_documentos
            WHERE notas ILIKE %s
        """
        p_doc = [like]
        if nid:
            sql_doc += " AND negocio_id = %s"
            p_doc.append(nid)
        sql_doc += " ORDER BY id DESC LIMIT 5"

        r_doc = conn.execute(sql_doc, tuple(p_doc)).fetchall()
        for d in r_doc:
            texto_nota = d['notas'] or ''
            tipo_label = _formatear_nombre_doc(d.get('tipo_documento'), mapa_docs)
            notas_out.append({
                'tipo': 'cartera',
                'origen': f"Documento #{d['numero_documento'] or d['id']} ({tipo_label})",
                'modulo': 'Saldos por Documento',
                'icono': '💳',
                'fecha': d['fecha'],
                'monto': float(d['saldo'] or 0),
                'extracto': texto_nota[:160] + ('...' if len(texto_nota) > 160 else ''),
                'url': f"/admin/saldos-documentos/{nid or 0}?doc_id={d['id']}"
            })
    except Exception:
        pass

    # 3. Pedidos
    try:
        sql_ped = """
            SELECT id, nombre_cliente, estado, TO_CHAR(created_at, 'YYYY-MM-DD') AS fecha,
                   total, notas
            FROM pedidos
            WHERE notas ILIKE %s
        """
        p_ped = [like]
        if nid:
            sql_ped += " AND negocio_id = %s"
            p_ped.append(nid)
        sql_ped += " ORDER BY id DESC LIMIT 5"

        r_ped = conn.execute(sql_ped, tuple(p_ped)).fetchall()
        for p in r_ped:
            texto_nota = p['notas'] or ''
            notas_out.append({
                'tipo': 'pedido',
                'origen': f"Pedido #{p['id']} - {p['nombre_cliente'] or 'Cliente'} ({p['estado']})",
                'modulo': 'Ventas / Pedidos',
                'icono': '📦',
                'fecha': p['fecha'],
                'monto': float(p['total'] or 0),
                'extracto': texto_nota[:160] + ('...' if len(texto_nota) > 160 else ''),
                'url': f"/ventas-costos/{nid or 0}?pedido_id={p['id']}"
            })
    except Exception:
        pass

    return notas_out[:limite]



def buscar_datos_cuentas_puc(conn, q, negocio_id, limite=5):
    mapa_docs = _obtener_mapa_tipos_doc(conn, negocio_id)
    """Busca cuentas contables en el PUC y calcula su saldo neto real acumulado
    segun naturaleza (credito o debito) a partir de movimientos_contables,
    junto con sus ultimos 5 movimientos.
    """
    q_limpio = (q or '').strip()
    if len(q_limpio) < 2:
        return []
    try:
        nid = int(negocio_id) if negocio_id else None
    except (TypeError, ValueError):
        nid = None
    
    like = f"%{q_limpio}%"
    try:
        rows = conn.execute("""
            SELECT c.id, c.codigo, c.nombre, c.naturaleza, c.nivel
            FROM cuentas_puc c
            WHERE (c.codigo ILIKE %s OR c.nombre ILIKE %s) AND c.activo = true
            ORDER BY (LOWER(c.codigo) = LOWER(%s) OR LOWER(c.nombre) = LOWER(%s)) DESC, c.codigo ASC
            LIMIT %s
        """, (like, like, q_limpio, q_limpio, limite)).fetchall()
    except Exception:
        return []

    cuentas_out = []
    for c in rows:
        cod = c['codigo']
        c_nom = c['nombre'] or 'Sin nombre'
        c_nat = (c['naturaleza'] or 'debito').lower()

        debs = 0.0
        creds = 0.0
        tot_movs = 0
        movimientos = []
        if nid:
            try:
                r_bal = conn.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN tipo = 'debito' THEN monto ELSE 0 END), 0) AS debs,
                        COALESCE(SUM(CASE WHEN tipo = 'credito' THEN monto ELSE 0 END), 0) AS creds,
                        COUNT(*) AS cnt
                    FROM movimientos_contables
                    WHERE negocio_id = %s AND (cuenta = %s OR cuenta LIKE %s)
                """, (nid, cod, f"{cod}%")).fetchone()
                if r_bal:
                    debs = float(r_bal['debs'] or 0)
                    creds = float(r_bal['creds'] or 0)
                    tot_movs = int(r_bal['cnt'] or 0)
            except Exception:
                pass

            try:
                r_movs = conn.execute("""
                    SELECT mc.id, TO_CHAR(mc.fecha, 'YYYY-MM-DD') AS fecha, mc.tipo, mc.monto,
                           mc.concepto, mc.numero_documento, mc.tipo_documento,
                           t.nombre AS tercero_nombre
                    FROM movimientos_contables mc
                    LEFT JOIN terceros t ON t.id = mc.tercero_id
                    WHERE negocio_id = %s AND (cuenta = %s OR cuenta LIKE %s)
                    ORDER BY mc.fecha DESC, mc.id DESC
                    LIMIT 5
                """, (nid, cod, f"{cod}%")).fetchall()
                for m in r_movs:
                    movimientos.append({
                        'id': m['id'],
                        'fecha': m['fecha'],
                        'tipo': m['tipo'],
                        'monto': float(m['monto'] or 0),
                        'concepto': (m['concepto'] or '').replace('\r', ' ').replace('\n', ' ').strip(),
                        'doc': f"{_formatear_nombre_doc(m.get('tipo_documento'), mapa_docs)} #{m.get('numero_documento') or m['id']}",
                        'tercero': m['tercero_nombre'] or ''
                    })
            except Exception:
                pass

        es_cred = (c_nat == 'credito') or (cod.startswith(('2', '3', '4')))
        saldo = (creds - debs) if es_cred else (debs - creds)

        cuentas_out.append({
            'id': c['id'],
            'codigo': cod,
            'nombre': c_nom,
            'naturaleza': 'Crédito' if es_cred else 'Débito',
            'saldo': round(saldo, 2),
            'debitos': round(debs, 2),
            'creditos': round(creds, 2),
            'total_movimientos': tot_movs,
            'ultimos_movimientos': movimientos,
            'url': f"/contabilidad/{nid or 0}?tab=consulta&cuenta={cod}&cuenta_id={c['id']}&desde=2026-01-01"
        })

    return cuentas_out


def buscar_datos_tipos_doc(conn, q, negocio_id, limite=5):
    """Busca tipos de documento configurados para el negocio (tipos_documento_negocio)."""
    q_limpio = (q or '').strip()
    if len(q_limpio) < 2:
        return []
    try:
        nid = int(negocio_id) if negocio_id else None
    except (TypeError, ValueError):
        nid = None
    
    like = f"%{q_limpio}%"
    try:
        sql = """
            SELECT id, codigo, nombre, tipo_movimiento, mueve_inventario, consecutivo, numero_inicio
            FROM tipos_documento_negocio
            WHERE activo = true AND (codigo ILIKE %s OR nombre ILIKE %s)
        """
        params = [like, like]
        if nid:
            sql += " AND negocio_id = %s"
            params.append(nid)
        sql += " ORDER BY (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s)) DESC, nombre ASC LIMIT %s"
        params.extend([q_limpio, q_limpio, limite])
        
        rows = conn.execute(sql, tuple(params)).fetchall()
        tipos_out = []
        for r in rows:
            tipos_out.append({
                'id': r['id'],
                'codigo': r['codigo'],
                'nombre': r['nombre'],
                'tipo_movimiento': r['tipo_movimiento'] or 'Operativo',
                'mueve_inventario': bool(r['mueve_inventario']),
                'consecutivo': r['consecutivo'] or 0,
                'proximo_numero': (r['consecutivo'] or 0) + 1,
                'url': f"/contabilidad/{nid or 0}?tab=tipos_doc"
            })
        return tipos_out
    except Exception:
        return []
