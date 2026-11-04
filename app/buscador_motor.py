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


def buscar_omni(q, negocio_id=None, slug=None, otorgados=None, filas=None, manuales_otorgados=None):
    q_limpio = (q or '').strip()
    q_norm = quitar_tildes(q_limpio)
    
    rutas_base = _obtener_catalogo_base(negocio_id=negocio_id, slug=slug, otorgados=otorgados, filas=filas)
    secciones_manuales = _cargar_indice_manuales()

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
        if manuales_otorgados is not None and item.get('slug') not in manuales_otorgados:
            continue
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
        a.pop('slug', None)

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
