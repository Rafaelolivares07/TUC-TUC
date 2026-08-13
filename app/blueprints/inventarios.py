from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from ..db import get_db_connection
from decimal import Decimal
from datetime import date

try:
    from .contabilidad import _ejecutar_asiento_costo_mov as _asiento_costo_mov
    from .contabilidad import _ejecutar_asiento_produccion as _asiento_produccion
    from .contabilidad import _ejecutar_asiento_automatico as _asiento_auto
    from .contabilidad import obtener_siguiente_consecutivo
    from .contabilidad import _verificar_periodo_cerrado
except ImportError:
    _asiento_costo_mov = None
    _asiento_produccion = None
    _asiento_auto = None
    def obtener_siguiente_consecutivo(*args, **kwargs):
        return None, True
    def _verificar_periodo_cerrado(*args, **kwargs):
        pass

bp = Blueprint('inventarios', __name__)

_tablas_listas = False


def _crear_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return
    sqls = [
        """CREATE TABLE IF NOT EXISTS productos (
            id          SERIAL PRIMARY KEY,
            negocio_id  INTEGER NOT NULL,
            nombre      VARCHAR(255) NOT NULL,
            categoria   VARCHAR(100),
            precio      DECIMAL(10,2) DEFAULT 0,
            costo       DECIMAL(10,2) DEFAULT 0,
            imagen      TEXT,
            descripcion TEXT,
            codigo_barra VARCHAR(50),
            iva_pct     NUMERIC(5,2) DEFAULT 0,
            disponible  BOOLEAN DEFAULT TRUE,
            orden       INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS tarjeta_estandar (
            id           SERIAL PRIMARY KEY,
            producto_id  INTEGER NOT NULL REFERENCES productos(id),
            componente_id INTEGER NOT NULL REFERENCES productos(id),
            cantidad     NUMERIC(12,4) NOT NULL DEFAULT 1,
            UNIQUE(producto_id, componente_id)
        )""",
        """CREATE TABLE IF NOT EXISTS saldos_inventario (
            id                SERIAL PRIMARY KEY,
            negocio_id        INTEGER NOT NULL,
            producto_id       INTEGER NOT NULL REFERENCES productos(id),
            bodega            INTEGER NOT NULL DEFAULT 1,
            stock             NUMERIC(12,4) DEFAULT 0,
            costo_und         NUMERIC(12,4) DEFAULT 0,
            valor_existencia  NUMERIC(14,2) DEFAULT 0,
            updated_at        TIMESTAMP DEFAULT NOW(),
            UNIQUE(negocio_id, producto_id, bodega)
        )""",
        """CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id               SERIAL PRIMARY KEY,
            negocio_id       INTEGER NOT NULL,
            producto_id      INTEGER NOT NULL,
            nombre_producto  VARCHAR(255),
            tipo             VARCHAR(20) NOT NULL,
            motivo           VARCHAR(50),
            cantidad         NUMERIC(12,4) NOT NULL,
            stock_anterior   NUMERIC(12,4),
            stock_nuevo      NUMERIC(12,4),
            registrado_por   INTEGER,
            notas            TEXT,
            valor_unitario   NUMERIC(14,4),
            valor_total      NUMERIC(14,4),
            costo_und        NUMERIC(12,4),
            referencia_id    INTEGER,
            referencia_tipo  VARCHAR(50),
            created_at       TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS presentaciones (
            id           SERIAL PRIMARY KEY,
            nombre       VARCHAR(100) NOT NULL,
            equivalencia NUMERIC(14,4) NOT NULL DEFAULT 1.0,
            created_at   TIMESTAMP DEFAULT NOW()
        )""",
    ]
    for sql in sqls:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    alters = [
        "CREATE INDEX IF NOT EXISTS idx_productos_negocio ON productos(negocio_id)",
        "CREATE INDEX IF NOT EXISTS idx_tarjeta_producto ON tarjeta_estandar(producto_id)",
        "CREATE INDEX IF NOT EXISTS idx_saldos_negocio_producto ON saldos_inventario(negocio_id, producto_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_presentaciones_unique ON presentaciones(LOWER(nombre), equivalencia)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS presentacion_id INTEGER REFERENCES presentaciones(id)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS costo_und NUMERIC(12,4)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(50)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS documento_numero VARCHAR(80)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS documento_fecha DATE",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS proveedor_id INTEGER REFERENCES terceros(id)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS proveedor_nombre VARCHAR(255)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS producto_padre_id INTEGER REFERENCES productos(id)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS iva_total NUMERIC(14,2)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS documento_total NUMERIC(14,2)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS iva_pct NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS iva_valor NUMERIC(14,2) DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS recargo DECIMAL(10,2) DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS catalogo_id INTEGER",
        "ALTER TABLE comprobantes_contables ADD COLUMN IF NOT EXISTS origen_tipo VARCHAR(50)",
        "ALTER TABLE comprobantes_contables ADD COLUMN IF NOT EXISTS origen_id VARCHAR(100)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE movimientos_inventario ALTER COLUMN valor_unitario TYPE NUMERIC(16,6)",
        "ALTER TABLE movimientos_inventario ALTER COLUMN costo_und TYPE NUMERIC(16,6)",
        "ALTER TABLE saldos_inventario ALTER COLUMN costo_und TYPE NUMERIC(16,6)",
        "ALTER TABLE productos ALTER COLUMN costo TYPE NUMERIC(16,6)",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # Migrar productos_tienda → productos si la tabla origen existe y aún no se migró
    try:
        conn.execute("""
            INSERT INTO productos (id, negocio_id, nombre, categoria, precio, costo,
                                   imagen, descripcion, codigo_barra, iva_pct,
                                   disponible, orden, created_at)
            SELECT pt.id, t.tercero_id, pt.nombre, pt.categoria, pt.precio, 0,
                   pt.imagen, pt.descripcion, pt.codigo_barra, COALESCE(pt.iva_pct, 0),
                   pt.disponible, pt.orden, pt.created_at
            FROM productos_tienda pt
            JOIN tiendas t ON t.id = pt.tienda_id
            WHERE t.tercero_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        # Migrar stock actual a saldos_inventario
        conn.execute("""
            INSERT INTO saldos_inventario (negocio_id, producto_id, bodega, stock)
            SELECT t.tercero_id, pt.id, 1, COALESCE(pt.stock, 0)
            FROM productos_tienda pt
            JOIN tiendas t ON t.id = pt.tienda_id
            WHERE t.tercero_id IS NOT NULL AND COALESCE(pt.stock, 0) > 0
            ON CONFLICT DO NOTHING
        """)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    _tablas_listas = True


def _txt(value):
    value = str(value or '').strip()
    return value or None


def _dec(value, default='0'):
    try:
        return Decimal(str(value if value not in (None, '') else default))
    except Exception:
        return Decimal(default)


def _int_o_none(value):
    try:
        return int(value) if value not in (None, '') else None
    except Exception:
        return None


def _fecha_o_none(value):
    value = _txt(value)
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return None


def _negocio_id_tienda(conn, slug):
    row = conn.execute(
        "SELECT tercero_id FROM tiendas WHERE slug = %s AND activo = TRUE",
        (slug,)
    ).fetchone()
    if not row:
        return None, 'Tienda no encontrada'
    if not row['tercero_id']:
        return None, 'La tienda no tiene tercero_id asociado para inventario'
    return row['tercero_id'], None


def _contexto_negocio(conn, negocio_id):
    negocio = conn.execute(
        "SELECT nombre FROM terceros WHERE id = %s", (negocio_id,)
    ).fetchone()
    if not negocio:
        return None

    tienda = conn.execute(
        "SELECT slug, nombre, admin_id FROM tiendas WHERE tercero_id = %s AND activo = TRUE LIMIT 1",
        (negocio_id,)
    ).fetchone()
    restaurante = None
    if not tienda:
        restaurante = conn.execute(
            "SELECT slug, nombre, admin_id FROM restaurantes WHERE tercero_id = %s AND activo = TRUE LIMIT 1",
            (negocio_id,)
        ).fetchone()

    volver_url = '/admin'
    volver_label = 'Admin'
    admin_id = None
    if tienda:
        volver_url = f"/admin/tienda/{tienda['slug']}"
        volver_label = tienda['nombre'] or 'Tienda'
        admin_id = tienda['admin_id']
    elif restaurante:
        volver_url = f"/admin/restaurante/{restaurante['slug']}"
        volver_label = restaurante['nombre'] or 'Restaurante'
        admin_id = restaurante['admin_id']

    return {
        'negocio_nombre': negocio['nombre'],
        'volver_url': volver_url,
        'volver_label': volver_label,
        'admin_id': admin_id,
    }


def _mismo_id(a, b):
    try:
        return int(a) == int(b)
    except Exception:
        return False


def _puede_gestionar_negocio(contexto):
    usuario_id = session.get('usuario_id')
    rol = session.get('rol')
    nombre = session.get('nombre')
    return (
        rol == 'Administrador'
        or nombre == 'Rafael Olivares'
        or usuario_id == 1
        or (usuario_id and contexto.get('admin_id') and _mismo_id(usuario_id, contexto['admin_id']))
    )


def _validar_negocio_json(conn, negocio_id):
    contexto = _contexto_negocio(conn, negocio_id)
    if not contexto:
        return None, (jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404)
    if not _puede_gestionar_negocio(contexto):
        return None, (jsonify({'ok': False, 'error': 'No autorizado para este negocio'}), 403)
    return contexto, None


def _negocio_id_de_producto(conn, producto_id):
    row = conn.execute(
        "SELECT negocio_id FROM productos WHERE id = %s",
        (producto_id,)
    ).fetchone()
    return row['negocio_id'] if row else None


def _es_ensamble(conn, producto_id):
    """Retorna True si el producto tiene componentes distintos a sí mismo."""
    rows = conn.execute(
        "SELECT componente_id FROM tarjeta_estandar WHERE producto_id = %s",
        (producto_id,)
    ).fetchall()
    if not rows:
        return False
    return any(r['componente_id'] != producto_id for r in rows)


def _componentes_de(conn, producto_id):
    """Retorna lista de componentes con nombre, para mensajes al usuario."""
    return conn.execute("""
        SELECT p.id, p.nombre, te.cantidad
        FROM tarjeta_estandar te
        JOIN productos p ON p.id = te.componente_id
        WHERE te.producto_id = %s
    """, (producto_id,)).fetchall()


def _mov_directo(conn, negocio_id, producto_id, cantidad, tipo, motivo,
                 registrado_por, valor_unitario=None, notas=None, bodega=1,
                 referencia_id=None, referencia_tipo=None,
                 tipo_documento=None, documento_numero=None,
                 documento_fecha=None, proveedor_id=None,
                 proveedor_nombre=None, iva_total=None,
                 documento_total=None, iva_pct=None, iva_valor=None,
                 producto_padre_id=None, presentacion_id=None,
                 metodo_pago=None, tipo_documento_id=None):
    """Movimiento directo sobre un producto, sin pasar por tarjeta estándar."""
    signo  = Decimal('1') if tipo == 'entrada' else Decimal('-1')
    cantidad = Decimal(str(cantidad))

    saldo = conn.execute(
        "SELECT stock, costo_und, valor_existencia FROM saldos_inventario "
        "WHERE negocio_id=%s AND producto_id=%s AND bodega=%s",
        (negocio_id, producto_id, bodega)
    ).fetchone()

    stock_ant   = Decimal(str(saldo['stock']))            if saldo else Decimal('0')
    costo_ant   = Decimal(str(saldo['costo_und']))        if saldo else Decimal('0')
    val_exi_ant = Decimal(str(saldo['valor_existencia'])) if saldo else Decimal('0')

    stock_nuevo = stock_ant + cantidad * signo

    if tipo == 'entrada' and valor_unitario is not None:
        vu = Decimal(str(valor_unitario))
        costo_nuevo   = (val_exi_ant + cantidad * vu) / stock_nuevo if stock_nuevo > 0 else vu
        val_exi_nuevo = stock_nuevo * costo_nuevo if stock_nuevo > 0 else Decimal('0')
    else:
        costo_nuevo   = costo_ant if stock_nuevo > 0 else Decimal('0')
        val_exi_nuevo = stock_nuevo * costo_nuevo if stock_nuevo > 0 else Decimal('0')

    # Guardar costo de valoración del movimiento (evitando costo cero cuando cae a stock 0)
    costo_registro = costo_nuevo if (tipo == 'entrada' or stock_nuevo > 0) else costo_ant

    nombre_prod = conn.execute("SELECT nombre FROM productos WHERE id=%s", (producto_id,)).fetchone()

    conn.execute("""
        INSERT INTO movimientos_inventario
            (negocio_id, producto_id, nombre_producto, tipo, motivo,
             cantidad, stock_anterior, stock_nuevo, registrado_por, notas,
             valor_unitario, valor_total, costo_und, referencia_id, referencia_tipo,
             tipo_documento, documento_numero, documento_fecha, proveedor_id,
             proveedor_nombre, iva_total, documento_total, iva_pct, iva_valor,
             producto_padre_id, presentacion_id, metodo_pago, tipo_documento_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        negocio_id, producto_id,
        nombre_prod['nombre'] if nombre_prod else '',
        tipo, motivo,
        float(cantidad), float(stock_ant), float(stock_nuevo),
        registrado_por, notas,
        float(valor_unitario) if valor_unitario else None,
        float(cantidad * Decimal(str(valor_unitario))) if valor_unitario else None,
        float(costo_registro),
        referencia_id, referencia_tipo,
        tipo_documento, documento_numero, documento_fecha, proveedor_id,
        proveedor_nombre,
        float(iva_total) if iva_total is not None else None,
        float(documento_total) if documento_total is not None else None,
        float(iva_pct) if iva_pct is not None else 0.0,
        float(iva_valor) if iva_valor is not None else 0.0,
        producto_padre_id, presentacion_id, metodo_pago, tipo_documento_id
    ))

    if saldo:
        conn.execute("""
            UPDATE saldos_inventario
            SET stock=%s, costo_und=%s, valor_existencia=%s, updated_at=NOW()
            WHERE negocio_id=%s AND producto_id=%s AND bodega=%s
        """, (float(stock_nuevo), float(costo_nuevo), float(val_exi_nuevo),
              negocio_id, producto_id, bodega))
    else:
        conn.execute("""
            INSERT INTO saldos_inventario (negocio_id, producto_id, bodega, stock, costo_und, valor_existencia)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (negocio_id, producto_id, bodega,
              float(stock_nuevo), float(costo_nuevo), float(val_exi_nuevo)))

    # Actualizar también el costo base del producto
    conn.execute("""
        UPDATE productos SET costo=%s WHERE id=%s AND negocio_id=%s
    """, (float(costo_nuevo), producto_id, negocio_id))




def _verificar_stock_pedido(conn, negocio_id, items, excluir_componentes=None):
    """
    Verifica si hay stock suficiente en bodega 1 para procesar los items del pedido.
    excluir_componentes: lista de diccionarios/objetos [{'producto_id': ID, 'componente_id': ID}] 
                         que representa las exclusiones de la opción 4.
    Retorna: lista de diccionarios con los insumos/productos faltantes.
    """
    from decimal import Decimal
    
    required_map = {}
    exclusions_set = {}
    if excluir_componentes:
        for exc in excluir_componentes:
            pid = int(exc.get('producto_id') or 0)
            cid = int(exc.get('componente_id') or 0)
            if pid and cid:
                if pid not in exclusions_set:
                    exclusions_set[pid] = set()
                exclusions_set[pid].add(cid)

    for item in items:
        prod_id = int(item.get('producto_id') or 0)
        cantidad = Decimal(str(item.get('cantidad') or 1))
        
        prod_row = conn.execute("SELECT nombre FROM productos WHERE id = %s AND negocio_id = %s", (prod_id, negocio_id)).fetchone()
        prod_name = prod_row['nombre'] if prod_row else f"Producto #{prod_id}"
        
        componentes = conn.execute(
            "SELECT componente_id, cantidad FROM tarjeta_estandar WHERE producto_id = %s",
            (prod_id,)
        ).fetchall()
        
        if not componentes:
            componentes = [{'componente_id': prod_id, 'cantidad': Decimal('1')}]
            
        for comp in componentes:
            comp_id = comp['componente_id']
            if prod_id in exclusions_set and comp_id in exclusions_set[prod_id]:
                continue
                
            qty_needed = Decimal(str(comp['cantidad'])) * cantidad
            
            if comp_id not in required_map:
                required_map[comp_id] = {'requerido': Decimal('0'), 'final_products': []}
            
            required_map[comp_id]['requerido'] += qty_needed
            if not any(fp['id'] == prod_id for fp in required_map[comp_id]['final_products']):
                required_map[comp_id]['final_products'].append({
                    'id': prod_id,
                    'nombre': prod_name if comp_id != prod_id else "Venta Directa"
                })

    shortages = []
    for comp_id, info in required_map.items():
        req_qty = info['requerido']
        if req_qty <= 0:
            continue
            
        saldo = conn.execute(
            "SELECT stock FROM saldos_inventario WHERE negocio_id = %s AND producto_id = %s AND bodega = 1",
            (negocio_id, comp_id)
        ).fetchone()
        
        stock_disp = Decimal(str(saldo['stock'] if saldo else 0.0))
        
        if stock_disp < req_qty:
            comp_row = conn.execute("SELECT nombre, costo FROM productos WHERE id = %s AND negocio_id = %s", (comp_id, negocio_id)).fetchone()
            comp_name = comp_row['nombre'] if comp_row else f"Insumo #{comp_id}"
            
            last_mov = conn.execute("""
                SELECT valor_unitario FROM movimientos_inventario 
                WHERE negocio_id = %s AND producto_id = %s AND tipo = 'entrada' 
                ORDER BY id DESC LIMIT 1
            """, (negocio_id, comp_id)).fetchone()
            
            last_cost = float(last_mov['valor_unitario'] if last_mov and last_mov['valor_unitario'] is not None else (comp_row['costo'] if comp_row and comp_row['costo'] is not None else 0.0))
            
            shortages.append({
                'producto_id': comp_id,
                'nombre': comp_name,
                'requerido': float(req_qty),
                'disponible': float(stock_disp),
                'ultimo_costo': last_cost,
                'es_receta': any(fp['nombre'] != "Venta Directa" for fp in info['final_products']),
                'final_products': info['final_products'],
                'producto_final_nombre': ", ".join(fp['nombre'] for fp in info['final_products'])
            })
            
    return shortages


def _aplicar_tarjeta(conn, negocio_id, producto_id, cantidad, tipo, motivo,
                     registrado_por, valor_unitario=None, notas=None, bodega=1,
                     referencia_id=None, referencia_tipo=None,
                     tipo_documento=None, documento_numero=None,
                     documento_fecha=None, proveedor_id=None,
                     proveedor_nombre=None, iva_total=None,
                     documento_total=None, iva_pct=None, iva_valor=None,
                     presentacion_id=None, metodo_pago=None, tipo_documento_id=None,
                     excluir_componentes_ids=None):
    """Aplica entrada o salida según tarjeta estándar. Sin tarjeta → 1:1 sobre sí mismo."""
    componentes = conn.execute(
        "SELECT componente_id, cantidad FROM tarjeta_estandar WHERE producto_id = %s",
        (producto_id,)
    ).fetchall()

    if not componentes:
        componentes = [{'componente_id': producto_id, 'cantidad': Decimal('1')}]

    cantidad = Decimal(str(cantidad))
    excluded_set = set(excluir_componentes_ids or [])

    for comp in componentes:
        comp_id = comp['componente_id']
        if comp_id in excluded_set:
            continue
            
        cant_comp = Decimal(str(comp['cantidad'])) * cantidad
        padre_id = producto_id if comp['componente_id'] != producto_id else None
        pres_id = presentacion_id if comp['componente_id'] == producto_id else None
        _mov_directo(conn, negocio_id, comp['componente_id'], cant_comp, tipo, motivo,
                     registrado_por, valor_unitario, notas, bodega,
                     referencia_id, referencia_tipo, tipo_documento,
                     documento_numero, documento_fecha, proveedor_id,
                     proveedor_nombre, iva_total, documento_total,
                     iva_pct, iva_valor, producto_padre_id=padre_id,
                     presentacion_id=pres_id, metodo_pago=metodo_pago,
                     tipo_documento_id=tipo_documento_id)


def _registrar_entrada_inventario(conn, negocio_id, data, usuario_id):
    from datetime import datetime
    lineas = data.get('lineas', [])
    motivo = data.get('motivo', 'compra')
    notas = _txt(data.get('notes') or data.get('notas'))
    if not lineas:
        return {'ok': False, 'error': 'Debe agregar al menos una linea'}, 400

    metodo_pago = (_txt(data.get('metodo_pago')) or 'efectivo').lower()

    # Resolve document type ID
    tipo_doc_id = _int_o_none(data.get('tipo_documento_id') or data.get('tipo_documento'))
    if not tipo_doc_id:
        tipo_str = (_txt(data.get('tipo_documento') or data.get('tipo_documento_id')) or 'otro').strip()
        td_row = conn.execute("""
            SELECT id FROM tipos_documento_negocio
            WHERE negocio_id = %s AND (UPPER(nombre) = %s OR UPPER(codigo) = %s)
            LIMIT 1
        """, (negocio_id, tipo_str.upper(), tipo_str.upper())).fetchone()
        if td_row:
            tipo_doc_id = td_row['id']

    td = None
    if tipo_doc_id:
        td = conn.execute("""
            SELECT id, nombre, es_interno 
            FROM tipos_documento_negocio
            WHERE negocio_id = %s AND id = %s
        """, (negocio_id, tipo_doc_id)).fetchone()

    es_interno = td['es_interno'] if (td and td['es_interno'] is not None) else True
    tipo_documento = td['nombre'] if td else 'OTRO'
    documento_numero = (_txt(data.get('documento_numero') or data.get('numero_documento')) or '').strip().upper()
    es_modificacion = bool(data.get('es_modificacion', False))

    if not es_modificacion:
        res_num, es_interno_actual = obtener_siguiente_consecutivo(conn, negocio_id, tipo_doc_id or tipo_documento)
        if es_interno:
            if res_num:
                documento_numero = res_num
            else:
                documento_numero = f"ENT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        else:
            # Documento Externo: Número es obligatorio
            if not documento_numero:
                return {'ok': False, 'error': f'El número de documento es obligatorio para el tipo de documento externo {tipo_documento}.'}, 400
    else:
        if not documento_numero:
            return {'ok': False, 'error': 'El número de documento es requerido para realizar la modificación.'}, 400

    documento_fecha = _fecha_o_none(data.get('documento_fecha') or data.get('fecha_documento'))
    proveedor_id = _int_o_none(data.get('proveedor_id') or data.get('tercero_id'))
    proveedor_nombre = _txt(data.get('proveedor_nombre'))
    subtotal_compra = Decimal('0')
    iva_total = Decimal('0')
    advertencias = []

    # Strict validation: provider ID is required and must exist
    if not proveedor_id:
        return {'ok': False, 'error': 'Debe seleccionar un proveedor de la lista o crearlo antes de continuar'}, 400

    prov = conn.execute(
        "SELECT nombre FROM terceros WHERE id = %s",
        (proveedor_id,)
    ).fetchone()
    if not prov:
        return {'ok': False, 'error': 'Proveedor no encontrado'}, 400
    proveedor_nombre = prov['nombre']
    # Validation check: if it is external, check for duplicates and prevent registration
    if not es_interno and tipo_doc_id and documento_numero and proveedor_id:
        num_variants = resolver_variantes_numero(documento_numero)
        
        existing_movs = conn.execute("""
            SELECT id, producto_id FROM movimientos_inventario
            WHERE negocio_id = %s AND tipo = 'entrada' AND (
                (tipo_documento_id = %s AND documento_numero = %s AND proveedor_id = %s)
                OR (documento_numero IN %s)
            )
        """, (negocio_id, tipo_doc_id, documento_numero, proveedor_id, tuple(num_variants))).fetchall()
        
        existing_saldo = conn.execute("""
            SELECT 1 FROM saldo_por_documentos
            WHERE negocio_id = %s AND (
                (tercero_id = %s AND tipo_documento_id = %s AND numero_documento = %s)
                OR (numero_documento IN %s)
            )
            LIMIT 1
        """, (negocio_id, proveedor_id, tipo_doc_id, documento_numero, tuple(num_variants))).fetchone()
        
        if existing_movs or existing_saldo:
            if es_modificacion:
                # ── VOID/DELETE PREVIOUS ENTRIES BEFORE REGISTERING ──
                prod_ids_to_recost = list({m['producto_id'] for m in existing_movs})
                mov_ids = [m['id'] for m in existing_movs]
                
                # 1. Delete inventory movements
                if mov_ids:
                    placeholders = ','.join(['%s'] * len(mov_ids))
                    conn.execute(f"DELETE FROM movimientos_inventario WHERE id IN ({placeholders})", tuple(mov_ids))
                    
                # 2. Delete pending balance record
                conn.execute("""
                    DELETE FROM saldo_por_documentos
                    WHERE negocio_id = %s AND (
                        numero_documento IN %s
                        OR (tercero_id = %s AND numero_documento IN %s)
                    )
                """, (negocio_id, tuple(num_variants), proveedor_id, tuple(num_variants)))
                
                # 3. Delete cotizaciones
                conn.execute("""
                    DELETE FROM cotizaciones_compras
                    WHERE negocio_id = %s AND (numero_cotizacion IN %s OR (tercero_id = %s AND numero_cotizacion = %s)) AND origen = 'compra'
                """, (negocio_id, tuple(num_variants), proveedor_id, documento_numero))
                
                # 4. Delete accounting vouchers
                origen_ids = [f"{tipo_documento}:{v}" for v in num_variants]
                if tipo_doc_id == 1:
                    for name in ['Factura de Proveedor', 'Factura Proveedor', 'Factura', 'FACTURA']:
                        for v in num_variants:
                            origen_ids.append(f"{name}:{v}")
                
                comp_rows = conn.execute("""
                    SELECT id FROM comprobantes_contables
                    WHERE negocio_id = %s AND (
                        (origen_tipo IS NOT NULL AND LOWER(origen_id) IN %s)
                        OR (numero_comprobante IN %s)
                    )
                """, (negocio_id, tuple(o.lower() for o in origen_ids), tuple(num_variants))).fetchall()
                
                comp_ids = [c['id'] for c in comp_rows]
                if comp_ids:
                    placeholders = ','.join(['%s'] * len(comp_ids))
                    conn.execute(f"DELETE FROM movimientos_contables WHERE comprobante_id IN ({placeholders})", tuple(comp_ids))
                    conn.execute(f"DELETE FROM comprobantes_contables WHERE id IN ({placeholders})", tuple(comp_ids))
                
                # Save products to recostear at the end
                data['_prod_ids_to_recost'] = prod_ids_to_recost
            else:
                return {'ok': False, 'error': f'El documento {tipo_documento} N° {documento_numero} ya está registrado para este proveedor.'}, 400
    # Primer ciclo: validación y cálculo de subtotales e IVA acumulado
    lineas_procesadas = []
    for ln in lineas:
        prod_id = int(ln['producto_id'])
        prod = conn.execute(
            "SELECT nombre FROM productos WHERE id=%s AND negocio_id=%s",
            (prod_id, negocio_id)
        ).fetchone()
        if not prod:
            return {'ok': False, 'error': f'Producto {prod_id} no pertenece al negocio'}, 400
        if _es_ensamble(conn, prod_id):
            comps = _componentes_de(conn, prod_id)
            nombres = ', '.join(f"{c['nombre']} x{c['cantidad']}" for c in comps)
            return {
                'ok': False,
                'error': f'"{prod["nombre"]}" es un ensamble - no se puede comprar directamente. '
                         f'Compre sus componentes: {nombres}'
            }, 400

        pres_id = _int_o_none(ln.get('presentacion_id'))
        pres_nombre = _txt(ln.get('presentacion_nombre') or ln.get('presentacion') or ln.get('descripcion_presentacion'))
        try:
            pres_equiv = Decimal(str(ln.get('presentacion_equivalencia') or ln.get('unidades_item') or 1.0))
        except Exception:
            pres_equiv = Decimal('1.0')

        if not pres_id and pres_nombre:
            existente_pres = conn.execute("""
                SELECT id FROM presentaciones
                WHERE LOWER(nombre) = LOWER(%s) AND equivalencia = %s
                LIMIT 1
            """, (pres_nombre, float(pres_equiv))).fetchone()
            if existente_pres:
                pres_id = existente_pres['id']
            else:
                row_pres = conn.execute("""
                    INSERT INTO presentaciones (nombre, equivalencia)
                    VALUES (%s, %s)
                    RETURNING id
                """, (pres_nombre, float(pres_equiv))).fetchone()
                pres_id = row_pres['id']

        if not pres_id:
            existente_default = conn.execute("""
                SELECT id FROM presentaciones
                WHERE LOWER(nombre) = 'unidad' AND equivalencia = 1.0
                LIMIT 1
            """, ()).fetchone()
            if existente_default:
                pres_id = existente_default['id']
                pres_nombre = 'Unidad'
                pres_equiv = Decimal('1.0')
            else:
                row_pres = conn.execute("""
                    INSERT INTO presentaciones (nombre, equivalencia)
                    VALUES ('Unidad', 1.0)
                    RETURNING id
                """).fetchone()
                pres_id = row_pres['id']
                pres_nombre = 'Unidad'
                pres_equiv = Decimal('1.0')
        else:
            r_p = conn.execute("SELECT nombre, equivalencia FROM presentaciones WHERE id=%s", (pres_id,)).fetchone()
            if r_p:
                pres_nombre = r_p['nombre']
                pres_equiv = Decimal(str(r_p['equivalencia']))

        cant = _dec(ln.get('cantidad'))
        vu = _dec(ln.get('valor_unitario'))
        iva_pct = _dec(ln.get('iva_pct') or '0')

        line_subtotal = cant * vu
        line_iva_val = line_subtotal * (iva_pct / Decimal('100'))

        subtotal_compra += line_subtotal
        iva_total += line_iva_val

        lineas_procesadas.append({
            'producto_id': prod_id,
            'cantidad': cant,
            'valor_unitario': vu,
            'iva_pct': iva_pct,
            'iva_valor': line_iva_val,
            'presentacion_id': pres_id,
            'presentacion_nombre': pres_nombre,
            'presentacion_equivalencia': pres_equiv
        })

    documento_total = subtotal_compra + iva_total

    # Segundo ciclo: registrar movimientos
    for ln in lineas_procesadas:
        _aplicar_tarjeta(
            conn, negocio_id,
            producto_id=ln['producto_id'],
            cantidad=float(ln['cantidad']),
            tipo='entrada',
            motivo=motivo,
            registrado_por=usuario_id,
            valor_unitario=float(ln['valor_unitario']) if ln['valor_unitario'] else None,
            notas=notas,
            referencia_id=data.get('referencia_id'),
            referencia_tipo=data.get('referencia_tipo'),
            tipo_documento=tipo_documento,
            documento_numero=documento_numero,
            documento_fecha=documento_fecha,
            proveedor_id=proveedor_id,
            proveedor_nombre=proveedor_nombre,
            iva_total=iva_total,
            documento_total=documento_total,
            iva_pct=ln['iva_pct'],
            iva_valor=ln['iva_valor'],
            presentacion_id=ln['presentacion_id'],
            metodo_pago=metodo_pago,
            tipo_documento_id=tipo_doc_id
        )

        # Feed/update quote (cotizacion) from this entry if it's a purchase and has a price
        if motivo == 'compra' and proveedor_id and ln['valor_unitario'] and float(ln['valor_unitario']) > 0:
            from datetime import timedelta, date
            vu = float(ln['valor_unitario'])
            f_cot = documento_fecha or date.today()
            f_vence = f_cot + timedelta(days=180)
            
            pres_id = ln['presentacion_id']
            pres_nombre = ln['presentacion_nombre']
            pres_equiv = float(ln['presentacion_equivalencia'])
            precio_cot = vu * pres_equiv
            
            # Check if a quote exists for this product, provider, and presentation
            cot_row = conn.execute("""
                SELECT id FROM cotizaciones_compras
                WHERE negocio_id = %s AND tercero_id = %s AND item_id = %s AND presentacion_id = %s
                LIMIT 1
            """, (negocio_id, proveedor_id, ln['producto_id'], pres_id)).fetchone()
            
            if cot_row:
                conn.execute("""
                    UPDATE cotizaciones_compras
                    SET numero_cotizacion = %s, fecha_cotizacion = %s, fecha_vencimiento = %s,
                        precio = %s, unidades_item = %s, descripcion_presentacion = %s,
                        validada_proveedor = TRUE, updated_at = NOW()
                    WHERE id = %s
                """, (documento_numero, f_cot, f_vence, precio_cot, pres_equiv, pres_nombre, cot_row['id']))
            else:
                conn.execute("""
                    INSERT INTO cotizaciones_compras
                        (negocio_id, numero_cotizacion, tercero_id, item_id, fecha_cotizacion,
                         fecha_vencimiento, descripcion_presentacion, unidades_item, precio,
                         origen, validada_proveedor, updated_at, presentacion_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'compra', TRUE, NOW(), %s)
                """, (negocio_id, documento_numero, proveedor_id, ln['producto_id'], f_cot, f_vence, pres_nombre, pres_equiv, precio_cot, pres_id))

    if _asiento_auto:
        try:
            if documento_total > 0:
                _asiento_auto(conn, negocio_id, tipo_doc_id or tipo_documento,
                              {'subtotal_compra': float(subtotal_compra),
                               'iva_compra': float(iva_total),
                               'total_compra': float(documento_total)},
                              registrado_por=usuario_id,
                              fecha=documento_fecha,
                              descripcion_override=f"{tipo_documento} N° {documento_numero}",
                              origen_tipo='inventario_entrada',
                              origen_id=f"{tipo_documento}:{documento_numero}",
                              metodo_pago=metodo_pago,
                              tercero_id=proveedor_id,
                              tipo_documento_fisico=tipo_documento,
                              documento_numero_fisico=documento_numero)
        except Exception as _e:
            raise _e

    # Recostear any products that were deleted or registered/modified in this document
    prods_to_recost = set(data.get('_prod_ids_to_recost', []))
    for ln in lineas_procesadas:
        prods_to_recost.add(ln['producto_id'])
    for p_id in prods_to_recost:
        _recostear_producto(conn, negocio_id, p_id)

    return {
        'ok': True,
        'advertencias': advertencias,
        'lineas': len(lineas),
        'subtotal_compra': float(subtotal_compra),
        'iva_compra': float(iva_total),
        'total_compra': float(documento_total),
    }, 200


# ── Productos ──────────────────────────────────────────────────────────────────

@bp.route('/api/inventario/producto', methods=['POST'])
def api_inventario_producto_crear():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    negocio_id = data.get('negocio_id')
    nombre     = (data.get('nombre') or '').strip()
    if not negocio_id or not nombre:
        return jsonify({'ok': False, 'error': 'negocio_id y nombre requeridos'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, int(negocio_id))
        if error:
            return error
        row = conn.execute("""
            INSERT INTO productos (negocio_id, nombre, categoria, precio, costo,
                                   descripcion, codigo_barra, iva_pct, orden)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            negocio_id, nombre,
            data.get('categoria') or None,
            float(data.get('precio') or 0),
            float(data.get('costo') or 0),
            data.get('descripcion') or None,
            data.get('codigo_barra') or None,
            float(data.get('iva_pct') or 0),
            int(data.get('orden') or 0),
        )).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': row[0]})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/producto/<int:producto_id>', methods=['DELETE'])
def api_inventario_producto_eliminar(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id = _negocio_id_de_producto(conn, producto_id)
        if not negocio_id:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404

        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error

        # Check 1: Movimientos de inventario
        mov_cnt = conn.execute(
            "SELECT COUNT(*) FROM movimientos_inventario WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if mov_cnt > 0:
            return jsonify({
                'ok': False,
                'error': f'No se puede eliminar el producto porque registra {mov_cnt} movimiento(s) de inventario.'
            }), 400

        # Check 2: Tarjeta estándar propia (receta configurada)
        receta_cnt = conn.execute(
            "SELECT COUNT(*) FROM tarjeta_estandar WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if receta_cnt > 0:
            return jsonify({
                'ok': False,
                'error': 'No se puede eliminar el producto porque tiene una tarjeta estándar (receta) configurada. Elimine la receta primero.'
            }), 400

        # Check 3: Componente en tarjeta estándar de otros productos
        comp_rows = conn.execute("""
            SELECT DISTINCT p.nombre 
            FROM tarjeta_estandar te
            JOIN productos p ON te.producto_id = p.id
            WHERE te.componente_id = %s
        """, (producto_id,)).fetchall()
        if comp_rows:
            nombres = ", ".join([r['nombre'] for r in comp_rows])
            return jsonify({
                'ok': False,
                'error': f'No se puede eliminar el producto porque se utiliza como ingrediente en las recetas de: {nombres}. Retíralo de esas recetas antes de borrar el producto.'
            }), 400

        # Check 4: Historial de ventas / pedidos
        ventas_r = conn.execute(
            "SELECT COUNT(*) FROM pedido_items WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        ventas_t = conn.execute(
            "SELECT COUNT(*) FROM items_pedido_tienda WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        total_ventas = ventas_r + ventas_t
        if total_ventas > 0:
            return jsonify({
                'ok': False,
                'error': f'No se puede eliminar el producto porque registra un historial de {total_ventas} venta(s)/pedido(s).'
            }), 400

        # Check 5: Cotizaciones de compras
        cot_compras_cnt = conn.execute(
            "SELECT COUNT(*) FROM cotizaciones_compras WHERE item_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if cot_compras_cnt > 0:
            return jsonify({
                'ok': False,
                'error': f'No se puede eliminar el producto porque tiene {cot_compras_cnt} cotización(es) de compra registrada(s). Por favor, elimina primero las cotizaciones correspondientes en la pestaña "Compras y agotados" antes de intentar borrar este producto.'
            }), 400

        # Check 6: Cotizaciones de tienda (ventas/POS)
        cot_tienda_cnt = conn.execute(
            "SELECT COUNT(*) FROM cotizacion_items_tienda WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if cot_tienda_cnt > 0:
            return jsonify({
                'ok': False,
                'error': f'No se puede eliminar el producto porque está referenciado en {cot_tienda_cnt} cotización(es) de la tienda. Debes eliminar primero dichas cotizaciones de venta.'
            }), 400

        # Check 7: Fichas solares (módulo Home Solar)
        ficha_cnt = conn.execute(
            "SELECT COUNT(*) FROM producto_fichas_solares WHERE producto_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if ficha_cnt > 0:
            return jsonify({
                'ok': False,
                'error': 'No se puede eliminar el producto porque tiene una ficha solar activa vinculada. Elimina la ficha solar primero.'
            }), 400

        # Check 8: Vinculado como producto obtenido en producción
        parent_cnt = conn.execute(
            "SELECT COUNT(*) FROM movimientos_inventario WHERE producto_padre_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if parent_cnt > 0:
            return jsonify({
                'ok': False,
                'error': f'No se puede eliminar el producto porque figura como el producto obtenido en {parent_cnt} producción(es) del historial.'
            }), 400

        # All checks passed! Delete product dependent sub-records and product
        conn.execute("DELETE FROM saldos_inventario WHERE producto_id = %s", (producto_id,))
        conn.execute("DELETE FROM producto_atributos WHERE producto_id = %s", (producto_id,))
        conn.execute("DELETE FROM producto_variantes WHERE producto_id = %s", (producto_id,))
        conn.execute("DELETE FROM producto_imagenes WHERE producto_id = %s", (producto_id,))
        conn.execute("DELETE FROM productos WHERE id = %s AND negocio_id = %s", (producto_id, negocio_id))
        conn.commit()

        return jsonify({'ok': True, 'mensaje': 'Producto eliminado correctamente'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/productos')
def api_inventario_productos(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        rows = conn.execute("""
            SELECT p.id, p.nombre, p.categoria, p.precio,
                   COALESCE(s.costo_und, p.costo) AS costo,
                   p.codigo_barra, p.iva_pct, p.disponible, p.orden,
                   COALESCE(s.stock, 0) AS stock
            FROM productos p
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id
                AND s.negocio_id = p.negocio_id AND s.bodega = 1
            WHERE p.negocio_id = %s
            ORDER BY p.categoria, p.orden, p.nombre
        """, (negocio_id,)).fetchall()
        return jsonify({'ok': True, 'productos': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Tarjeta estándar ───────────────────────────────────────────────────────────

@bp.route('/api/inventario/producto/<int:producto_id>/tarjeta', methods=['GET'])
def api_inventario_tarjeta_ver(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id = _negocio_id_de_producto(conn, producto_id)
        if not negocio_id:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        rows = conn.execute("""
            SELECT te.componente_id, te.cantidad, p.nombre,
                   COALESCE(s.costo_und, p.costo, 0) AS costo_und
            FROM tarjeta_estandar te
            JOIN productos p ON p.id = te.componente_id
            LEFT JOIN (
                SELECT DISTINCT ON (producto_id, negocio_id) producto_id, negocio_id, costo_und
                FROM saldos_inventario
                WHERE bodega = 1
                ORDER BY producto_id, negocio_id, id DESC
            ) s ON s.producto_id = p.id AND s.negocio_id = p.negocio_id
            WHERE te.producto_id = %s
            ORDER BY te.id ASC
        """, (producto_id,)).fetchall()
        return jsonify({'ok': True, 'componentes': [{
            'componente_id': r['componente_id'],
            'cantidad': float(r['cantidad']),
            'nombre': r['nombre'],
            'costo_und': float(r['costo_und'] or 0)
        } for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/producto/<int:producto_id>/tarjeta', methods=['POST'])
def api_inventario_tarjeta_guardar(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    lineas = data.get('lineas', [])
    if not lineas:
        return jsonify({'ok': False, 'error': 'Debe agregar al menos un componente'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id = _negocio_id_de_producto(conn, producto_id)
        if not negocio_id:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        conn.execute("DELETE FROM tarjeta_estandar WHERE producto_id = %s", (producto_id,))
        for ln in lineas:
            conn.execute("""
                INSERT INTO tarjeta_estandar (producto_id, componente_id, cantidad)
                VALUES (%s,%s,%s)
                ON CONFLICT (producto_id, componente_id) DO UPDATE SET cantidad = EXCLUDED.cantidad
            """, (producto_id, int(ln['componente_id']), float(ln['cantidad'])))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/producto/<int:producto_id>/tarjeta', methods=['DELETE'])
def api_inventario_tarjeta_eliminar(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id = _negocio_id_de_producto(conn, producto_id)
        if not negocio_id:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        conn.execute("DELETE FROM tarjeta_estandar WHERE producto_id = %s", (producto_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Entrada de mercancía ───────────────────────────────────────────────────────

@bp.route('/api/inventario/<int:negocio_id>/entrada', methods=['POST'])
def api_inventario_entrada(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data   = request.get_json() or {}
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        resultado, status = _registrar_entrada_inventario(
            conn, negocio_id, data, session['usuario_id']
        )
        if not resultado.get('ok'):
            conn.rollback()
            return jsonify(resultado), status
        conn.commit()
        return jsonify(resultado), status
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()

    lineas = data.get('lineas', [])
    motivo = data.get('motivo', 'compra')
    notas  = data.get('notas') or None
    if not lineas:
        return jsonify({'ok': False, 'error': 'Debe agregar al menos una línea'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        advertencias = []
        for ln in lineas:
            prod_id = int(ln['producto_id'])
            if _es_ensamble(conn, prod_id):
                comps = _componentes_de(conn, prod_id)
                nombres = ', '.join(f"{c['nombre']} x{c['cantidad']}" for c in comps)
                prod = conn.execute("SELECT nombre FROM productos WHERE id=%s", (prod_id,)).fetchone()
                return jsonify({
                    'ok': False,
                    'error': f'"{prod["nombre"]}" es un ensamble — no se puede comprar directamente. '
                             f'Compre sus componentes: {nombres}'
                }), 400

        for ln in lineas:
            _aplicar_tarjeta(
                conn, negocio_id,
                producto_id    = int(ln['producto_id']),
                cantidad       = float(ln['cantidad']),
                tipo           = 'entrada',
                motivo         = motivo,
                registrado_por = session['usuario_id'],
                valor_unitario = float(ln.get('valor_unitario') or 0) or None,
                notas          = notas,
                referencia_id  = data.get('referencia_id'),
                referencia_tipo= data.get('referencia_tipo'),
            )
        if _asiento_auto:
            try:
                total_compra = sum(
                    float(ln['cantidad']) * float(ln.get('valor_unitario') or 0)
                    for ln in lineas if ln.get('valor_unitario')
                )
                if total_compra > 0:
                    _asiento_auto(conn, negocio_id, 'COMPRA',
                                  {'subtotal_compra': total_compra,
                                   'iva_compra': 0,
                                   'total_compra': total_compra},
                                  registrado_por=session['usuario_id'])
            except Exception as _e:
                print(f'[cont] compra negocio={negocio_id}: {_e}')
        conn.commit()
        return jsonify({'ok': True, 'advertencias': advertencias})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Stock y kardex ─────────────────────────────────────────────────────────────

@bp.route('/api/tienda/<slug>/inventario/entrada', methods=['POST'])
def api_tienda_inventario_entrada(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id, error = _negocio_id_tienda(conn, slug)
        if error:
            return jsonify({'ok': False, 'error': error}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        resultado, status = _registrar_entrada_inventario(
            conn, negocio_id, data, session['usuario_id']
        )
        if not resultado.get('ok'):
            conn.rollback()
            return jsonify(resultado), status
        conn.commit()
        return jsonify(resultado), status
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/stock')
def api_inventario_stock(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        rows = conn.execute("""
            SELECT p.id, p.nombre, p.categoria, s.bodega,
                   s.stock, s.costo_und, s.valor_existencia, s.updated_at
            FROM saldos_inventario s
            JOIN productos p ON p.id = s.producto_id
            WHERE s.negocio_id = %s
            ORDER BY p.categoria, p.nombre
        """, (negocio_id,)).fetchall()
        return jsonify({'ok': True, 'saldos': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/inventario/stock')
def api_tienda_inventario_stock(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id, error = _negocio_id_tienda(conn, slug)
        if error:
            return jsonify({'ok': False, 'error': error}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        rows = conn.execute("""
            SELECT p.id, p.nombre, p.categoria, s.bodega,
                   s.stock, s.costo_und, s.valor_existencia, s.updated_at
            FROM saldos_inventario s
            JOIN productos p ON p.id = s.producto_id
            WHERE s.negocio_id = %s
            ORDER BY p.categoria, p.nombre
        """, (negocio_id,)).fetchall()
        return jsonify({'ok': True, 'saldos': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/producto/<int:producto_id>/kardex')
def api_inventario_kardex(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id = _negocio_id_de_producto(conn, producto_id)
        if not negocio_id:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        rows = conn.execute("""
            SELECT m.id, m.tipo, m.motivo, m.cantidad, m.stock_anterior, m.stock_nuevo,
                   m.valor_unitario, m.costo_und, m.valor_total, m.notas, m.tipo_documento,
                   m.documento_numero, m.documento_fecha, m.proveedor_id,
                   COALESCE(t.nombre, m.proveedor_nombre) AS proveedor_nombre, m.iva_total, m.documento_total,
                   COALESCE(TO_CHAR(m.documento_fecha, 'DD/MM/YY') || ' ' || TO_CHAR(m.created_at, 'HH24:MI'), TO_CHAR(m.created_at, 'DD/MM/YY HH24:MI')) AS fecha,
                   p_padre.nombre AS producto_padre_nombre
            FROM movimientos_inventario m
            LEFT JOIN terceros t ON t.id = m.proveedor_id
            LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
            WHERE m.producto_id = %s
            ORDER BY COALESCE(m.documento_fecha, m.created_at::date) DESC, m.created_at DESC, m.id DESC LIMIT 300
        """, (producto_id,)).fetchall()
        prod_info = conn.execute("""
            SELECT p.costo, COALESCE(s.stock, 0.0) AS stock
            FROM productos p
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.bodega = 1
            WHERE p.id = %s
        """, (producto_id,)).fetchone()
        
        costo_actual = float(prod_info['costo']) if prod_info and prod_info['costo'] is not None else 0.0
        stock_actual = float(prod_info['stock']) if prod_info and prod_info['stock'] is not None else 0.0

        return jsonify({
            'ok': True, 
            'movimientos': [dict(r) for r in rows],
            'costo_actual': costo_actual,
            'stock_actual': stock_actual
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/inventario/kardex')
def api_tienda_inventario_kardex(slug):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    producto_id = request.args.get('producto_id', type=int)
    if not producto_id:
        return jsonify({'ok': False, 'error': 'producto_id requerido'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id, error = _negocio_id_tienda(conn, slug)
        if error:
            return jsonify({'ok': False, 'error': error}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        rows = conn.execute("""
            SELECT m.id, m.tipo, m.motivo, m.cantidad, m.stock_anterior, m.stock_nuevo,
                   m.valor_unitario, m.costo_und, m.valor_total, m.notas, m.tipo_documento,
                   m.documento_numero, m.documento_fecha, m.proveedor_id,
                   COALESCE(t.nombre, m.proveedor_nombre) AS proveedor_nombre, m.iva_total, m.documento_total,
                   COALESCE(TO_CHAR(m.documento_fecha, 'DD/MM/YY') || ' ' || TO_CHAR(m.created_at, 'HH24:MI'), TO_CHAR(m.created_at, 'DD/MM/YY HH24:MI')) AS fecha,
                   p_padre.nombre AS producto_padre_nombre
            FROM movimientos_inventario m
            LEFT JOIN terceros t ON t.id = m.proveedor_id
            LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
            WHERE m.producto_id = %s AND m.negocio_id = %s
            ORDER BY COALESCE(m.documento_fecha, m.created_at::date) DESC, m.created_at DESC, m.id DESC LIMIT 300
        """, (producto_id, negocio_id)).fetchall()
        prod_info = conn.execute("""
            SELECT p.costo, COALESCE(s.stock, 0.0) AS stock
            FROM productos p
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.bodega = 1
            WHERE p.id = %s AND p.negocio_id = %s
        """, (producto_id, negocio_id)).fetchone()
        
        costo_actual = float(prod_info['costo']) if prod_info and prod_info['costo'] is not None else 0.0
        stock_actual = float(prod_info['stock']) if prod_info and prod_info['stock'] is not None else 0.0

        return jsonify({
            'ok': True, 
            'movimientos': [dict(r) for r in rows],
            'costo_actual': costo_actual,
            'stock_actual': stock_actual
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/producto/<int:producto_id>', methods=['POST', 'PUT'])
def api_inventario_producto_editar(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        negocio_id = _negocio_id_de_producto(conn, producto_id)
        if not negocio_id:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        conn.execute("""
            UPDATE productos SET
                nombre=%s, categoria=%s, precio=%s, costo=%s,
                descripcion=%s, codigo_barra=%s, iva_pct=%s, disponible=%s
            WHERE id=%s
        """, (
            (data.get('nombre') or '').strip(),
            data.get('categoria') or None,
            float(data.get('precio') or 0),
            float(data.get('costo') or 0),
            data.get('descripcion') or None,
            data.get('codigo_barra') or None,
            float(data.get('iva_pct') or 0),
            bool(data.get('disponible', True)),
            producto_id,
        ))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Producción ────────────────────────────────────────────────────────────────

@bp.route('/api/inventario/<int:negocio_id>/produccion/preview')
def api_produccion_preview(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    producto_id = request.args.get('producto_id', type=int)
    cantidad    = request.args.get('cantidad', type=float, default=1)
    if not producto_id or cantidad <= 0:
        return jsonify({'ok': False, 'error': 'producto_id y cantidad requeridos'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        producto = conn.execute(
            "SELECT nombre FROM productos WHERE id=%s AND negocio_id=%s",
            (producto_id, negocio_id)
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        componentes = conn.execute("""
            SELECT te.componente_id AS id, p.nombre,
                   te.cantidad AS cant_tarjeta,
                   COALESCE(s.stock, 0) AS stock_actual,
                   COALESCE(s.costo_und, p.costo, 0) AS costo_und
            FROM tarjeta_estandar te
            JOIN productos p ON p.id = te.componente_id
            LEFT JOIN saldos_inventario s
                   ON s.producto_id = te.componente_id
                  AND s.negocio_id  = %s AND s.bodega = 1
            WHERE te.producto_id = %s
        """, (negocio_id, producto_id)).fetchall()
        if not componentes:
            return jsonify({'ok': False, 'error': 'Este producto no tiene tarjeta estándar definida'}), 400
        qty = Decimal(str(cantidad))
        lineas = []
        puede_producir = True
        costo_total_produccion = Decimal('0')
        for c in componentes:
            a_consumir  = Decimal(str(c['cant_tarjeta'])) * qty
            stock_actual = Decimal(str(c['stock_actual']))
            costo_und    = Decimal(str(c['costo_und']))
            costo_total  = a_consumir * costo_und
            costo_total_produccion += costo_total
            
            suficiente  = stock_actual >= a_consumir
            if not suficiente:
                puede_producir = False
            lineas.append({
                'id':           c['id'],
                'nombre':       c['nombre'],
                'a_consumir':   float(a_consumir),
                'stock_actual': float(stock_actual),
                'costo_und':    float(costo_und),
                'costo_total':  float(costo_total),
                'suficiente':   suficiente,
            })
            
        costo_unitario_produccion = costo_total_produccion / qty if qty > 0 else Decimal('0')
        return jsonify({
            'ok': True,
            'producto': producto['nombre'],
            'cantidad': cantidad,
            'puede_producir': puede_producir,
            'costo_total_produccion': float(costo_total_produccion),
            'costo_unitario_produccion': float(costo_unitario_produccion),
            'lineas': lineas,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/produccion', methods=['POST'])
def api_produccion_registrar(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data        = request.get_json() or {}
    producto_id = int(data.get('producto_id') or 0)
    cantidad    = Decimal(str(data.get('cantidad') or 1))
    notas       = data.get('notas') or None
    tipo_documento = (data.get('tipo_documento') or '').strip().upper() or None
    documento_numero = (data.get('documento_numero') or '').strip().upper() or None

    if not producto_id or cantidad <= 0:
        return jsonify({'ok': False, 'error': 'producto_id y cantidad requeridos'}), 400
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        
        # Resolve document type ID
        tipo_doc_id = _int_o_none(data.get('tipo_documento_id') or data.get('tipo_documento'))
        if not tipo_doc_id:
            # Fallback to predeterminado document type of type 'produccion'
            default_doc = conn.execute(
                "SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND activo = TRUE AND predeterminado = TRUE AND tipo_movimiento = 'produccion' LIMIT 1",
                (negocio_id,)
            ).fetchone()
            if default_doc:
                tipo_doc_id = default_doc['id']
        elif not tipo_doc_id and data.get('tipo_documento'):
            tipo_str = str(data['tipo_documento']).strip()
            td_row = conn.execute("""
                SELECT id FROM tipos_documento_negocio
                WHERE negocio_id = %s AND (UPPER(nombre) = %s OR UPPER(codigo) = %s)
                LIMIT 1
            """, (negocio_id, tipo_str.upper(), tipo_str.upper())).fetchone()
            if td_row:
                tipo_doc_id = td_row['id']

        td = None
        if tipo_doc_id:
            td = conn.execute("""
                SELECT id, nombre, es_interno, codigo 
                FROM tipos_documento_negocio
                WHERE negocio_id = %s AND id = %s
            """, (negocio_id, tipo_doc_id)).fetchone()

        es_interno = td['es_interno'] if (td and td['es_interno'] is not None) else True
        tipo_documento = td['nombre'] if td else 'PRODUCCION'

        # Consecutivo de producción si aplica
        if tipo_doc_id:
            from .contabilidad import obtener_siguiente_consecutivo
            res_num, es_interno_actual = obtener_siguiente_consecutivo(conn, negocio_id, tipo_doc_id)
            if es_interno:
                if res_num:
                    tipo_doc_codigo = td['codigo'] if (td and td['codigo']) else 'PROD'
                    try:
                        documento_numero = f"{tipo_doc_codigo}-{int(res_num)}"
                    except (ValueError, TypeError):
                        documento_numero = f"{tipo_doc_codigo}-{res_num}"
            else:
                if not documento_numero:
                    return jsonify({'ok': False, 'error': f'El número de documento es obligatorio para el tipo de documento externo {tipo_documento}.'}), 400

        producto = conn.execute(
            "SELECT nombre FROM productos WHERE id=%s AND negocio_id=%s",
            (producto_id, negocio_id)
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        componentes = conn.execute(
            "SELECT componente_id, cantidad FROM tarjeta_estandar WHERE producto_id=%s",
            (producto_id,)
        ).fetchall()
        if not componentes:
            return jsonify({'ok': False, 'error': 'Sin tarjeta estándar'}), 400

        # Verificar stock suficiente y leer costos ANTES de aplicar salidas
        faltantes    = []
        costo_total  = Decimal('0')
        comps_cont   = []
        for c in componentes:
            a_consumir = Decimal(str(c['cantidad'])) * cantidad
            saldo = conn.execute("""
                SELECT COALESCE(s.stock, 0) AS stock,
                       COALESCE(s.costo_und, p.costo, 0) AS costo_und
                FROM productos p
                LEFT JOIN saldos_inventario s
                       ON s.producto_id = p.id
                      AND s.negocio_id  = %s AND s.bodega = 1
                WHERE p.id = %s AND p.negocio_id = %s
            """, (negocio_id, c['componente_id'], negocio_id)).fetchone()
            stock_actual = Decimal(str(saldo['stock']))     if saldo else Decimal('0')
            costo_und    = Decimal(str(saldo['costo_und'])) if saldo else Decimal('0')
            if stock_actual < a_consumir:
                nombre = conn.execute("SELECT nombre FROM productos WHERE id=%s",
                                      (c['componente_id'],)).fetchone()
                faltantes.append(
                    f"{nombre['nombre'] if nombre else c['componente_id']}: "
                    f"necesita {float(a_consumir)}, tiene {float(stock_actual)}"
                )
            costo_total += a_consumir * costo_und
            comps_cont.append({
                'producto_id': c['componente_id'],
                'cantidad':    float(a_consumir),
                'costo_und':   float(costo_und),
            })

        if faltantes:
            return jsonify({'ok': False, 'error': 'Stock insuficiente:\n' + '\n'.join(faltantes)}), 400

        # Costo unitario del terminado = total componentes / cantidad producida
        costo_unitario = costo_total / cantidad if cantidad > 0 else Decimal('0')

        import time
        prod_token = int(time.time())

        # Salida de cada componente
        for i, c in enumerate(componentes):
            cant_comp = Decimal(str(c['cantidad'])) * cantidad
            comp_cost = comps_cont[i]['costo_und']
            _mov_directo(conn, negocio_id, c['componente_id'], cant_comp,
                         'salida', 'produccion', session['usuario_id'],
                         valor_unitario=comp_cost,
                         notas=notas, referencia_tipo='produccion', referencia_id=prod_token,
                         producto_padre_id=producto_id,
                         tipo_documento=tipo_documento, documento_numero=documento_numero,
                         documento_fecha=date.today(),
                         tipo_documento_id=tipo_doc_id)

        # Entrada del terminado con costo calculado desde componentes
        _mov_directo(conn, negocio_id, producto_id, cantidad,
                     'entrada', 'produccion', session['usuario_id'],
                     valor_unitario=costo_unitario,
                     notas=notas, referencia_tipo='produccion', referencia_id=prod_token,
                     tipo_documento=tipo_documento, documento_numero=documento_numero,
                     documento_fecha=date.today(),
                     tipo_documento_id=tipo_doc_id)

        # Asiento contable de producción (best-effort, no bloquea)
        if _asiento_produccion:
            try:
                _asiento_produccion(
                    conn, negocio_id, producto_id, float(costo_total), comps_cont,
                    registrado_por=session['usuario_id'],
                    descripcion=f'Producción {producto["nombre"]} x{float(cantidad)}',
                    origen_tipo='produccion',
                    origen_id=prod_token,
                    tipo_documento=tipo_documento,
                    documento_numero=documento_numero,
                    tipo_documento_id=tipo_doc_id
                )
            except Exception as _e:
                print(f'[cont] produccion prod={producto_id}: {_e}')

        conn.commit()
        return jsonify({
            'ok': True,
            'producido':      float(cantidad),
            'producto':       producto['nombre'],
            'costo_unitario': float(costo_unitario),
            'costo_total':    float(costo_total),
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


def _recostear_producto(conn, negocio_id, producto_id):
    """
    Recalcula cronológicamente los saldos de inventario y el costo promedio de un producto.
    """
    from decimal import Decimal
    movs = conn.execute("""
        SELECT id, tipo, cantidad, valor_unitario
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s
        ORDER BY COALESCE(documento_fecha, created_at::date) ASC, created_at ASC, id ASC
    """, (negocio_id, producto_id)).fetchall()

    stock = Decimal('0')
    val_existencia = Decimal('0')
    costo_und = Decimal('0')

    for m in movs:
        cant_m = Decimal(str(m['cantidad']))
        signo = Decimal('1') if m['tipo'] == 'entrada' else Decimal('-1')
        stock_ant = stock
        stock_nuevo = stock_ant + cant_m * signo

        if m['tipo'] == 'entrada' and m['valor_unitario'] is not None:
            vu = Decimal(str(m['valor_unitario']))
            costo_und = (val_existencia + cant_m * vu) / stock_nuevo if stock_nuevo > 0 else vu
            val_existencia = stock_nuevo * costo_und if stock_nuevo > 0 else Decimal('0')
        else:
            val_existencia = stock_nuevo * costo_und if stock_nuevo > 0 else Decimal('0')

        valor_total = cant_m * (Decimal(str(m['valor_unitario'])) if m['valor_unitario'] is not None else costo_und)

        conn.execute("""
            UPDATE movimientos_inventario
            SET stock_anterior = %s,
                stock_nuevo = %s,
                costo_und = %s,
                valor_total = %s
            WHERE id = %s
        """, (float(stock_ant), float(stock_nuevo), float(costo_und), float(valor_total), m['id']))

        stock = stock_nuevo

    saldo_final = conn.execute("""
        SELECT id FROM saldos_inventario
        WHERE negocio_id = %s AND producto_id = %s AND bodega = 1
    """, (negocio_id, producto_id)).fetchone()

    if saldo_final:
        conn.execute("""
            UPDATE saldos_inventario
            SET stock = %s, costo_und = %s, valor_existencia = %s, updated_at = NOW()
            WHERE id = %s
        """, (float(stock), float(costo_und), float(val_existencia), saldo_final['id']))
    else:
        conn.execute("""
            INSERT INTO saldos_inventario (negocio_id, producto_id, bodega, stock, costo_und, valor_existencia)
            VALUES (%s, %s, 1, %s, %s, %s)
        """, (negocio_id, producto_id, float(stock), float(costo_und), float(val_existencia)))

    conn.execute("""
        UPDATE productos
        SET costo = %s
        WHERE id = %s AND negocio_id = %s
    """, (float(costo_und), producto_id, negocio_id))


@bp.route('/api/inventario/<int:negocio_id>/documento/previsualizar')
def api_documento_previsualizar(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    movimiento_id = request.args.get('movimiento_id', type=int)
    if not movimiento_id:
        return jsonify({'ok': False, 'error': 'movimiento_id requerido'}), 400

    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error

        mov = conn.execute("""
            SELECT m.id, m.producto_id, m.nombre_producto, m.tipo, m.cantidad, 
                   m.tipo_documento, m.documento_numero, m.referencia_id, m.referencia_tipo,
                   m.created_at, m.documento_total
            FROM movimientos_inventario m
            WHERE m.id = %s AND m.negocio_id = %s
        """, (movimiento_id, negocio_id)).fetchone()

        if not mov:
            return jsonify({'ok': False, 'error': 'Movimiento no encontrado'}), 404

        mov_dict = dict(mov)
        otros_items = []
        origen_id = None
        origen_tipo = None

        if mov['referencia_tipo'] == 'produccion' and mov['referencia_id']:
            origen_tipo = 'produccion'
            origen_id = mov['referencia_id']
            rows = conn.execute("""
                SELECT id, producto_id, nombre_producto, tipo, cantidad
                FROM movimientos_inventario
                WHERE negocio_id = %s AND referencia_tipo = 'produccion' AND referencia_id = %s AND id != %s
            """, (negocio_id, mov['referencia_id'], movimiento_id)).fetchall()
            otros_items = [dict(r) for r in rows]

        elif mov['tipo_documento'] and mov['documento_numero']:
            origen_tipo = 'inventario_entrada'
            origen_id = f"{mov['tipo_documento']}:{mov['documento_numero']}"
            rows = conn.execute("""
                SELECT id, producto_id, nombre_producto, tipo, cantidad
                FROM movimientos_inventario
                WHERE negocio_id = %s AND tipo_documento = %s AND documento_numero = %s AND id != %s
            """, (negocio_id, mov['tipo_documento'], mov['documento_numero'], movimiento_id)).fetchall()
            otros_items = [dict(r) for r in rows]

        comprobante = None
        if origen_id and origen_tipo:
            comp_row = conn.execute("""
                SELECT id, numero_comprobante, tipo, total_debitos, descripcion, fecha
                FROM comprobantes_contables
                WHERE negocio_id = %s AND origen_tipo = %s AND origen_id = %s
                LIMIT 1
            """, (negocio_id, origen_tipo, origen_id)).fetchone()
            if comp_row:
                comprobante = dict(comp_row)

        if not comprobante and mov['tipo_documento'] and mov['documento_numero']:
            comp_row = conn.execute("""
                SELECT id, numero_comprobante, tipo, total_debitos, descripcion, fecha
                FROM comprobantes_contables
                WHERE negocio_id = %s AND tipo = 'COMPRA'
                  AND ABS(total_debitos - %s) < 0.05
                  AND fecha = %s::date
                LIMIT 1
            """, (negocio_id, float(mov['documento_total'] or 0), mov['created_at'].date())).fetchone()
            if comp_row:
                comprobante = dict(comp_row)

        return jsonify({
            'ok': True,
            'item_seleccionado': mov_dict,
            'otros_items': otros_items,
            'comprobante': comprobante
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/documento/anular', methods=['POST'])
def api_documento_anular(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    data = request.get_json() or {}
    movimiento_id = data.get('movimiento_id')
    anular_todo = bool(data.get('anular_todo', False))

    if not movimiento_id:
        return jsonify({'ok': False, 'error': 'movimiento_id requerido'}), 400

    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error

        mov = conn.execute("""
            SELECT id, producto_id, tipo, cantidad, tipo_documento, documento_numero,
                   referencia_id, referencia_tipo, documento_total, created_at
            FROM movimientos_inventario
            WHERE id = %s AND negocio_id = %s
        """, (movimiento_id, negocio_id)).fetchone()

        if not mov:
            return jsonify({'ok': False, 'error': 'Movimiento no encontrado'}), 404

        movimientos_a_borrar = []
        productos_a_recostear = set()
        comprobantes_a_borrar = []

        if anular_todo:
            origen_id = None
            origen_tipo = None

            if mov['referencia_tipo'] == 'produccion' and mov['referencia_id']:
                origen_tipo = 'produccion'
                origen_id = mov['referencia_id']
                rows = conn.execute("""
                    SELECT id, producto_id FROM movimientos_inventario
                    WHERE negocio_id = %s AND referencia_tipo = 'produccion' AND referencia_id = %s
                """, (negocio_id, mov['referencia_id'])).fetchall()
                for r in rows:
                    movimientos_a_borrar.append(r['id'])
                    productos_a_recostear.add(r['producto_id'])

            elif mov['tipo_documento'] and mov['documento_numero']:
                origen_tipo = 'inventario_entrada'
                origen_id = f"{mov['tipo_documento']}:{mov['documento_numero']}"
                rows = conn.execute("""
                    SELECT id, producto_id FROM movimientos_inventario
                    WHERE negocio_id = %s AND tipo_documento = %s AND documento_numero = %s
                """, (negocio_id, mov['tipo_documento'], mov['documento_numero'])).fetchall()
                for r in rows:
                    movimientos_a_borrar.append(r['id'])
                    productos_a_recostear.add(r['producto_id'])

            else:
                movimientos_a_borrar.append(mov['id'])
                productos_a_recostear.add(mov['producto_id'])

            if origen_id and origen_tipo:
                comp_row = conn.execute("""
                    SELECT id FROM comprobantes_contables
                    WHERE negocio_id = %s AND origen_tipo = %s AND origen_id = %s
                """, (negocio_id, origen_tipo, origen_id)).fetchone()
                if comp_row:
                    comprobantes_a_borrar.append(comp_row['id'])

            if not comprobantes_a_borrar and mov['tipo_documento'] and mov['documento_numero']:
                comp_row = conn.execute("""
                    SELECT id FROM comprobantes_contables
                    WHERE negocio_id = %s AND tipo = 'COMPRA'
                      AND ABS(total_debitos - %s) < 0.05
                      AND fecha = %s::date
                """, (negocio_id, float(mov['documento_total'] or 0), mov['created_at'].date())).fetchone()
                if comp_row:
                    comprobantes_a_borrar.append(comp_row['id'])

        else:
            movimientos_a_borrar.append(mov['id'])
            productos_a_recostear.add(mov['producto_id'])

        for comp_id in comprobantes_a_borrar:
            conn.execute("DELETE FROM movimientos_contables WHERE comprobante_id = %s", (comp_id,))
            conn.execute("DELETE FROM comprobantes_contables WHERE id = %s", (comp_id,))

        for mov_id in movimientos_a_borrar:
            conn.execute("DELETE FROM movimientos_inventario WHERE id = %s", (mov_id,))

        productos_recosteados = []
        for prod_id in productos_a_recostear:
            _recostear_producto(conn, negocio_id, prod_id)
            p_info = conn.execute("SELECT nombre FROM productos WHERE id=%s", (prod_id,)).fetchone()
            productos_recosteados.append(p_info['nombre'] if p_info else f"Prod #{prod_id}")

        conn.commit()

        return jsonify({
            'ok': True,
            'movimientos_borrados': len(movimientos_a_borrar),
            'comprobantes_borrados': len(comprobantes_a_borrar),
            'productos_recosteados': productos_recosteados
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/proveedores/buscar')
def api_buscar_proveedores():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, nombre, telefono 
            FROM terceros 
            WHERE (tipo_tercero IS NULL OR tipo_tercero IN ('persona', 'proveedor', 'negocio'))
              AND nombre ILIKE %s 
            ORDER BY nombre 
            LIMIT 50
        """, (f'%{q}%',)).fetchall()
        return jsonify([{'id': r['id'], 'nombre': r['nombre'], 'telefono': r['telefono']} for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/terceros/buscar')
def api_buscar_terceros():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, nombre, telefono 
            FROM terceros 
            WHERE nombre ILIKE %s 
            ORDER BY nombre 
            LIMIT 50
        """, (f'%{q}%',)).fetchall()
        return jsonify([{'id': r['id'], 'nombre': r['nombre'], 'telefono': r['telefono']} for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/proveedores/crear', methods=['POST'])
def api_crear_proveedor():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    nombre = _txt(data.get('nombre'))
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre de proveedor requerido'}), 400
    conn = get_db_connection()
    try:
        # Check if already exists
        row = conn.execute("SELECT id FROM terceros WHERE LOWER(nombre) = LOWER(%s) LIMIT 1", (nombre,)).fetchone()
        if row:
            return jsonify({'ok': True, 'id': row['id'], 'mensaje': 'Ya existía'})
        # Insert new
        row_ins = conn.execute("INSERT INTO terceros (nombre) VALUES (%s) RETURNING id", (nombre,)).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': row_ins['id'], 'mensaje': 'Creado con éxito'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/documentos-tercero/<int:tercero_id>', methods=['GET'])
def api_mantenimiento_documentos_tercero(negocio_id, tercero_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        # Query unique documents in movimientos_inventario (purchases/entries)
        rows_inv = conn.execute("""
            SELECT mi.tipo_documento, mi.documento_numero, mi.documento_fecha, SUM(mi.valor_total) AS total,
                   MIN(sd.saldo) AS saldo_pendiente
            FROM movimientos_inventario mi
            LEFT JOIN saldo_por_documentos sd ON sd.negocio_id = mi.negocio_id 
                                            AND sd.tercero_id = mi.proveedor_id
                                            AND sd.tipo_documento = mi.tipo_documento
                                            AND sd.numero_documento = mi.documento_numero
            WHERE mi.negocio_id = %s AND mi.proveedor_id = %s
            GROUP BY mi.tipo_documento, mi.documento_numero, mi.documento_fecha
            ORDER BY mi.documento_fecha DESC, mi.documento_numero DESC
        """, (negocio_id, tercero_id)).fetchall()
        
        documentos = []
        for r in rows_inv:
            documentos.append({
                'tipo_documento': r['tipo_documento'] or 'otro',
                'documento_numero': r['documento_numero'],
                'fecha': r['documento_fecha'].isoformat() if r['documento_fecha'] else None,
                'origen': 'inventario',
                'total': float(r['total'] or 0),
                'saldo_pendiente': float(r['saldo_pendiente']) if r['saldo_pendiente'] is not None else None
            })
            
        # Query unique documents in pedidos (sales/orders)
        rows_ped = conn.execute("""
            SELECT id, numero_documento, fecha, created_at, total, estado
            FROM pedidos
            WHERE cliente_id = %s OR id_tercero = %s
            ORDER BY COALESCE(fecha, created_at) DESC, id DESC
        """, (tercero_id, tercero_id)).fetchall()
        
        for r in rows_ped:
            doc_num = r['numero_documento'] or str(r['id'])
            # Fallback to created_at if fecha is null
            f_val = r['fecha'] or r['created_at']
            documentos.append({
                'tipo_documento': 'pedido_venta',
                'documento_numero': doc_num,
                'fecha': f_val.date().isoformat() if f_val else None,
                'origen': 'ventas',
                'total': float(r['total'] or 0),
                'estado': r['estado']
            })
            
        # Sort combined documents by date descending
        documentos.sort(key=lambda d: d['fecha'] or '', reverse=True)
        
        return jsonify({
            'ok': True,
            'documentos': documentos
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/documentos-recientes', methods=['GET'])
def api_mantenimiento_documentos_recientes(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    page = _int_o_none(request.args.get('page')) or 1
    limit = _int_o_none(request.args.get('limit')) or 50
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '').strip()
    desde = request.args.get('desde', '').strip()
    hasta = request.args.get('hasta', '').strip()
    
    conn = get_db_connection()
    try:
        # Obtener mapeo de tipos de documentos del negocio
        types_rows = conn.execute("SELECT id, nombre, codigo FROM tipos_documento_negocio WHERE negocio_id = %s", (negocio_id,)).fetchall()
        types_map = {r['id']: r['nombre'] for r in types_rows}

        # 1. Fetch recent inventory documents
        sql_inv = """
            SELECT mi.tipo_documento_id, mi.tipo_documento, mi.documento_numero, mi.documento_fecha, SUM(mi.valor_total) AS total,
                   MIN(mi.proveedor_id) AS proveedor_id, MIN(mi.proveedor_nombre) AS proveedor_nombre
            FROM movimientos_inventario mi
            WHERE mi.negocio_id = %s AND mi.tipo_documento IS NOT NULL AND mi.tipo_documento <> '' 
              AND mi.documento_numero IS NOT NULL AND mi.documento_numero <> ''
        """
        params_inv = [negocio_id]
        
        if q:
            sql_inv += " AND (mi.documento_numero ILIKE %s OR mi.proveedor_nombre ILIKE %s)"
            params_inv.extend([f'%{q}%', f'%{q}%'])
        
        if tipo and tipo != 'todos':
            if tipo != 'pedido_venta':
                try:
                    tipo_id = int(tipo)
                    sql_inv += " AND mi.tipo_documento_id = %s"
                    params_inv.append(tipo_id)
                except ValueError:
                    sql_inv += " AND LOWER(mi.tipo_documento) = LOWER(%s)"
                    params_inv.append(tipo)
            else:
                # Si filtran por 'pedido_venta', no hay registros en movimientos_inventario con ese tipo directo
                sql_inv += " AND 1=0"
                
        if desde:
            sql_inv += " AND mi.documento_fecha >= %s"
            params_inv.append(desde)
        if hasta:
            sql_inv += " AND mi.documento_fecha <= %s"
            params_inv.append(hasta)
            
        sql_inv += """
            GROUP BY mi.tipo_documento_id, mi.tipo_documento, mi.documento_numero, mi.documento_fecha
            ORDER BY mi.documento_fecha DESC, mi.documento_numero DESC
            LIMIT 1000
        """
        
        rows_inv = conn.execute(sql_inv, tuple(params_inv)).fetchall()
        
        consolidated = {}
        
        for r in rows_inv:
            td_id = r['tipo_documento_id']
            doc_num = r['documento_numero']
            td_name = r['tipo_documento'] or 'otro'
            
            # Resolver nombre dinámico desde tipos_documento_negocio
            if td_id and td_id in types_map:
                td_name = types_map[td_id]
                
            key = (td_id, doc_num) if td_id else (td_name, doc_num)
            
            consolidated[key] = {
                'tipo_documento_id': td_id,
                'tipo_documento': td_name,
                'documento_numero': doc_num,
                'fecha': r['documento_fecha'].isoformat() if r['documento_fecha'] else None,
                'origen': 'inventario',
                'total': float(r['total'] or 0),
                'tercero_nombre': r['proveedor_nombre'] or '—',
                'tercero_id': r['proveedor_id']
            }
            
        # 2. Fetch recent orders (sales)
        sql_ped = """
            SELECT p.id, p.tipo_documento_id, p.numero_documento, p.fecha, p.created_at, p.total, p.cliente_id, p.id_tercero, p.nombre_cliente, p.estado
            FROM pedidos p
            WHERE p.negocio_id = %s
        """
        params_ped = [negocio_id]
        
        if q:
            sql_ped += " AND (p.numero_documento ILIKE %s OR p.nombre_cliente ILIKE %s)"
            params_ped.extend([f'%{q}%', f'%{q}%'])
            
        if tipo and tipo != 'todos':
            if tipo == 'pedido_venta':
                sql_ped += " AND (p.tipo_documento_id IS NULL OR p.tipo_documento_id IN (SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND tipo_movimiento = 'venta'))"
                params_ped.append(negocio_id)
            else:
                try:
                    tipo_id = int(tipo)
                    sql_ped += " AND p.tipo_documento_id = %s"
                    params_ped.append(tipo_id)
                except ValueError:
                    sql_ped += " AND p.tipo_documento_id IN (SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND LOWER(nombre) = LOWER(%s))"
                    params_ped.extend([negocio_id, tipo])
                    
        if desde:
            sql_ped += " AND COALESCE(p.fecha, p.created_at::date) >= %s"
            params_ped.append(desde)
        if hasta:
            sql_ped += " AND COALESCE(p.fecha, p.created_at::date) <= %s"
            params_ped.append(hasta)
            
        sql_ped += """
            ORDER BY COALESCE(p.fecha, p.created_at) DESC, p.id DESC
            LIMIT 1000
        """
        
        rows_ped = conn.execute(sql_ped, tuple(params_ped)).fetchall()
        
        for r in rows_ped:
            # Resolve customer name
            c_name = r['nombre_cliente']
            c_id = r['cliente_id'] or r['id_tercero']
            if c_id:
                t_row = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (c_id,)).fetchone()
                if t_row:
                    c_name = t_row['nombre']
                    
            doc_num = r['numero_documento'] or str(r['id'])
            td_id = r['tipo_documento_id']
            td_name = 'pedido_venta'
            if td_id and td_id in types_map:
                td_name = types_map[td_id]
                
            key = (td_id, doc_num) if td_id else (td_name, doc_num)
            f_val = r['fecha'] or r['created_at']
            # Normalizar fecha a YYYY-MM-DD para consistencia en consolidado
            date_str = f_val.strftime('%Y-%m-%d') if f_val else None
            
            # Consolidación: si ya existe el documento por inventario, unificar
            if key in consolidated:
                consolidated[key]['origen'] = 'ambos'
                if not consolidated[key]['tercero_id'] and c_id:
                    consolidated[key]['tercero_id'] = c_id
                    consolidated[key]['tercero_nombre'] = c_name or 'Cliente general'
                if r['total'] and float(r['total']) > consolidated[key]['total']:
                    consolidated[key]['total'] = float(r['total'])
            else:
                consolidated[key] = {
                    'tipo_documento_id': td_id,
                    'tipo_documento': td_name,
                    'documento_numero': doc_num,
                    'fecha': date_str,
                    'origen': 'ventas',
                    'total': float(r['total'] or 0),
                    'tercero_nombre': c_name or 'Cliente general',
                    'tercero_id': c_id,
                    'estado': r['estado']
                }
            
        # 3. Fetch recent accounting documents from movimientos_contables and comprobantes_contables
        sql_cont = """
            SELECT cc.tipo_documento_id, COALESCE(cc.tipo, 'comprobante') AS tipo_documento, 
                   COALESCE(cc.numero_documento, cc.numero_comprobante) AS documento_numero,
                   cc.fecha AS documento_fecha,
                   SUM(CASE WHEN mc.tipo = 'debito' THEN mc.monto ELSE 0 END) AS total,
                   MIN(mc.tercero_id) AS proveedor_id
            FROM movimientos_contables mc
            JOIN comprobantes_contables cc ON cc.id = mc.comprobante_id
            WHERE mc.negocio_id = %s
        """
        params_cont = [negocio_id]
        
        if q:
            sql_cont += """ AND (
                cc.numero_comprobante ILIKE %s 
                OR cc.numero_documento ILIKE %s 
                OR mc.concepto ILIKE %s 
                OR mc.tercero_id IN (SELECT id FROM terceros WHERE nombre ILIKE %s)
            )"""
            params_cont.extend([f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%'])
            
        if tipo and tipo != 'todos':
            if tipo == 'pedido_venta':
                sql_cont += " AND LOWER(cc.tipo) IN ('factura', 'factura_de_venta', 'venta')"
            else:
                try:
                    tipo_id = int(tipo)
                    sql_cont += " AND (cc.tipo_documento_id = %s OR cc.tipo IN (SELECT codigo FROM tipos_documento_negocio WHERE id = %s))"
                    params_cont.extend([tipo_id, tipo_id])
                except ValueError:
                    sql_cont += " AND (LOWER(cc.tipo) = LOWER(%s) OR cc.tipo_documento_id IN (SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND LOWER(codigo) = LOWER(%s)))"
                    params_cont.extend([tipo, negocio_id, tipo])
                    
        if desde:
            sql_cont += " AND cc.fecha >= %s"
            params_cont.append(desde)
        if hasta:
            sql_cont += " AND cc.fecha <= %s"
            params_cont.append(hasta)
            
        sql_cont += """
            GROUP BY cc.tipo_documento_id, cc.tipo, cc.numero_documento, cc.numero_comprobante, cc.fecha
            ORDER BY cc.fecha DESC, cc.numero_documento DESC
            LIMIT 1000
        """
        
        rows_cont = conn.execute(sql_cont, tuple(params_cont)).fetchall()
        
        for r in rows_cont:
            td_id = r['tipo_documento_id']
            # Resolve tipo_documento_id if None using the type string
            if not td_id and r['tipo_documento']:
                td_row = conn.execute("SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))", (negocio_id, r['tipo_documento'].lower(), r['tipo_documento'].lower())).fetchone()
                if td_row:
                    td_id = td_row['id']
                    
            doc_num = r['documento_numero']
            pure_num = doc_num
            if doc_num and '-' in doc_num:
                parts = doc_num.split('-')
                if parts[-1].strip().isdigit():
                    pure_num = parts[-1].strip()
                    
            td_name = r['tipo_documento']
            if td_id and td_id in types_map:
                td_name = types_map[td_id]
                
            key = (td_id, pure_num) if td_id else (td_name.lower(), pure_num)
            
            p_id = r['proveedor_id']
            p_name = '—'
            if p_id:
                t_row = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (p_id,)).fetchone()
                if t_row:
                    p_name = t_row['nombre']
            
            date_str = r['documento_fecha'].isoformat() if r['documento_fecha'] else None
            
            # Consolidate
            if key in consolidated:
                if consolidated[key]['origen'] in ('inventario', 'ventas'):
                    consolidated[key]['origen'] = 'ambos'
                if not consolidated[key]['tercero_id'] and p_id:
                    consolidated[key]['tercero_id'] = p_id
                    consolidated[key]['tercero_nombre'] = p_name or 'Cliente/Proveedor general'
                if r['total'] and float(r['total']) > consolidated[key]['total']:
                    consolidated[key]['total'] = float(r['total'])
            else:
                consolidated[key] = {
                    'tipo_documento_id': td_id,
                    'tipo_documento': td_name,
                    'documento_numero': pure_num,
                    'fecha': date_str,
                    'origen': 'contabilidad',
                    'total': float(r['total'] or 0),
                    'tercero_nombre': p_name or '—',
                    'tercero_id': p_id
                }
            
        # Convertir diccionario consolidado a lista y ordenar por fecha descendente
        documentos = list(consolidated.values())
        documentos.sort(key=lambda d: d['fecha'] or '', reverse=True)
        
        # Calcular paginación
        total_registros = len(documentos)
        total_paginas = (total_registros + limit - 1) // limit if total_registros > 0 else 1
        
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginados = documentos[start_idx:end_idx]
        
        return jsonify({
            'ok': True,
            'documentos': paginados,
            'pagina_actual': page,
            'total_paginas': total_paginas,
            'total_registros': total_registros
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/tipos-documentos', methods=['GET'])
def api_mantenimiento_tipos_documentos(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, nombre, codigo, tipo_movimiento
            FROM tipos_documento_negocio
            WHERE negocio_id = %s AND activo = TRUE
            ORDER BY nombre
        """, (negocio_id,)).fetchall()
        
        tipos = [{
            'id': r['id'],
            'nombre': r['nombre'],
            'codigo': r['codigo'],
            'tipo_movimiento': r['tipo_movimiento']
        } for r in rows]
        
        return jsonify({'ok': True, 'tipos': tipos})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


def normalizar_numero(num_str):
    if not num_str:
        return ""
    num_str = num_str.strip().upper()
    if '-' in num_str:
        parts = num_str.split('-')
        suffix = parts[-1].strip()
        if suffix:
            return suffix
    return num_str

def resolver_variantes_numero(num_str):
    if not num_str:
        return []
    variantes = [num_str]
    # Normalizar quitando espacios alrededor del string
    num_str_clean = num_str.strip()
    if num_str_clean not in variantes:
        variantes.append(num_str_clean)
        
    if '-' in num_str:
        parts = num_str.split('-')
        prefix = '-'.join(parts[:-1]).strip()
        suffix = parts[-1].strip()
        
        # Agregar el sufijo limpio por sí solo (ej: '956' de 'FACTURA PROVEEDOR-956')
        if suffix and suffix not in variantes:
            variantes.append(suffix)
            
        # También el sufijo anterior (antepenúltima parte si aplica, ej: 'PRODUCCION-4' de 'REPORTE-PRODUCCION-4')
        if len(parts) >= 3:
            v_mid = f"{parts[-2].strip()}-{parts[-1].strip()}"
            if v_mid not in variantes:
                variantes.append(v_mid)
                
        try:
            val_num = int(suffix)
            v_unpadded = f"{prefix}-{val_num}"
            if v_unpadded not in variantes:
                variantes.append(v_unpadded)
            # Agregar también el consecutivo numérico puro como string
            v_num_str = str(val_num)
            if v_num_str not in variantes:
                variantes.append(v_num_str)
        except ValueError:
            pass
            
    # Variantes en minúsculas y mayúsculas
    all_variants = []
    for v in variantes:
        v_upper = v.upper()
        v_lower = v.lower()
        if v_upper not in all_variants:
            all_variants.append(v_upper)
        if v_lower not in all_variants:
            all_variants.append(v_lower)
            
    return all_variants


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/auditar-documento', methods=['GET'])
def api_auditar_documento(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    tipo_doc = request.args.get('tipo_documento', '').strip()
    num_doc = request.args.get('documento_numero', '').strip()
    proveedor_id = request.args.get('proveedor_id', '').strip()
    
    if not tipo_doc or not num_doc:
        return jsonify({'ok': False, 'error': 'tipo_documento y documento_numero requeridos'}), 400
    
    conn = get_db_connection()
    try:
        # Resolver tipo_documento_id
        tipo_documento_id = None
        try:
            tipo_documento_id = int(tipo_doc)
        except ValueError:
            row_td = conn.execute("""
                SELECT id FROM tipos_documento_negocio 
                WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))
            """, (negocio_id, tipo_doc, tipo_doc)).fetchone()
            if row_td:
                tipo_documento_id = row_td['id']

        # Look up the order in `pedidos` if it exists
        pedido_row = None
        num_variants = resolver_variantes_numero(num_doc)
        
        # Extraer consecutivos puros y generar variantes con prefijo para enlace retrocompatible
        if '-' in num_doc:
            parts = num_doc.split('-')
            if len(parts) >= 2:
                variant_1 = f"{parts[-2].strip()}-{parts[-1].strip()}"
                variant_2 = parts[-1].strip()
                if variant_1 not in num_variants:
                    num_variants.append(variant_1)
                if variant_2 not in num_variants:
                    num_variants.append(variant_2)
                    
        if tipo_documento_id:
            td_row = conn.execute("SELECT nombre, codigo FROM tipos_documento_negocio WHERE id = %s", (tipo_documento_id,)).fetchone()
            if td_row:
                v_long = f"{td_row['nombre']}-{num_doc}"
                if v_long not in num_variants:
                    num_variants.append(v_long)
                v_long_code = f"{td_row['codigo']}-{num_doc}"
                if v_long_code not in num_variants:
                    num_variants.append(v_long_code)
        
        try:
            pedido_id = int(num_doc)
            pedido_row = conn.execute("SELECT * FROM pedidos WHERE id = %s AND negocio_id = %s", (pedido_id, negocio_id)).fetchone()
        except ValueError:
            pass

        if not pedido_row:
            pedido_row = conn.execute("SELECT * FROM pedidos WHERE UPPER(numero_documento) IN %s AND negocio_id = %s", (tuple(v.upper() for v in num_variants), negocio_id)).fetchone()

        if pedido_row and not tipo_documento_id:
            tipo_documento_id = pedido_row['tipo_doc_id']

        # 1. Query movimientos_inventario
        if tipo_documento_id:
            sql_inv = """
                SELECT m.id, m.producto_id, m.nombre_producto, m.tipo, m.motivo, m.cantidad, 
                       m.valor_unitario, m.valor_total, m.iva_pct, m.created_at, m.documento_fecha,
                       m.proveedor_id, m.proveedor_nombre, m.producto_padre_id,
                       p_padre.nombre AS producto_padre_nombre, m.costo_und
                FROM movimientos_inventario m
                LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
                WHERE m.negocio_id = %s AND m.tipo_documento_id = %s AND m.documento_numero IN %s
            """
            params_inv = [negocio_id, tipo_documento_id, tuple(num_variants)]
        else:
            # Fallback legacy
            if pedido_row:
                sql_inv = """
                    SELECT m.id, m.producto_id, m.nombre_producto, m.tipo, m.motivo, m.cantidad, 
                           m.valor_unitario, m.valor_total, m.iva_pct, m.created_at, m.documento_fecha,
                           m.proveedor_id, m.proveedor_nombre, m.producto_padre_id,
                           p_padre.nombre AS producto_padre_nombre, m.costo_und
                    FROM movimientos_inventario m
                    LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
                    WHERE m.negocio_id = %s AND (
                        (m.referencia_tipo IN ('pedido', 'pedido_tienda', 'pedido_restaurante') AND m.referencia_id = %s)
                        OR (LOWER(m.tipo_documento) = LOWER(%s) AND LOWER(m.documento_numero) IN %s)
                    )
                """
                params_inv = [negocio_id, pedido_row['id'], tipo_doc, tuple(v.lower() for v in num_variants)]
            else:
                sql_inv = """
                    SELECT m.id, m.producto_id, m.nombre_producto, m.tipo, m.motivo, m.cantidad, 
                           m.valor_unitario, m.valor_total, m.iva_pct, m.created_at, m.documento_fecha,
                           m.proveedor_id, m.proveedor_nombre, m.producto_padre_id,
                           p_padre.nombre AS producto_padre_nombre, m.costo_und
                    FROM movimientos_inventario m
                    LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
                    WHERE m.negocio_id = %s AND LOWER(m.tipo_documento) = LOWER(%s) AND LOWER(m.documento_numero) IN %s
                """
                params_inv = [negocio_id, tipo_doc, tuple(v.lower() for v in num_variants)]
        
        rows_inv = conn.execute(sql_inv, tuple(params_inv)).fetchall()
        if not rows_inv and tipo_documento_id:
            # Fallback legacy if no rows found with tipo_documento_id
            sql_inv_fallback = """
                SELECT m.id, m.producto_id, m.nombre_producto, m.tipo, m.motivo, m.cantidad, 
                       m.valor_unitario, m.valor_total, m.iva_pct, m.created_at, m.documento_fecha,
                       m.proveedor_id, m.proveedor_nombre, m.producto_padre_id,
                       p_padre.nombre AS producto_padre_nombre, m.costo_und
                FROM movimientos_inventario m
                LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
                WHERE m.negocio_id = %s AND LOWER(m.tipo_documento) = LOWER(%s) AND LOWER(m.documento_numero) IN %s
            """
            rows_inv = conn.execute(sql_inv_fallback, (negocio_id, tipo_doc, tuple(v.lower() for v in num_variants))).fetchall()
        items_inventario = [
            {
                'id': r['id'],
                'producto_id': r['producto_id'],
                'nombre_producto': r['nombre_producto'],
                'tipo': r['tipo'],
                'motivo': r['motivo'],
                'cantidad': float(r['cantidad']),
                'valor_unitario': float(r['valor_unitario'] if r['valor_unitario'] is not None else float(r['costo_und'] or 0)),
                'valor_total': float(r['valor_total'] if r['valor_total'] is not None else (float(r['cantidad'] or 0) * float(r['costo_und'] or 0))),
                'iva_pct': float(r['iva_pct'] or 0),
                'created_at': r['created_at'].isoformat() if r['created_at'] else None,
                'documento_fecha': r['documento_fecha'].isoformat() if r['documento_fecha'] else None,
                'proveedor_id': r['proveedor_id'],
                'proveedor_nombre': r['proveedor_nombre'],
                'producto_padre_id': r['producto_padre_id'],
                'producto_padre_nombre': r['producto_padre_nombre']
            } for r in rows_inv
        ]
        
        # 2. Query comprobantes_contables and movimientos_contables
        if tipo_documento_id:
            comp_row = conn.execute("""
                SELECT id, numero_comprobante, tipo, fecha, descripcion, total_debitos, total_creditos, notas
                FROM comprobantes_contables
                WHERE negocio_id = %s AND tipo_documento_id = %s AND (numero_comprobante IN %s OR origen_id IN %s)
                LIMIT 1
            """, (negocio_id, tipo_documento_id, tuple(num_variants), tuple(num_variants))).fetchone()
            
            # Fallback if no row found with tipo_documento_id (e.g. manually uploaded vouchers where tipo_documento_id is null)
            # We strictly filter by tipo or tipo_documento_id to avoid matching wrong documents with the same numeric suffix (like FACTURA_DE_VENTA-1 instead of GASTO_DE_ENTREGAS-1)
            if not comp_row:
                comp_row = conn.execute("""
                    SELECT id, numero_comprobante, tipo, fecha, descripcion, total_debitos, total_creditos, notas
                    FROM comprobantes_contables
                    WHERE negocio_id = %s 
                      AND (tipo_documento_id = %s OR LOWER(tipo) = LOWER(%s))
                      AND (
                        numero_comprobante IN %s 
                        OR origen_id IN %s 
                        OR numero_documento = %s
                      )
                    LIMIT 1
                """, (negocio_id, tipo_documento_id, tipo_doc, tuple(num_variants), tuple(num_variants), num_doc)).fetchone()

        else:
            # Fallback legacy
            origen_id_str = f"{tipo_doc}:{num_doc}"
            pedido_id_str = str(pedido_row['id']) if pedido_row else None
            comp_row = conn.execute("""
                SELECT id, numero_comprobante, tipo, fecha, descripcion, total_debitos, total_creditos, notas
                FROM comprobantes_contables
                WHERE negocio_id = %s AND (
                    (origen_tipo = 'pedido' AND origen_id = %s)
                    OR (origen_tipo IS NOT NULL AND LOWER(origen_id) IN %s)
                    OR (numero_comprobante IN %s)
                )
                LIMIT 1
            """, (negocio_id, pedido_id_str, tuple(v.lower() for v in num_variants), tuple(num_variants))).fetchone()
            
        comprobante = None
        if comp_row:
            entries = conn.execute("""
                SELECT mc.id, mc.cuenta_id, mc.cuenta, mc.concepto, mc.tipo, mc.monto
                FROM movimientos_contables mc
                WHERE mc.negocio_id = %s AND mc.comprobante_id = %s
                ORDER BY mc.tipo DESC, mc.id
            """, (negocio_id, comp_row['id'])).fetchall()
            
            comprobante = {
                'id': comp_row['id'],
                'numero_comprobante': comp_row['numero_comprobante'],
                'tipo': comp_row['tipo'],
                'fecha': comp_row['fecha'].isoformat() if comp_row['fecha'] else None,
                'descripcion': comp_row['descripcion'],
                'total_debitos': float(comp_row['total_debitos'] or 0),
                'total_creditos': float(comp_row['total_creditos'] or 0),
                'notas': comp_row['notas'],
                'documento_fisico': num_doc
            }
            
            # If we don't have detailed entries but we have the comprobante list, render seats
            comprobante['asientos'] = [
                {
                    'id': e['id'],
                    'cuenta_id': e['cuenta_id'],
                    'cuenta': e['cuenta'],
                    'concepto': e['concepto'],
                    'tipo': 'D' if e['tipo'] == 'debito' else 'C',
                    'monto': float(e['monto'] or 0)
                } for e in entries
            ]
        
        # 3. Query sales (pedidos & pedido_items)
        pedido = None
        if pedido_row:
            p_items = conn.execute("""
                SELECT pi.id, pi.producto_id, pi.nombre_producto, pi.cantidad, pi.precio_unitario
                FROM pedido_items pi
                WHERE pi.pedido_id = %s
            """, (pedido_row['id'],)).fetchall()
            
            cliente_nombre = None
            c_tercero_id = pedido_row['cliente_id'] or pedido_row['id_tercero']
            if c_tercero_id:
                cli_row = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (c_tercero_id,)).fetchone()
                if cli_row:
                    cliente_nombre = cli_row['nombre']
            else:
                cliente_nombre = pedido_row['nombre_cliente']
                
            pedido = {
                'id': pedido_row['id'],
                'fecha': pedido_row['fecha'].isoformat() if pedido_row['fecha'] else (pedido_row['created_at'].isoformat() if pedido_row['created_at'] else None),
                'total': float(pedido_row['total'] or 0),
                'metodo_pago': pedido_row['metodo_pago'],
                'estado': pedido_row['estado'] or 'registrado',
                'notas': pedido_row['notas'],
                'cliente_nombre': cliente_nombre or 'Cliente en local',
                'tercero_id': c_tercero_id,
                'items': [
                    {
                        'id': pi['id'],
                        'producto_id': pi['producto_id'],
                        'nombre_producto': pi['nombre_producto'],
                        'cantidad': float(pi['cantidad']),
                        'precio_unitario': float(pi['precio_unitario'] or 0),
                        'subtotal': float(pi['cantidad'] or 0) * float(pi['precio_unitario'] or 0)
                    } for pi in p_items
                ]
            }
        else:
            # Fallback to query by ID if num_doc is numeric
            pedido_id = None
            try:
                pedido_id = int(num_doc)
            except ValueError:
                pass
            
            if pedido_id:
                ped_row = conn.execute("""
                    SELECT p.id, p.fecha, p.total, p.metodo_pago, p.estado, p.notas, p.cliente_id, p.id_tercero, p.nombre_cliente
                    FROM pedidos p
                    WHERE p.id = %s AND p.negocio_id = %s
                    LIMIT 1
                """, (pedido_id, negocio_id)).fetchone()
                
                if ped_row:
                    p_items = conn.execute("""
                        SELECT pi.id, pi.producto_id, pi.nombre_producto, pi.cantidad, pi.precio_unitario
                        FROM pedido_items pi
                        WHERE pi.pedido_id = %s
                    """, (pedido_id,)).fetchall()
                    
                    cliente_nombre = None
                    c_tercero_id = ped_row['cliente_id'] or ped_row['id_tercero']
                    if c_tercero_id:
                        cli_row = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (c_tercero_id,)).fetchone()
                        if cli_row:
                            cliente_nombre = cli_row['nombre']
                    else:
                        cliente_nombre = ped_row['nombre_cliente']
                        
                    pedido = {
                        'id': ped_row['id'],
                        'fecha': ped_row['fecha'].isoformat() if ped_row['fecha'] else None,
                        'total': float(ped_row['total'] or 0),
                        'metodo_pago': ped_row['metodo_pago'],
                        'estado': ped_row['estado'],
                        'notas': ped_row['notas'],
                        'cliente_nombre': cliente_nombre or 'Cliente en local',
                        'tercero_id': c_tercero_id,
                        'items': [
                            {
                                'id': pi['id'],
                                'producto_id': pi['producto_id'],
                                'nombre_producto': pi['nombre_producto'],
                                'cantidad': float(pi['cantidad']),
                                'precio_unitario': float(pi['precio_unitario'] or 0),
                                'subtotal': float(pi['cantidad'] or 0) * float(pi['precio_unitario'] or 0)
                            } for pi in p_items
                        ]
                    }
        
        # 4. Query pending balance in saldo_por_documentos
        t_id = proveedor_id or (pedido['tercero_id'] if pedido else None) or (items_inventario[0]['proveedor_id'] if items_inventario else None)
        saldo_row = None
        if t_id:
            saldo_row = conn.execute("""
                SELECT saldo, monto_original FROM saldo_por_documentos
                WHERE negocio_id = %s AND tercero_id = %s AND (
                    tipo_documento = %s 
                    OR (tipo_documento_id IS NOT NULL AND tipo_documento_id = %s)
                ) AND numero_documento = %s
            """, (negocio_id, t_id, tipo_doc, pedido_row['tipo_documento_id'] if pedido_row else None, num_doc)).fetchone()
        else:
            saldo_row = conn.execute("""
                SELECT saldo, monto_original FROM saldo_por_documentos
                WHERE negocio_id = %s AND tipo_documento = %s AND numero_documento = %s
            """, (negocio_id, tipo_doc, num_doc)).fetchone()
            
        saldo_pendiente = float(saldo_row['saldo']) if (saldo_row and saldo_row['saldo'] is not None) else None
        monto_original = float(saldo_row['monto_original']) if (saldo_row and saldo_row['monto_original'] is not None) else None
        
        return jsonify({
            'ok': True,
            'existe': bool(items_inventario or comprobante or pedido),
            'inventario': items_inventario,
            'contabilidad': comprobante,
            'ventas': pedido,
            'saldo_pendiente': saldo_pendiente,
            'monto_original': monto_original
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/anular-documento', methods=['POST'])
def api_anular_documento(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    data = request.get_json() or {}
    tipo_doc = _txt(data.get('tipo_documento'))
    num_doc = _txt(data.get('documento_numero'))
    proveedor_id = data.get('proveedor_id')
    
    if not tipo_doc or not num_doc:
        return jsonify({'ok': False, 'error': 'tipo_documento y documento_numero son requeridos'}), 400
    
    conn = get_db_connection()
    try:
        deleted_inventario = 0
        deleted_contables = 0
        deleted_comprobantes = 0
        pedido_anulado = False
        
        # Look up the order in `pedidos` if it exists
        pedido_row = None
        try:
            pedido_id = int(num_doc)
            pedido_row = conn.execute("SELECT * FROM pedidos WHERE id = %s AND negocio_id = %s", (pedido_id, negocio_id)).fetchone()
        except ValueError:
            pass

        if not pedido_row:
            pedido_row = conn.execute("SELECT * FROM pedidos WHERE UPPER(numero_documento) = UPPER(%s) AND negocio_id = %s", (num_doc, negocio_id)).fetchone()
        
        # Get inventory movement IDs to be deleted, and their product IDs (for recosteo!)
        if pedido_row:
            sql_inv = """
                SELECT id, producto_id, proveedor_id
                FROM movimientos_inventario
                WHERE negocio_id = %s AND (
                    (referencia_tipo IN ('pedido', 'pedido_tienda', 'pedido_restaurante') AND referencia_id = %s)
                    OR (LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s))
                )
            """
            params_inv = [negocio_id, pedido_row['id'], tipo_doc, num_doc]
        else:
            sql_inv = """
                SELECT id, producto_id, proveedor_id
                FROM movimientos_inventario
                WHERE negocio_id = %s AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s)
            """
            params_inv = [negocio_id, tipo_doc, num_doc]
        
        movs = conn.execute(sql_inv, tuple(params_inv)).fetchall()
        mov_ids = [m['id'] for m in movs]
        prod_ids = list({m['producto_id'] for m in movs})
        p_id = proveedor_id or (pedido_row['cliente_id'] or pedido_row['id_tercero'] if pedido_row else None) or (movs[0]['proveedor_id'] if movs else None)
        
        # Delete inventory movements
        if mov_ids:
            placeholders = ','.join(['%s'] * len(mov_ids))
            conn.execute(f"DELETE FROM movimientos_inventario WHERE id IN ({placeholders})", tuple(mov_ids))
            deleted_inventario = len(mov_ids)
            
        # Delete pending balance record
        if p_id:
            conn.execute("""
                DELETE FROM saldo_por_documentos
                WHERE negocio_id = %s AND tercero_id = %s AND (
                    tipo_documento = %s
                    OR (tipo_documento_id IS NOT NULL AND tipo_documento_id = %s)
                ) AND numero_documento = %s
            """, (negocio_id, p_id, tipo_doc, pedido_row['tipo_documento_id'] if pedido_row else None, num_doc))
        else:
            conn.execute("""
                DELETE FROM saldo_por_documentos
                WHERE negocio_id = %s AND tipo_documento = %s AND numero_documento = %s
            """, (negocio_id, tipo_doc, num_doc))

        # Delete purchase cotizaciones generated by this entry
        if p_id:
            conn.execute("""
                DELETE FROM cotizaciones_compras
                WHERE negocio_id = %s AND tercero_id = %s AND numero_cotizacion = %s AND origen = 'compra'
            """, (negocio_id, p_id, num_doc))
        
        # Delete accounting vouchers & entries
        origen_id_str = f"{tipo_doc}:{num_doc}"
        pedido_id_str = str(pedido_row['id']) if pedido_row else None
        
        comp_rows = conn.execute("""
            SELECT id FROM comprobantes_contables
            WHERE negocio_id = %s AND (
                (origen_tipo = 'pedido' AND origen_id = %s)
                OR (origen_tipo IS NOT NULL AND LOWER(origen_id) = LOWER(%s))
                OR (numero_comprobante ILIKE %s)
            )
        """, (negocio_id, pedido_id_str, origen_id_str, f'%{num_doc}%')).fetchall()
        comp_ids = [c['id'] for c in comp_rows]
        
        if comp_ids:
            placeholders = ','.join(['%s'] * len(comp_ids))
            cur_mc = conn.execute(f"DELETE FROM movimientos_contables WHERE comprobante_id IN ({placeholders})", tuple(comp_ids))
            deleted_contables = cur_mc.rowcount
            cur_cc = conn.execute(f"DELETE FROM comprobantes_contables WHERE id IN ({placeholders})", tuple(comp_ids))
            deleted_comprobantes = cur_cc.rowcount
            
        # Action handler: 'anular' (default) vs 'eliminar'
        accion = _txt(data.get('accion') or 'anular').lower()
        pedido_eliminado = False
        pedido_anulado = False
        consecutivo_liberado = False

        if not pedido_row:
            pedido_id_val = None
            try:
                pedido_id_val = int(num_doc)
            except ValueError:
                pass
            if pedido_id_val:
                pedido_row = conn.execute("SELECT * FROM pedidos WHERE id = %s AND negocio_id = %s LIMIT 1", (pedido_id_val, negocio_id)).fetchone()

        if pedido_row:
            if accion == 'eliminar':
                # Check if it is the latest order to free consecutive
                if pedido_row['tipo_documento_id']:
                    latest_row = conn.execute("""
                        SELECT id FROM pedidos
                        WHERE negocio_id = %s AND tipo_documento_id = %s
                        ORDER BY id DESC LIMIT 1
                    """, (negocio_id, pedido_row['tipo_documento_id'])).fetchone()
                    
                    if latest_row and latest_row['id'] == pedido_row['id']:
                        td_row = conn.execute("SELECT id, consecutivo FROM tipos_documento_negocio WHERE id = %s", (pedido_row['tipo_documento_id'],)).fetchone()
                        if td_row and td_row['consecutivo'] and td_row['consecutivo'] > 0:
                            new_con = td_row['consecutivo'] - 1
                            conn.execute("UPDATE tipos_documento_negocio SET consecutivo = %s WHERE id = %s", (new_con, td_row['id']))
                            consecutivo_liberado = True
                
                # Delete completely
                conn.execute("DELETE FROM pedido_items WHERE pedido_id = %s", (pedido_row['id'],))
                conn.execute("DELETE FROM pedido_pagos WHERE pedido_id = %s", (pedido_row['id'],))
                conn.execute("DELETE FROM pedidos WHERE id = %s", (pedido_row['id'],))
                pedido_eliminado = True
            else:
                # Void sales order
                conn.execute("UPDATE pedidos SET estado = 'anulado' WHERE id = %s", (pedido_row['id'],))
                pedido_anulado = True
                
        # Recosteo: Recalculate stock and average cost for all affected products
        for prod_id in prod_ids:
            _recostear_producto(conn, negocio_id, prod_id)
            
        conn.commit()
        return jsonify({
            'ok': True,
            'deleted_inventario': deleted_inventario,
            'deleted_contables': deleted_contables,
            'deleted_comprobantes': deleted_comprobantes,
            'pedido_anulado': pedido_anulado,
            'pedido_eliminado': pedido_eliminado,
            'consecutivo_liberado': consecutivo_liberado
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/admin/inventario/<int:negocio_id>')
def admin_inventario(negocio_id):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto:
            return "Negocio no encontrado", 404
        if not _puede_gestionar_negocio(contexto):
            return "No autorizado para este negocio", 403
        return render_template('inventario_admin.html',
                               negocio_id=negocio_id,
                               negocio_nombre=contexto['negocio_nombre'],
                               volver_url=contexto['volver_url'],
                               volver_label=contexto['volver_label'])
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/admin/mantenimiento/<int:negocio_id>')
def admin_negocio_mantenimiento(negocio_id):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto:
            return "Negocio no encontrado", 404
        if not _puede_gestionar_negocio(contexto):
            return "No autorizado para este negocio", 403
        return render_template('mantenimiento_admin.html',
                               negocio_id=negocio_id,
                               negocio_nombre=contexto['negocio_nombre'],
                               volver_url=contexto['volver_url'],
                               volver_label=contexto['volver_label'])
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/unificar-terceros', methods=['POST'])
def api_unificar_terceros(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto or not _puede_gestionar_negocio(contexto):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
            
        data = request.get_json() or {}
        principal_id = _int_o_none(data.get('principal_id'))
        sobrantes_ids = data.get('sobrantes_ids', [])
        
        # Clean and validate IDs
        sobrantes_ids = [int(x) for x in sobrantes_ids if _int_o_none(x) is not None]
        
        if not principal_id:
            return jsonify({'ok': False, 'error': 'Debe seleccionar el tercero principal'}), 400
        if not sobrantes_ids:
            return jsonify({'ok': False, 'error': 'Debe seleccionar al menos un tercero sobrante'}), 400
        if principal_id in sobrantes_ids:
            return jsonify({'ok': False, 'error': 'El tercero principal no puede estar en la lista de sobrantes'}), 400
            
        # Verify principal exists
        p_row = conn.execute("SELECT id, nombre FROM terceros WHERE id = %s", (principal_id,)).fetchone()
        if not p_row:
            return jsonify({'ok': False, 'error': 'El tercero principal no existe'}), 400
            
        # Verify sobrantes exist
        placeholders = ', '.join(['%s'] * len(sobrantes_ids))
        s_rows = conn.execute(f"SELECT id, nombre FROM terceros WHERE id IN ({placeholders})", tuple(sobrantes_ids)).fetchall()
        if len(s_rows) != len(sobrantes_ids):
            return jsonify({'ok': False, 'error': 'Uno o más terceros sobrantes no existen'}), 400
            
        # Start transaction to merge
        principal_nombre = p_row['nombre']
        
        # 1. Update movimientos_inventario (both ID and name)
        conn.execute(f"""
            UPDATE movimientos_inventario 
            SET proveedor_id = %s, proveedor_nombre = %s
            WHERE proveedor_id IN ({placeholders})
        """, (principal_id, principal_nombre) + tuple(sobrantes_ids))
        
        # 2. Update cotizaciones
        conn.execute(f"""
            UPDATE cotizaciones_compras 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # 3. Update movimientos_contables
        conn.execute(f"""
            UPDATE movimientos_contables 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # 4. Update pedidos (clients, cajeros, names)
        conn.execute(f"""
            UPDATE pedidos 
            SET cliente_id = CASE WHEN cliente_id IN ({placeholders}) THEN %s ELSE cliente_id END,
                id_tercero = CASE WHEN id_tercero IN ({placeholders}) THEN %s ELSE id_tercero END,
                nombre_cliente = CASE WHEN (cliente_id IN ({placeholders}) OR id_tercero IN ({placeholders})) THEN %s ELSE nombre_cliente END
        """, tuple(sobrantes_ids) + (principal_id,) + tuple(sobrantes_ids) + (principal_id,) + tuple(sobrantes_ids) + tuple(sobrantes_ids) + (principal_nombre,))
        
        # 5. Update saldo_por_documentos
        conn.execute(f"""
            UPDATE saldo_por_documentos 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # 6. Update contactos
        conn.execute(f"""
            UPDATE contactos 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # 7. Update terceros_direcciones
        conn.execute(f"""
            UPDATE terceros_direcciones 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))

        # 8. Update other tables that might refer to third parties
        for tbl in ['colaboradores_entrega', 'config_negocio', 'restaurantes', 'tiendas', 'tienda_cajeros', 'rockola_biblioteca', 'rockola_cola', 'solicitudes_transporte']:
            conn.execute(f"""
                UPDATE {tbl} 
                SET tercero_id = %s 
                WHERE tercero_id IN ({placeholders})
            """, (principal_id,) + tuple(sobrantes_ids))
            
        # 9. Delete duplicates from terceros
        conn.execute(f"""
            DELETE FROM terceros 
            WHERE id IN ({placeholders})
        """, tuple(sobrantes_ids))
        
        conn.commit()
        return jsonify({'ok': True, 'mensaje': f'Se han unificado {len(sobrantes_ids)} terceros en "{p_row["nombre"]}"'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/documento/consultar')
def api_consultar_documento_existente(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    tipo_doc = request.args.get('tipo_documento', '').strip()
    num_doc = request.args.get('documento_numero', '').strip()
    proveedor_id = _int_o_none(request.args.get('proveedor_id'))
    proveedor_nombre = request.args.get('proveedor_nombre', '').strip()
    
    if not tipo_doc or not num_doc:
        return jsonify({'ok': False, 'error': 'Tipo y número de documento requeridos'}), 400
        
    conn = get_db_connection()
    try:
        tipo_doc_id = _int_o_none(tipo_doc)
        if not tipo_doc_id and tipo_doc:
            td_row = conn.execute("""
                SELECT id FROM tipos_documento_negocio
                WHERE negocio_id = %s AND (UPPER(nombre) = %s OR UPPER(codigo) = %s)
                LIMIT 1
            """, (negocio_id, tipo_doc.upper(), tipo_doc.upper())).fetchone()
            if td_row:
                tipo_doc_id = td_row['id']

        # Alternativas de tipos de documentos heredados (legacy)
        tipo_names = [tipo_doc.lower()]
        if tipo_doc_id == 1:
            tipo_names.extend(['factura de proveedor', 'factura proveedor', 'factura'])
        elif tipo_doc_id == 3:
            tipo_names.extend(['ajuste de inventario', 'ajuste entrada', 'ajuste'])

        # Resolver todas las variantes posibles del número de documento
        num_variants = resolver_variantes_numero(num_doc)

        # Check if there is any movement with this key
        query_base = """
SELECT m.id, m.producto_id, m.nombre_producto, m.cantidad, m.valor_unitario, m.iva_pct, m.notas,
       m.presentacion_id, p_pres.nombre AS presentacion_nombre, p_pres.equivalencia AS presentacion_equivalencia
FROM movimientos_inventario m
LEFT JOIN presentaciones p_pres ON p_pres.id = m.presentacion_id
WHERE m.negocio_id = %s AND m.tipo = 'entrada'
AND (m.tipo_documento_id = %s OR (m.tipo_documento_id IS NULL AND LOWER(m.tipo_documento) IN %s))
AND LOWER(m.documento_numero) IN %s
"""
        params = [negocio_id, tipo_doc_id, tuple(tipo_names), tuple(v.lower() for v in num_variants)]

        if proveedor_id:
            query_base += " AND m.proveedor_id = %s"
            params.append(proveedor_id)
        elif proveedor_nombre:
            query_base += " AND LOWER(m.proveedor_nombre) = LOWER(%s)"
            params.append(proveedor_nombre)

        query = query_base + " ORDER BY m.id"
        rows = conn.execute(query, tuple(params)).fetchall()
        if not rows:
            return jsonify({'ok': True, 'existe': False})
            
        # Get notes and date from first movement
        notes_query = """
SELECT notas, documento_fecha, created_at FROM movimientos_inventario
WHERE negocio_id = %s AND tipo = 'entrada' 
AND (tipo_documento_id = %s OR (tipo_documento_id IS NULL AND LOWER(tipo_documento) IN %s))
AND LOWER(documento_numero) IN %s
"""
        notes_params = [negocio_id, tipo_doc_id, tuple(tipo_names), tuple(v.lower() for v in num_variants)]
        
        if proveedor_id:
            notes_query += " AND proveedor_id = %s"
            notes_params.append(proveedor_id)
        elif proveedor_nombre:
            notes_query += " AND LOWER(proveedor_nombre) = LOWER(%s)"
            notes_params.append(proveedor_nombre)
            
        notes_query += " LIMIT 1"
        first_row = conn.execute(notes_query, tuple(notes_params)).fetchone()
        notes = first_row['notas'] if (first_row and 'notas' in first_row) else ''
        
        doc_date = None
        if first_row:
            if first_row['documento_fecha']:
                doc_date = first_row['documento_fecha'].isoformat()
            elif first_row['created_at']:
                doc_date = first_row['created_at'].strftime('%Y-%m-%d')
            
        return jsonify({
            'ok': True,
            'existe': True,
            'notas': notes,
            'fecha': doc_date,
            'items': [{
                'producto_id': r['producto_id'],
                'nombre_producto': r['nombre_producto'],
                'cantidad': float(r['cantidad']),
                'valor_unitario': float(r['valor_unitario'] or 0),
                'iva_pct': float(r['iva_pct'] or 0),
                'notas': r['notas'],
                'presentacion_id': r['presentacion_id'],
                'presentacion_nombre': r['presentacion_nombre'] or '',
                'presentacion_equivalencia': float(r['presentacion_equivalencia'] or 1.0)
            } for r in rows]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/tarjetas-resumen')
def api_inventario_tarjetas_resumen(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
            
        # 1. Fetch all products
        productos = conn.execute("""
            SELECT id, nombre, categoria, precio, costo AS costo_base 
            FROM productos 
            WHERE negocio_id = %s
            ORDER BY nombre
        """, (negocio_id,)).fetchall()
        
        # 2. Fetch all recipe lines for this business
        recipe_lines = conn.execute("""
            SELECT te.producto_id, te.componente_id, te.cantidad,
                   p.nombre AS componente_nombre,
                   COALESCE(s.costo_und, p.costo, 0) AS costo_und
            FROM tarjeta_estandar te
            JOIN productos prod ON prod.id = te.producto_id
            JOIN productos p ON p.id = te.componente_id
            LEFT JOIN (
                SELECT DISTINCT ON (producto_id, negocio_id) producto_id, negocio_id, costo_und
                FROM saldos_inventario
                WHERE bodega = 1
                ORDER BY producto_id, negocio_id, id DESC
            ) s ON s.producto_id = te.componente_id AND s.negocio_id = prod.negocio_id
            WHERE prod.negocio_id = %s
            ORDER BY te.id ASC
        """, (negocio_id,)).fetchall()
        
        # Group recipe lines by product_id
        recipes_by_prod = {}
        for r in recipe_lines:
            pid = r['producto_id']
            if pid not in recipes_by_prod:
                recipes_by_prod[pid] = []
            recipes_by_prod[pid].append(r)
            
        # 3. Assemble response list
        resumen = []
        for p in productos:
            pid = p['id']
            lines = recipes_by_prod.get(pid, [])
            tiene_tarjeta = len(lines) > 0
            
            costo_total = Decimal('0')
            componentes_list = []
            
            if tiene_tarjeta:
                for line in lines:
                    cant = Decimal(str(line['cantidad']))
                    costo_u = Decimal(str(line['costo_und']))
                    line_cost = cant * costo_u
                    costo_total += line_cost
                    componentes_list.append({
                        'componente_id': line['componente_id'],
                        'nombre': line['componente_nombre'],
                        'cantidad': float(cant),
                        'costo_und': float(costo_u),
                        'costo_total': float(line_cost)
                    })
            else:
                costo_total = Decimal(str(p['costo_base'] or 0))
                
            precio = Decimal(str(p['precio'] or 0))
            margen_usd = precio - costo_total
            margen_pct = (margen_usd / precio * 100) if precio > 0 else Decimal('0')
            
            resumen.append({
                'id': pid,
                'nombre': p['nombre'],
                'categoria': p['categoria'],
                'precio': float(precio),
                'tiene_tarjeta': tiene_tarjeta,
                'costo_total': float(costo_total),
                'margen_usd': float(margen_usd),
                'margen_pct': float(margen_pct),
                'componentes': componentes_list
            })
            
        return jsonify({'ok': True, 'productos': resumen})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/presentaciones/buscar')
def api_presentaciones_buscar():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    q = request.args.get('q', '').strip()
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        query_sql = """
            SELECT id, nombre, equivalencia 
            FROM presentaciones
        """
        params = []
        if q:
            try:
                val = float(q)
                query_sql += " WHERE nombre ILIKE %s OR equivalencia = %s"
                params = [f"%{q}%", val]
            except ValueError:
                query_sql += " WHERE nombre ILIKE %s"
                params = [f"%{q}%"]
        
        query_sql += " ORDER BY nombre ASC LIMIT 50"
        rows = conn.execute(query_sql, tuple(params)).fetchall()
        
        return jsonify({
            'ok': True,
            'presentaciones': [{
                'id': r['id'],
                'nombre': r['nombre'],
                'equivalencia': float(r['equivalencia'])
            } for r in rows]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/presentaciones/crear', methods=['POST'])
def api_presentaciones_crear():
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    nombre = (data.get('nombre') or '').strip()
    try:
        equivalencia = Decimal(str(data.get('equivalencia') or 1.0))
    except Exception:
        equivalencia = Decimal('1.0')
        
    if not nombre or equivalencia <= 0:
        return jsonify({'ok': False, 'error': 'Nombre y equivalencia válidos requeridos'}), 400
        
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        existente = conn.execute("""
            SELECT id, nombre, equivalencia FROM presentaciones
            WHERE LOWER(nombre) = LOWER(%s) AND equivalencia = %s
            LIMIT 1
        """, (nombre, float(equivalencia))).fetchone()
        
        if existente:
            return jsonify({
                'ok': True,
                'presentacion': {
                    'id': existente['id'],
                    'nombre': existente['nombre'],
                    'equivalencia': float(existente['equivalencia'])
                }
            })
            
        row = conn.execute("""
            INSERT INTO presentaciones (nombre, equivalencia)
            VALUES (%s, %s)
            RETURNING id, nombre, equivalencia
        """, (nombre, float(equivalencia))).fetchone()
        conn.commit()
        
        return jsonify({
            'ok': True,
            'presentacion': {
                'id': row['id'],
                'nombre': row['nombre'],
                'equivalencia': float(row['equivalencia'])
            }
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/producto/<int:producto_id>/proveedor/<int:proveedor_id>/ultima-presentacion')
def api_ultima_presentacion(negocio_id, producto_id, proveedor_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT c.presentacion_id, p.nombre AS presentacion_nombre, p.equivalencia
            FROM cotizaciones_compras c
            JOIN presentaciones p ON p.id = c.presentacion_id
            WHERE c.negocio_id = %s AND c.tercero_id = %s AND c.item_id = %s
            ORDER BY c.fecha_cotizacion DESC, c.id DESC
            LIMIT 1
        """, (negocio_id, proveedor_id, producto_id)).fetchone()
        
        if row:
            return jsonify({
                'ok': True,
                'encontrada': True,
                'presentacion_id': row['presentacion_id'],
                'presentacion_nombre': row['presentacion_nombre'],
                'equivalencia': float(row['equivalencia'])
            })
            
        u_row = conn.execute("""
            SELECT id, nombre, equivalencia FROM presentaciones
            WHERE LOWER(nombre) = 'unidad' AND equivalencia = 1.0
            LIMIT 1
        """).fetchone()
        
        if u_row:
            return jsonify({
                'ok': True,
                'encontrada': False,
                'presentacion_id': u_row['id'],
                'presentacion_nombre': u_row['nombre'],
                'equivalencia': float(u_row['equivalencia'])
            })
            
        return jsonify({'ok': True, 'encontrada': False, 'presentacion_id': None, 'presentacion_nombre': 'Unidad', 'equivalencia': 1.0})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/produccion/historial')
def api_produccion_historial(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT m.id, m.producto_id, m.nombre_producto, m.cantidad, m.valor_unitario, m.valor_total,
                   m.documento_numero, m.tipo_documento_id, tdn.nombre AS tipo_documento_nombre, 
                   m.created_at, m.referencia_id AS prod_token, m.notas
            FROM movimientos_inventario m
            LEFT JOIN tipos_documento_negocio tdn ON tdn.id = m.tipo_documento_id
            WHERE m.negocio_id = %s AND m.tipo = 'entrada' AND m.referencia_tipo = 'produccion'
            ORDER BY m.id DESC
            LIMIT 50
        """, (negocio_id,)).fetchall()
        
        historial = []
        for r in rows:
            fecha_str = r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else ''
            historial.append({
                'id': r['id'],
                'producto_id': r['producto_id'],
                'producto_nombre': r['nombre_producto'],
                'cantidad': float(r['cantidad']),
                'valor_unitario': float(r['valor_unitario'] or 0),
                'valor_total': float(r['valor_total'] or 0),
                'documento_numero': r['documento_numero'],
                'tipo_documento_id': r['tipo_documento_id'],
                'tipo_documento_nombre': r['tipo_documento_nombre'] or 'PRODUCCIÓN',
                'fecha': fecha_str,
                'prod_token': r['prod_token'],
                'notas': r['notes'] if 'notes' in r else r['notas']
            })
        return jsonify({'ok': True, 'historial': historial})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/produccion/<int:prod_token>/imprimir')
def api_produccion_imprimir(negocio_id, prod_token):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    try:
        # 1. Buscar negocio
        negocio = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (negocio_id,)).fetchone()
        negocio_nombre = negocio['nombre'] if negocio else 'Mi Negocio'
        
        # 2. Buscar terminado
        terminado = conn.execute("""
            SELECT m.*, tdn.nombre AS tipo_documento_nombre
            FROM movimientos_inventario m
            LEFT JOIN tipos_documento_negocio tdn ON tdn.id = m.tipo_documento_id
            WHERE m.negocio_id = %s AND m.tipo = 'entrada' AND m.referencia_tipo = 'produccion' AND m.referencia_id = %s
            LIMIT 1
        """, (negocio_id, prod_token)).fetchone()
        
        if not terminado:
            return "No se encontró el registro de producción especificado.", 404
            
        # 3. Buscar componentes
        componentes = conn.execute("""
            SELECT m.*
            FROM movimientos_inventario m
            WHERE m.negocio_id = %s AND m.tipo = 'salida' AND m.referencia_tipo = 'produccion' AND m.referencia_id = %s
            ORDER BY m.id ASC
        """, (negocio_id, prod_token)).fetchall()
        
        fecha_doc = terminado['created_at'].strftime('%Y-%m-%d %H:%M') if terminado['created_at'] else ''
        total_insumos = sum(float(c['valor_total'] or 0) for c in componentes)
        
        return render_template(
            'produccion_print.html',
            negocio_nombre=negocio_nombre,
            terminado=terminado,
            componentes=componentes,
            fecha_doc=fecha_doc,
            total_insumos=total_insumos,
            consecutivo=terminado['documento_numero'] or f"PROD-{prod_token}",
            tipo_documento_nombre=terminado['tipo_documento_nombre'] or 'PRODUCCIÓN'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error al generar la impresión: {e}", 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/produccion/<int:prod_token>/anular', methods=['POST'])
def api_anular_produccion(negocio_id, prod_token):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    conn = get_db_connection()
    try:
        # Get all movements for this production to identify products
        movs = conn.execute("""
            SELECT id, producto_id
            FROM movimientos_inventario
            WHERE negocio_id = %s AND referencia_tipo = 'produccion' AND referencia_id = %s
        """, (negocio_id, str(prod_token))).fetchall()
        
        if not movs:
            # Fallback check if it was stored as integer
            movs = conn.execute("""
                SELECT id, producto_id
                FROM movimientos_inventario
                WHERE negocio_id = %s AND referencia_tipo = 'produccion' AND (referencia_id = %s OR referencia_id = %s)
            """, (negocio_id, str(prod_token), f"{prod_token}")).fetchall()
            
        if not movs:
            return jsonify({'ok': False, 'error': 'No se encontraron movimientos para esta producción'}), 404
            
        prod_ids = list({m['producto_id'] for m in movs})
        mov_ids = [m['id'] for m in movs]
        
        # 1. Delete inventory movements
        placeholders = ','.join(['%s'] * len(mov_ids))
        conn.execute(f"DELETE FROM movimientos_inventario WHERE id IN ({placeholders})", tuple(mov_ids))
        
        # 2. Delete accounting entry (vouchers)
        comp_rows = conn.execute("""
            SELECT id FROM comprobantes_contables
            WHERE negocio_id = %s AND origen_tipo = 'produccion' AND (origen_id = %s OR origen_id = %s)
        """, (negocio_id, str(prod_token), f"{prod_token}")).fetchall()
        comp_ids = [c['id'] for c in comp_rows]
        if comp_ids:
            placeholders_cc = ','.join(['%s'] * len(comp_ids))
            conn.execute(f"DELETE FROM movimientos_contables WHERE comprobante_id IN ({placeholders_cc})", tuple(comp_ids))
            conn.execute(f"DELETE FROM comprobantes_contables WHERE id IN ({placeholders_cc})", tuple(comp_ids))
            
        # 3. Recosteo: Recalculate stock and average cost for all affected products
        for prod_id in prod_ids:
            _recostear_producto(conn, negocio_id, prod_id)
            
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Producción anulada y costos recalculados correctamente'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/ajuste-rapido', methods=['POST'])
def api_tienda_ajuste_rapido(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    data = request.get_json() or {}
    adjustments = data.get('adjustments', [])
    if not adjustments:
        return jsonify({'ok': False, 'error': 'No se enviaron ajustes'}), 400
        
    conn = get_db_connection()
    try:
        # 1. Resolve or create document type AJUSTE_INV
        td = conn.execute("""
            SELECT id, codigo, consecutivo FROM tipos_documento_negocio
            WHERE negocio_id = %s AND (UPPER(codigo) = 'AJUSTE_INV' OR UPPER(nombre) = 'AJUSTE DE INVENTARIO')
            LIMIT 1
        """, (negocio_id,)).fetchone()
        
        if not td:
            conn.execute("""
                INSERT INTO tipos_documento_negocio (negocio_id, nombre, codigo, tipo_movimiento, consecutivo, numero_inicio, activo, predeterminado)
                VALUES (%s, 'Ajuste de Inventario', 'AJUSTE_INV', 'ajuste', 0, 1, TRUE, FALSE)
            """, (negocio_id,))
            td = conn.execute("""
                SELECT id, codigo, consecutivo FROM tipos_documento_negocio
                WHERE negocio_id = %s AND UPPER(codigo) = 'AJUSTE_INV'
                LIMIT 1
            """, (negocio_id,)).fetchone()
            
        # 2. Get consecutive number using the standard generator
        res_num, es_interno = obtener_siguiente_consecutivo(conn, negocio_id, td['id'])
        if not res_num:
            res_num = str((td['consecutivo'] or 0) + 1)
            conn.execute("UPDATE tipos_documento_negocio SET consecutivo = %s WHERE id = %s", (int(res_num), td['id']))
            
        try:
            doc_num = f"AJUSTE_INV-{int(res_num)}"
        except (ValueError, TypeError):
            doc_num = f"AJUSTE_INV-{res_num}"
            
        # 3. Apply adjustments
        adjusted_products = []
        for adj in adjustments:
            prod_id = int(adj.get('producto_id') or 0)
            qty_physical = float(adj.get('cantidad_fisica') or 0.0)
            cost_unit = float(adj.get('costo_unitario') or 0.0)
            
            if not prod_id:
                continue
                
            # Get current stock
            saldo = conn.execute(
                "SELECT stock FROM saldos_inventario WHERE negocio_id = %s AND producto_id = %s AND bodega = 1",
                (negocio_id, prod_id)
            ).fetchone()
            qty_system = float(saldo['stock'] if saldo else 0.0)
            
            diff = qty_physical - qty_system
            if abs(diff) < 0.000001:
                continue
                
            if diff > 0:
                _mov_directo(conn, negocio_id, prod_id, diff, 'entrada', 'ajuste',
                             registrado_por=session.get('usuario_id'),
                             valor_unitario=cost_unit,
                             bodega=1,
                             tipo_documento='AJUSTE_INV',
                             documento_numero=doc_num,
                             tipo_documento_id=td['id'])
            else:
                _mov_directo(conn, negocio_id, prod_id, abs(diff), 'salida', 'ajuste',
                             registrado_por=session.get('usuario_id'),
                             valor_unitario=cost_unit,
                             bodega=1,
                             tipo_documento='AJUSTE_INV',
                             documento_numero=doc_num,
                             tipo_documento_id=td['id'])
                             
            adjusted_products.append(prod_id)
            
        # 4. Recalculate cost/stock for all affected products
        for p_id in adjusted_products:
            _recostear_producto(conn, negocio_id, p_id)
            
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Ajuste de inventario realizado con éxito', 'numero_documento': doc_num})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── NUEVOS ENDPOINTS: INVENTARIO FISICO Y CONTABILIZACION INDIVIDUAL ───────────────────

@bp.route('/admin/inventario-fisico/<int:negocio_id>')
def admin_inventario_fisico(negocio_id):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto:
            return "Negocio no encontrado", 404
        if not _puede_gestionar_negocio(contexto):
            return "No autorizado para este negocio", 403
            
        # Obtener los tipos de documento activos de tipo 'ajuste'
        tipos_doc = conn.execute("""
            SELECT id, nombre, codigo, predeterminado
            FROM tipos_documento_negocio
            WHERE negocio_id = %s AND activo = TRUE AND tipo_movimiento = 'ajuste'
            ORDER BY nombre
        """, (negocio_id,)).fetchall()
        
        # Si no existe ninguno, creamos uno predeterminado 'AJUSTE_INV'
        if not tipos_doc:
            td = conn.execute("""
                SELECT id, nombre, codigo, predeterminado
                FROM tipos_documento_negocio
                WHERE negocio_id = %s AND (UPPER(codigo) = 'AJUSTE_INV' OR UPPER(nombre) = 'AJUSTE DE INVENTARIO')
                LIMIT 1
            """, (negocio_id,)).fetchone()
            
            if not td:
                conn.execute("""
                    INSERT INTO tipos_documento_negocio (negocio_id, nombre, codigo, tipo_movimiento, consecutivo, numero_inicio, activo, predeterminado)
                    VALUES (%s, 'Ajuste de Inventario', 'AJUSTE_INV', 'ajuste', 0, 1, TRUE, TRUE)
                """, (negocio_id,))
                conn.commit()
                td = conn.execute("""
                    SELECT id, nombre, codigo, predeterminado
                    FROM tipos_documento_negocio
                    WHERE negocio_id = %s AND UPPER(codigo) = 'AJUSTE_INV'
                    LIMIT 1
                """, (negocio_id,)).fetchone()
            tipos_doc = [td]
            
        return render_template('inventario_fisico.html',
                               negocio_id=negocio_id,
                               negocio_nombre=contexto['negocio_nombre'],
                               volver_url=url_for('inventarios.admin_inventario', negocio_id=negocio_id),
                               volver_label='Inventario',
                               tipos_doc=[dict(t) for t in tipos_doc])
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ajuste-fisico/siguiente-documento')
def api_ajuste_siguiente_documento(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    tipo_doc_id = request.args.get('tipo_doc_id')
    if not tipo_doc_id:
        return jsonify({'ok': False, 'error': 'tipo_doc_id es requerido'}), 400
    conn = get_db_connection()
    try:
        td = conn.execute("""
            SELECT id, codigo, consecutivo, numero_inicio
            FROM tipos_documento_negocio
            WHERE negocio_id = %s AND id = %s
        """, (negocio_id, int(tipo_doc_id))).fetchone()
        
        if not td:
            return jsonify({'ok': False, 'error': 'Tipo de documento no encontrado'}), 404
            
        next_num = max((td['consecutivo'] or 0) + 1, (td['numero_inicio'] or 1))
        tipo_code = td['codigo'] or 'AJUSTE_INV'
        doc_num = f"{tipo_code}-{next_num}"
        
        return jsonify({'ok': True, 'documento_numero': doc_num, 'consecutivo': next_num})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ajuste-fisico/guardar-item', methods=['POST'])
def api_ajuste_guardar_item(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        
    data = request.get_json() or {}
    tipo_documento_id = data.get('tipo_documento_id')
    documento_numero = data.get('documento_numero')
    producto_id = data.get('producto_id')
    cantidad_fisica = data.get('cantidad_fisica')
    costo_unitario = data.get('costo_unitario')
    notas = data.get('notas') or ''
    
    if not tipo_documento_id or not documento_numero or not producto_id or cantidad_fisica is None or costo_unitario is None:
        return jsonify({'ok': False, 'error': 'Todos los campos son requeridos'}), 400
        
    conn = get_db_connection()
    try:
        # 1. Obtener producto y stock actual
        prod = conn.execute("SELECT nombre, categoria FROM productos WHERE id=%s AND negocio_id=%s", (producto_id, negocio_id)).fetchone()
        if not prod:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
            
        saldo = conn.execute("SELECT stock FROM saldos_inventario WHERE negocio_id=%s AND producto_id=%s AND bodega=1", (negocio_id, producto_id)).fetchone()
        stock_sistema = float(saldo['stock'] if saldo else 0.0)
        diff = float(cantidad_fisica) - stock_sistema
        
        if abs(diff) < 0.000001:
            return jsonify({'ok': True, 'mensaje': 'Sin diferencias, no requiere ajuste', 'consecutivo_actualizado': False})
            
        # Verificar si el periodo está cerrado
        _verificar_periodo_cerrado(conn, negocio_id, date.today())

        # 2. Verificar si existe el comprobante de esta sesión
        comp = conn.execute("""
            SELECT id, numero_comprobante FROM comprobantes_contables 
            WHERE negocio_id=%s AND numero_comprobante=%s
        """, (negocio_id, documento_numero)).fetchone()
        
        doc_num_final = documento_numero
        comp_id = None
        consecutivo_actualizado = False
        
        tipo_doc = conn.execute("SELECT id, codigo, consecutivo, numero_inicio FROM tipos_documento_negocio WHERE id=%s AND negocio_id=%s", (tipo_documento_id, negocio_id)).fetchone()
        if not tipo_doc:
            return jsonify({'ok': False, 'error': 'Tipo de documento no válido'}), 400
            
        tipo_code = tipo_doc['codigo'] or 'AJUSTE_INV'
        
        if comp:
            comp_id = comp['id']
        else:
            # Es el primer item: consumimos el consecutivo en la base de datos de manera atómica
            res_num, _ = obtener_siguiente_consecutivo(conn, negocio_id, tipo_documento_id)
            if not res_num:
                res_num = str(max((tipo_doc['consecutivo'] or 0) + 1, (tipo_doc['numero_inicio'] or 1)))
                conn.execute("UPDATE tipos_documento_negocio SET consecutivo = %s WHERE id = %s", (int(res_num), tipo_documento_id))
            
            doc_num_final = f"{tipo_code}-{int(res_num)}"
            
            desc_asiento = f"Ajuste físico de inventario - {doc_num_final}"
            comp_id = conn.execute("""
                INSERT INTO comprobantes_contables
                    (negocio_id, numero_comprobante, numero_documento, tipo, fecha, descripcion,
                     total_debitos, total_creditos, registrado_por, notas, origen_tipo, origen_id, tipo_documento_id)
                VALUES (%s, %s, %s, %s, CURRENT_DATE, %s, 0, 0, %s, 'Ajuste físico por ítem', 'ajuste_inventario', %s, %s)
                RETURNING id
            """, (negocio_id, doc_num_final, int(res_num), tipo_code, desc_asiento, session.get('usuario_id'), doc_num_final, tipo_documento_id)).fetchone()['id']
            consecutivo_actualizado = True
            
        # 3. Registrar el movimiento en movimientos_inventario (Kardex)
        tipo_mov = 'entrada' if diff > 0 else 'salida'
        _mov_directo(conn, negocio_id, producto_id, abs(diff), tipo_mov, 'ajuste',
                     registrado_por=session.get('usuario_id'),
                     valor_unitario=float(costo_unitario),
                     notas=notas,
                     bodega=1,
                     tipo_documento=tipo_code,
                     documento_numero=doc_num_final,
                     tipo_documento_id=tipo_documento_id)
                     
        # 4. Recostear el producto
        _recostear_producto(conn, negocio_id, producto_id)
        
        # 5. Integración contable individualizada por producto
        warnings = []
        if prod['categoria']:
            gi = conn.execute("""
                SELECT cuenta_inve_id, cuenta_ajuste_favor_id, cuenta_ajuste_contra_id
                FROM grupos_inventario
                WHERE negocio_id = %s AND nombre = %s
            """, (negocio_id, prod['categoria'])).fetchone()
            
            if gi:
                cuenta_inve = gi['cuenta_inve_id']
                cuenta_favor = gi['cuenta_ajuste_favor_id']
                cuenta_contra = gi['cuenta_ajuste_contra_id']
                
                monto_ajuste = abs(diff) * float(costo_unitario)
                
                db_cuenta_id = None
                cr_cuenta_id = None
                
                if diff > 0: # Sobrante (Ingreso / Ajuste en favor)
                    if cuenta_inve and cuenta_favor:
                        db_cuenta_id = cuenta_inve
                        cr_cuenta_id = cuenta_favor
                        concepto = f"Ajuste Físico (+): Insumo {prod['nombre']}"
                    else:
                        warnings.append("Falta configurar la cuenta de Inventario o de Ajuste a Favor para la categoría.")
                else: # Faltante (Gasto / Ajuste en contra)
                    if cuenta_contra and cuenta_inve:
                        db_cuenta_id = cuenta_contra
                        cr_cuenta_id = cuenta_inve
                        concepto = f"Ajuste Físico (-): Insumo {prod['nombre']}"
                    else:
                        warnings.append("Falta configurar la cuenta de Inventario o de Ajuste en Contra para la categoría.")
                        
                if db_cuenta_id and cr_cuenta_id:
                    # Resolver códigos de cuenta
                    db_cod = conn.execute("SELECT codigo FROM cuentas_puc WHERE id=%s", (db_cuenta_id,)).fetchone()['codigo']
                    cr_cod = conn.execute("SELECT codigo FROM cuentas_puc WHERE id=%s", (cr_cuenta_id,)).fetchone()['codigo']
                    
                    # Insertar Débito
                    conn.execute("""
                        INSERT INTO movimientos_contables (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, producto_id)
                        VALUES (%s, %s, %s, %s, %s, 'D', %s, %s, %s)
                    """, (negocio_id, comp_id, db_cuenta_id, db_cod, concepto, monto_ajuste, session.get('usuario_id'), producto_id))
                    
                    # Insertar Crédito
                    conn.execute("""
                        INSERT INTO movimientos_contables (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, producto_id)
                        VALUES (%s, %s, %s, %s, %s, 'C', %s, %s, %s)
                    """, (negocio_id, comp_id, cr_cuenta_id, cr_cod, concepto, monto_ajuste, session.get('usuario_id'), producto_id))
                    
                    # Recalcular totales del comprobante
                    totals = conn.execute("""
                        SELECT SUM(CASE WHEN tipo='D' THEN monto ELSE 0 END) AS deb,
                               SUM(CASE WHEN tipo='C' THEN monto ELSE 0 END) AS cred
                        FROM movimientos_contables WHERE comprobante_id = %s
                    """, (comp_id,)).fetchone()
                    
                    conn.execute("""
                        UPDATE comprobantes_contables
                        SET total_debitos = %s, total_creditos = %s
                        WHERE id = %s
                    """, (float(totals['deb'] or 0.0), float(totals['cred'] or 0.0), comp_id))
            else:
                warnings.append("La categoría del producto no está configurada en Grupos de Inventario.")
        else:
            warnings.append("El producto no pertenece a ninguna categoría.")
            
        conn.commit()
        return jsonify({
            'ok': True,
            'mensaje': 'Ajuste registrado y contabilizado con éxito',
            'documento_numero': doc_num_final,
            'consecutivo_actualizado': consecutivo_actualizado,
            'warnings': warnings
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ajuste-fisico/documento/<documento_numero>/items')
def api_ajuste_documento_items(negocio_id, documento_numero):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT m.id, m.producto_id, m.nombre_producto, m.cantidad, m.tipo, m.costo_und, m.valor_total,
                   m.stock_anterior, m.stock_nuevo, m.created_at, p.categoria
            FROM movimientos_inventario m
            JOIN productos p ON p.id = m.producto_id
            WHERE m.negocio_id = %s AND m.documento_numero = %s AND m.motivo = 'ajuste'
            ORDER BY m.id DESC
        """, (negocio_id, documento_numero)).fetchall()
        return jsonify({'ok': True, 'items': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ajuste-fisico/historial')
def api_ajuste_historial(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        # Agrupar documentos de ajuste físico por número
        rows = conn.execute("""
            SELECT m.documento_numero, MAX(m.created_at) AS fecha, c.id AS comprobante_id,
                   COALESCE(c.total_debitos, 0) AS total_debitos, COUNT(DISTINCT m.producto_id) AS total_items
            FROM movimientos_inventario m
            LEFT JOIN comprobantes_contables c ON c.numero_comprobante = m.documento_numero AND c.negocio_id = m.negocio_id
            WHERE m.negocio_id = %s AND m.motivo = 'ajuste'
            GROUP BY m.documento_numero, c.id, c.total_debitos
            ORDER BY fecha DESC
        """, (negocio_id,)).fetchall()
        return jsonify({'ok': True, 'historial': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ajuste-fisico/documento/<documento_numero>/detalles')
def api_ajuste_documento_detalles(negocio_id, documento_numero):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        # Obtener los items del Kardex
        items = conn.execute("""
            SELECT m.producto_id, m.nombre_producto, m.cantidad, m.tipo, m.costo_und, m.valor_total,
                   m.stock_anterior, m.stock_nuevo, p.categoria
            FROM movimientos_inventario m
            JOIN productos p ON p.id = m.producto_id
            WHERE m.negocio_id = %s AND m.documento_numero = %s AND m.motivo = 'ajuste'
            ORDER BY m.id
        """, (negocio_id, documento_numero)).fetchall()
        
        # Obtener el asiento contable individualizado
        asiento = conn.execute("""
            SELECT mc.cuenta, c.nombre AS cuenta_nombre, mc.concepto, mc.tipo, mc.monto, p.nombre AS producto_nombre
            FROM movimientos_contables mc
            JOIN cuentas_puc c ON c.id = mc.cuenta_id
            LEFT JOIN productos p ON p.id = mc.producto_id
            JOIN comprobantes_contables cc ON cc.id = mc.comprobante_id
            WHERE mc.negocio_id = %s AND cc.numero_comprobante = %s
            ORDER BY mc.id
        """, (negocio_id, documento_numero)).fetchall()
        
        return jsonify({
            'ok': True,
            'items': [dict(i) for i in items],
            'asiento': [dict(a) for a in asiento]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/modificar-documento', methods=['POST'])
def api_mantenimiento_modificar_documento(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    data = request.get_json() or {}
    tipo_documento = data.get('tipo_documento')
    documento_numero = data.get('documento_numero')
    nueva_fecha = data.get('nueva_fecha')
    nuevo_tercero_id = data.get('nuevo_tercero_id')
    
    if not tipo_documento or not documento_numero:
        return jsonify({'ok': False, 'error': 'tipo_documento y documento_numero son requeridos'}), 400
        
    if not nueva_fecha and nuevo_tercero_id is None:
        return jsonify({'ok': False, 'error': 'Se requiere al menos un atributo a modificar (nueva_fecha o nuevo_tercero_id)'}), 400
        
    conn = get_db_connection()
    try:
        # 1. Resolver tercero si nuevo_tercero_id es provisto
        tercero_nombre = None
        if nuevo_tercero_id is not None:
            tercero = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (int(nuevo_tercero_id),)).fetchone()
            if not tercero:
                return jsonify({'ok': False, 'error': f'Tercero con ID {nuevo_tercero_id} no encontrado'}), 404
            tercero_nombre = tercero['nombre']
            
        # 2. Buscar si existe pedido relacionado
        pedido_row = None
        try:
            pedido_id = int(documento_numero)
            pedido_row = conn.execute("SELECT id, tipo_documento_id FROM pedidos WHERE id = %s AND negocio_id = %s", (pedido_id, negocio_id)).fetchone()
        except ValueError:
            pass
            
        if not pedido_row:
            pedido_row = conn.execute("SELECT id, tipo_documento_id FROM pedidos WHERE UPPER(numero_documento) = UPPER(%s) AND negocio_id = %s", (documento_numero, negocio_id)).fetchone()

        # 3. Resolver tipo_documento_id de forma robusta
        tipo_documento_id = None
        try:
            tipo_documento_id = int(tipo_documento)
        except ValueError:
            row_td = conn.execute("""
                SELECT id FROM tipos_documento_negocio 
                WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))
            """, (negocio_id, tipo_documento, tipo_documento)).fetchone()
            if row_td:
                tipo_documento_id = row_td['id']

        if pedido_row and not tipo_documento_id:
            tipo_documento_id = pedido_row['tipo_documento_id']
            
        # 4. Determinar cláusula WHERE para movimientos_inventario
        if tipo_documento_id:
            where_inv = "negocio_id = %s AND tipo_documento_id = %s AND documento_numero = %s"
            params_inv = [negocio_id, tipo_documento_id, documento_numero]
        else:
            # Fallback legacy
            if pedido_row:
                where_inv = """
                    negocio_id = %s AND (
                        (referencia_tipo IN ('pedido', 'pedido_tienda', 'pedido_restaurante') AND referencia_id = %s)
                        OR (LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s))
                    )
                """
                params_inv = [negocio_id, pedido_row['id'], tipo_documento, documento_numero]
            else:
                where_inv = "negocio_id = %s AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s)"
                params_inv = [negocio_id, tipo_documento, documento_numero]
            
        # 5. Obtener productos afectados ANTES de cualquier modificación para poder recostearlos
        productos_afectados = [r['producto_id'] for r in conn.execute(f"SELECT DISTINCT producto_id FROM movimientos_inventario WHERE {where_inv}", tuple(params_inv)).fetchall()]
        
        # 6. Aplicar modificaciones en movimientos_inventario (Kardex)
        if nueva_fecha:
            conn.execute(f"""
                UPDATE movimientos_inventario
                SET documento_fecha = %s,
                    created_at = %s::date + (created_at::time)
                WHERE {where_inv}
            """, [nueva_fecha, nueva_fecha] + params_inv)
            
        if nuevo_tercero_id is not None:
            conn.execute(f"""
                UPDATE movimientos_inventario
                SET proveedor_id = %s,
                    proveedor_nombre = %s
                WHERE {where_inv}
            """, [int(nuevo_tercero_id), tercero_nombre] + params_inv)
            
        # 7. Aplicar modificaciones en comprobantes_contables
        if tipo_documento_id:
            where_comp = "negocio_id = %s AND tipo_documento_id = %s AND numero_comprobante = %s"
            params_comp = [negocio_id, tipo_documento_id, documento_numero]
        else:
            # Fallback legacy
            origen_id_str = f"{tipo_documento}:{documento_numero}"
            pedido_id_str = str(pedido_row['id']) if pedido_row else None
            where_comp = """
                negocio_id = %s AND (
                    (origen_tipo = 'pedido' AND origen_id = %s)
                    OR (origen_tipo IS NOT NULL AND LOWER(origen_id) = LOWER(%s))
                    OR (numero_comprobante ILIKE %s)
                )
            """
            params_comp = [negocio_id, pedido_id_str, origen_id_str, f'%{documento_numero}%']
        
        if nueva_fecha:
            conn.execute(f"""
                UPDATE comprobantes_contables
                SET fecha = %s,
                    created_at = %s::date + (created_at::time)
                WHERE {where_comp}
            """, [nueva_fecha, nueva_fecha] + params_comp)
            
        # 8. Aplicar modificaciones en pedidos (ventas)
        if pedido_row:
            if nueva_fecha:
                conn.execute("""
                    UPDATE pedidos
                    SET fecha = %s,
                        created_at = %s::date + (created_at::time)
                    WHERE id = %s AND negocio_id = %s
                """, (nueva_fecha, nueva_fecha, pedido_row['id'], negocio_id))
            if nuevo_tercero_id is not None:
                update_fields = ["id_tercero = %s"]
                update_params = [int(nuevo_tercero_id)]
                
                # Obtener columnas de tabla pedidos de manera segura
                ped_cols = [c['column_name'] for c in conn.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'pedidos'
                """).fetchall()]
                
                if 'cliente_id' in ped_cols:
                    update_fields.append("cliente_id = %s")
                    update_params.append(int(nuevo_tercero_id))
                if 'nombre_cliente' in ped_cols:
                    update_fields.append("nombre_cliente = %s")
                    update_params.append(tercero_nombre)
                    
                query_ped = f"UPDATE pedidos SET {', '.join(update_fields)} WHERE id = %s AND negocio_id = %s"
                conn.execute(query_ped, tuple(update_params + [pedido_row['id'], negocio_id]))
                
        # 9. Aplicar modificaciones en saldo_por_documentos
        if tipo_documento_id:
            where_saldo = "negocio_id = %s AND tipo_documento_id = %s AND numero_documento = %s"
            params_saldo = [negocio_id, tipo_documento_id, documento_numero]
        else:
            # Fallback legacy
            where_saldo = """
                negocio_id = %s AND (
                    (tipo_documento = %s AND numero_documento = %s)
                    OR (tipo_documento_id IS NOT NULL AND numero_documento = %s)
                )
            """
            params_saldo = [negocio_id, tipo_documento, documento_numero, documento_numero]
        
        if nueva_fecha:
            conn.execute(f"""
                UPDATE saldo_por_documentos
                SET fecha_hora = %s::date + (fecha_hora::time),
                    created_at = %s::date + (created_at::time)
                WHERE {where_saldo}
            """, [nueva_fecha, nueva_fecha] + params_saldo)
            
        if nuevo_tercero_id is not None:
            conn.execute(f"""
                UPDATE saldo_por_documentos
                SET tercero_id = %s
                WHERE {where_saldo}
            """, [int(nuevo_tercero_id)] + params_saldo)
            
        # 10. Recosteo retroactivo de todos los productos afectados
        for p_id in productos_afectados:
            _recostear_producto(conn, negocio_id, p_id)
            
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Documento modificado y propagado con éxito en todo el sistema.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()

@bp.route('/api/inventario/<int:negocio_id>/reporte-ventas-costos')
def api_reporte_ventas_costos(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    if not desde or not hasta:
        return jsonify({'ok': False, 'error': 'Debe especificar las fechas desde y hasta'}), 400
        
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT 
                pi.producto_id,
                p.nombre AS nombre_producto,
                SUM(pi.cantidad) AS cantidad_vendida,
                SUM(pi.cantidad * pi.precio_unitario) AS total_ventas_pesos,
                SUM(pi.cantidad * pi.costo_unitario) AS total_costo_pesos
            FROM pedido_items pi
            JOIN pedidos ped ON ped.id = pi.pedido_id
            JOIN productos p ON p.id = pi.producto_id
            WHERE ped.negocio_id = %s 
              AND (ped.estado IS NULL OR ped.estado != 'anulado')
              AND COALESCE(ped.fecha, ped.created_at::date) >= %s::date 
              AND COALESCE(ped.fecha, ped.created_at::date) <= %s::date
            GROUP BY pi.producto_id, p.nombre
            ORDER BY total_ventas_pesos DESC
        """, (negocio_id, desde, hasta)).fetchall()
        
        datos = []
        for r in rows:
            cant = float(r['cantidad_vendida'])
            ventas_tot = float(r['total_ventas_pesos'])
            costos_tot = float(r['total_costo_pesos'])
            
            px_prom = ventas_tot / cant if cant > 0 else 0.0
            cx_prom = costos_tot / cant if cant > 0 else 0.0
            
            margen_unitario = px_prom - cx_prom
            margen_total = ventas_tot - costos_tot
            margen_porcentual = (margen_total / ventas_tot * 100.0) if ventas_tot > 0 else 0.0
            
            datos.append({
                'producto_id': r['producto_id'],
                'nombre_producto': r['nombre_producto'],
                'cantidad': cant,
                'precio_unitario': px_prom,
                'costo_unitario': cx_prom,
                'total_venta': ventas_tot,
                'total_costo': costos_tot,
                'margen_unitario': margen_unitario,
                'margen_total': margen_total,
                'margen_porcentual': margen_porcentual
            })
            
        return jsonify({'ok': True, 'reporte': datos})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/mantenimiento/conciliar-cuentas-14')
def api_conciliar_cuentas_14(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    conn = get_db_connection()
    try:
        # 1. Total Inventario en Contabilidad (Cuentas 14)
        c_bal_row = conn.execute("""
            SELECT SUM(CASE WHEN mc.tipo = 'debito' THEN mc.monto ELSE -mc.monto END) AS balance
            FROM movimientos_contables mc
            JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
            WHERE mc.negocio_id = %s AND cp.codigo LIKE '14%%'
        """, (negocio_id,)).fetchone()
        total_contab = float(c_bal_row['balance'] or 0)

        # 2. Total Inventario en Kardex (Saldos actuales)
        k_bal_row = conn.execute("""
            SELECT SUM(valor_existencia) AS total
            FROM saldos_inventario
            WHERE negocio_id = %s
        """, (negocio_id,)).fetchone()
        total_kardex = float(k_bal_row['total'] or 0)

        # 3. Movimientos detallados agrupados por documento en Kardex
        kardex_rows = conn.execute("""
            SELECT m.documento_numero, m.tipo_documento_id, tdn.nombre AS tipo_documento_nombre,
                   SUM(CASE WHEN m.tipo = 'entrada' THEN COALESCE(m.valor_total, m.cantidad * m.costo_und, 0) 
                            ELSE -COALESCE(m.valor_total, m.cantidad * m.costo_und, 0) END) AS total_kardex,
                   MAX(m.created_at) as fecha
            FROM movimientos_inventario m
            LEFT JOIN tipos_documento_negocio tdn ON tdn.id = m.tipo_documento_id
            WHERE m.negocio_id = %s AND m.documento_numero IS NOT NULL
            GROUP BY m.documento_numero, m.tipo_documento_id, tdn.nombre
        """, (negocio_id,)).fetchall()

        # 4. Movimientos detallados agrupados por comprobante en Contabilidad (Cuentas 14)
        contab_rows = conn.execute("""
            SELECT cc.numero_comprobante, cc.tipo_documento_id, tdn.nombre AS tipo_documento_nombre,
                   SUM(CASE WHEN mc.tipo = 'debito' THEN mc.monto ELSE -mc.monto END) AS total_contab,
                   MAX(cc.fecha) as fecha
            FROM movimientos_contables mc
            JOIN comprobantes_contables cc ON cc.id = mc.comprobante_id
            JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
            LEFT JOIN tipos_documento_negocio tdn ON tdn.id = cc.tipo_documento_id
            WHERE mc.negocio_id = %s AND cp.codigo LIKE '14%%'
            GROUP BY cc.numero_comprobante, cc.tipo_documento_id, tdn.nombre
        """, (negocio_id,)).fetchall()

        # Agrupar mapas usando números normalizados
        kardex_map = {}
        for r in kardex_rows:
            num_orig = r['documento_numero']
            num_norm = normalizar_numero(num_orig)
            if num_norm not in kardex_map:
                kardex_map[num_norm] = []
            kardex_map[num_norm].append({
                'documento_numero': num_orig,
                'tipo_documento_id': r['tipo_documento_id'],
                'tipo_documento_nombre': r['tipo_documento_nombre'],
                'total_kardex': float(r['total_kardex']),
                'fecha': r['fecha']
            })

        contab_map = {}
        for r in contab_rows:
            num_orig = r['numero_comprobante']
            num_norm = normalizar_numero(num_orig)
            if num_norm not in contab_map:
                contab_map[num_norm] = []
            contab_map[num_norm].append({
                'numero_comprobante': num_orig,
                'tipo_documento_id': r['tipo_documento_id'],
                'tipo_documento_nombre': r['tipo_documento_nombre'],
                'total_contab': float(r['total_contab']),
                'fecha': r['fecha']
            })

        discrepancias_a = []  # Kardex sin Contabilidad
        discrepancias_b = []  # Contabilidad sin Kardex
        discrepancias_c = []  # Diferencias de monto

        # Comparar Kardex contra Contabilidad
        for norm_num, k_list in kardex_map.items():
            total_k = sum(item['total_kardex'] for item in k_list)
            if abs(total_k) < 0.01:
                continue
            if norm_num not in contab_map:
                for item in k_list:
                    discrepancias_a.append({
                        'documento': item['documento_numero'],
                        'tipo_documento': item['tipo_documento_nombre'] or 'Desconocido',
                        'valor_kardex': item['total_kardex'],
                        'fecha': item['fecha'].isoformat() if item['fecha'] else None
                    })
            else:
                total_c = sum(item['total_contab'] for item in contab_map[norm_num])
                if abs(total_k - total_c) > 0.01:
                    discrepancias_c.append({
                        'documento': k_list[0]['documento_numero'],
                        'tipo_documento': k_list[0]['tipo_documento_nombre'] or 'Desconocido',
                        'valor_kardex': total_k,
                        'valor_contabilidad': total_c,
                        'diferencia': total_k - total_c,
                        'fecha': k_list[0]['fecha'].isoformat() if k_list[0]['fecha'] else None
                    })

        # Comparar Contabilidad contra Kardex
        for norm_num, c_list in contab_map.items():
            total_c = sum(item['total_contab'] for item in c_list)
            if abs(total_c) < 0.01:
                continue
            if norm_num not in kardex_map:
                for item in c_list:
                    discrepancias_b.append({
                        'documento': item['numero_comprobante'],
                        'tipo_documento': item['tipo_documento_nombre'] or 'Desconocido',
                        'valor_contabilidad': item['total_contab'],
                        'fecha': item['fecha'].isoformat() if item['fecha'] else None
                    })

        # Sort helper key
        def get_fecha(x):
            return x['fecha'] or ''

        reporte = {
            'ok': True,
            'totales': {
                'total_kardex': total_kardex,
                'total_contabilidad': total_contab,
                'diferencia': total_kardex - total_contab
            },
            'kardex_sin_contabilidad': sorted(discrepancias_a, key=get_fecha, reverse=True),
            'contabilidad_sin_kardex': sorted(discrepancias_b, key=get_fecha, reverse=True),
            'diferencias_valor': sorted(discrepancias_c, key=get_fecha, reverse=True)
        }

        # Guardar en archivo local del servidor para soporte
        import json
        import os
        report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reconciliation_report.json')
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(reporte, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return jsonify(reporte)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
