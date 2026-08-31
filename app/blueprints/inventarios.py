from flask import Blueprint, Response, jsonify, redirect, render_template, request, session, url_for
from ..db import get_db_connection
from decimal import Decimal
from datetime import date, timedelta

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

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
            id             SERIAL PRIMARY KEY,
            producto_id    INTEGER NOT NULL REFERENCES productos(id),
            componente_id  INTEGER NOT NULL REFERENCES productos(id),
            cantidad       NUMERIC(12,4) NOT NULL DEFAULT 1,
            creado_en      TIMESTAMP DEFAULT NOW(),
            actualizado_en TIMESTAMP DEFAULT NOW(),
            tercero_id     INTEGER REFERENCES terceros(id),
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
        """CREATE TABLE IF NOT EXISTS precios (
            id            SERIAL PRIMARY KEY,
            negocio_id    INTEGER NOT NULL,
            producto_id   INTEGER NOT NULL REFERENCES productos(id),
            precio_venta  DECIMAL(12,2) DEFAULT 0,
            costo         DECIMAL(12,2) DEFAULT 0,
            iva_pct       NUMERIC(5,2) DEFAULT 0,
            categoria     VARCHAR(100),
            created_at    TIMESTAMP DEFAULT NOW(),
            updated_at    TIMESTAMP DEFAULT NOW(),
            UNIQUE(negocio_id, producto_id)
        )""",
        """CREATE TABLE IF NOT EXISTS inventario_distribuido_estado (
            id              SERIAL PRIMARY KEY,
            negocio_id      INTEGER NOT NULL,
            producto_id     INTEGER NOT NULL REFERENCES productos(id),
            usuario_id      INTEGER,
            estado          VARCHAR(20) DEFAULT 'pendiente',
            fecha_ultimo_conteo TIMESTAMP,
            conteos_total   INTEGER DEFAULT 0,
            prioridad_score NUMERIC(14,4) DEFAULT 0,
            quién_contó     VARCHAR(255),
            ciclo_inicio    TIMESTAMP,
            ciclo_fin       TIMESTAMP,
            UNIQUE(negocio_id, producto_id, ciclo_inicio)
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
        "ALTER TABLE tarjeta_estandar ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE tarjeta_estandar ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE tarjeta_estandar ADD COLUMN IF NOT EXISTS tercero_id INTEGER REFERENCES terceros(id)",
        "CREATE INDEX IF NOT EXISTS idx_saldos_negocio_producto ON saldos_inventario(negocio_id, producto_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_presentaciones_unique ON presentaciones(LOWER(nombre), equivalencia)",
        "CREATE INDEX IF NOT EXISTS idx_precios_negocio ON precios(negocio_id)",
        "CREATE INDEX IF NOT EXISTS idx_precios_producto ON precios(producto_id)",
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
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE movimientos_inventario ALTER COLUMN valor_unitario TYPE NUMERIC(16,6)",
        "ALTER TABLE movimientos_inventario ALTER COLUMN costo_und TYPE NUMERIC(16,6)",
        "ALTER TABLE saldos_inventario ALTER COLUMN costo_und TYPE NUMERIC(16,6)",
        "ALTER TABLE productos ALTER COLUMN costo TYPE NUMERIC(16,6)",
        "CREATE INDEX IF NOT EXISTS idx_inv_dist_negocio ON inventario_distribuido_estado(negocio_id)",
        "CREATE INDEX IF NOT EXISTS idx_inv_dist_producto ON inventario_distribuido_estado(producto_id)",
        "CREATE INDEX IF NOT EXISTS idx_inv_dist_estado ON inventario_distribuido_estado(estado)",
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


def _sync_precio(conn, negocio_id, producto_id):
    """Sincroniza precio/costo/iva/categoría de productos → precios (solo si precio > 0)."""
    try:
        row = conn.execute(
            "SELECT precio, costo, iva_pct, categoria FROM productos WHERE id = %s",
            (producto_id,)
        ).fetchone()
        if not row:
            return
        precio_venta = float(row['precio'] or 0)
        if precio_venta <= 0:
            # Producto no se vende — eliminar de precios si existe
            conn.execute("DELETE FROM precios WHERE negocio_id = %s AND producto_id = %s",
                         (negocio_id, producto_id))
            return
        conn.execute("""
            INSERT INTO precios (negocio_id, producto_id, precio_venta, costo, iva_pct, categoria)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (negocio_id, producto_id) DO UPDATE SET
                precio_venta = EXCLUDED.precio_venta,
                costo = EXCLUDED.costo,
                iva_pct = EXCLUDED.iva_pct,
                categoria = EXCLUDED.categoria,
                updated_at = NOW()
        """, (negocio_id, producto_id, precio_venta, row['costo'], row['iva_pct'], row['categoria']))
    except Exception:
        pass


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
                 metodo_pago=None, tipo_documento_id=None, valor_total=None):
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
        if valor_total is not None and valor_total > 0:
            vu = Decimal(str(valor_total)) / cantidad if cantidad > 0 else vu
        costo_nuevo   = (val_exi_ant + cantidad * vu) / stock_nuevo if stock_nuevo > 0 else vu
        val_exi_nuevo = stock_nuevo * costo_nuevo if stock_nuevo > 0 else Decimal('0')
    else:
        costo_nuevo   = costo_ant if stock_nuevo > 0 else Decimal('0')
        val_exi_nuevo = stock_nuevo * costo_nuevo if stock_nuevo > 0 else Decimal('0')

    # Guardar costo de valoración del movimiento (evitando costo cero cuando cae a stock 0)
    costo_registro = costo_nuevo if (tipo == 'entrada' or stock_nuevo > 0) else costo_ant

    nombre_prod = conn.execute("SELECT nombre FROM productos WHERE id=%s", (producto_id,)).fetchone()

    # Número de documento puro (sin el prefijo del código del tipo).
    # Estándar: tipo_documento_id + numero_documento (alfanumérico) identifica el documento en
    # movimientos_inventario y movimientos_contables. Nada de concatenaciones.
    num_puro = documento_numero
    if documento_numero:
        cod_row = None
        if tipo_documento_id:
            cod_row = conn.execute("SELECT codigo FROM tipos_documento_negocio WHERE id=%s", (tipo_documento_id,)).fetchone()
        cod = (cod_row['codigo'] if cod_row and cod_row['codigo'] else tipo_documento) or ''
        s = str(documento_numero).strip()
        if cod and s.upper().startswith(str(cod).strip().upper() + '-'):
            num_puro = s[len(str(cod).strip()) + 1:].strip()
        elif tipo_documento_id and s.upper().startswith('AJUSTE_INV-'):
            num_puro = s[len('AJUSTE_INV'):].lstrip('-').strip()

    conn.execute("""
        INSERT INTO movimientos_inventario
            (negocio_id, producto_id, nombre_producto, tipo, motivo,
             cantidad, stock_anterior, stock_nuevo, registrado_por, notas,
             valor_unitario, valor_total, costo_und, referencia_id, referencia_tipo,
             tipo_documento, documento_numero, numero_documento, documento_fecha, proveedor_id,
             proveedor_nombre, iva_total, documento_total, iva_pct, iva_valor,
             producto_padre_id, presentacion_id, metodo_pago, tipo_documento_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        negocio_id, producto_id,
        nombre_prod['nombre'] if nombre_prod else '',
        tipo, motivo,
        float(cantidad), float(stock_ant), float(stock_nuevo),
        registrado_por, notas,
        float(valor_unitario) if valor_unitario else None,
        float(valor_total) if valor_total is not None else (float(cantidad * Decimal(str(valor_unitario))) if valor_unitario else None),
        float(costo_registro),
        referencia_id, referencia_tipo,
        tipo_documento, num_puro, num_puro, documento_fecha, proveedor_id,
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
    _sync_precio(conn, negocio_id, producto_id)




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
                     excluir_componentes_ids=None, valor_total=None):
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
                     tipo_documento_id=tipo_documento_id, valor_total=valor_total)


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

    fecha_recibida = data.get('documento_fecha') or data.get('fecha_documento')
    documento_fecha = _fecha_o_none(fecha_recibida)
    if fecha_recibida and not documento_fecha:
        return {'ok': False, 'error': 'La fecha del documento no es válida.'}, 400
    if documento_fecha and documento_fecha > date.today():
        return {'ok': False, 'error': 'La fecha del documento no puede ser futura.'}, 400
    if documento_fecha:
        try:
            _verificar_periodo_cerrado(conn, negocio_id, documento_fecha)
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}, 400
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
                
                # Delete directly from movimientos_contables using flat metadata
                conn.execute("""
                    DELETE FROM movimientos_contables
                    WHERE negocio_id = %s AND (
                        (origen_tipo IS NOT NULL AND LOWER(origen_id) IN %s)
                        OR (numero_documento IN %s)
                        OR (tipo_documento_id = %s AND numero_documento IN %s)
                    )
                """, (negocio_id, tuple(o.lower() for o in origen_ids), tuple(num_variants), tipo_doc_id, tuple(num_variants)))
                
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
        vt = _dec(ln.get('valor_total')) if ln.get('valor_total') is not None else None
        iva_pct = _dec(ln.get('iva_pct') or '0')

        if vt is not None and vt > 0:
            line_subtotal = vt
        else:
            line_subtotal = cant * vu
        line_iva_val = line_subtotal * (iva_pct / Decimal('100'))

        subtotal_compra += line_subtotal
        iva_total += line_iva_val

        lineas_procesadas.append({
            'producto_id': prod_id,
            'cantidad': cant,
            'valor_unitario': vu,
            'valor_total': line_subtotal,
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
            tipo_documento_id=tipo_doc_id,
            valor_total=ln['valor_total']
        )

        # Feed/update quote (cotizacion) from this entry if it's a purchase and has a price
        if motivo == 'compra' and proveedor_id and ln['valor_unitario'] and float(ln['valor_unitario']) > 0:
            from datetime import timedelta
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
                WHERE tercero_id = %s AND item_id = %s AND presentacion_id = %s
                LIMIT 1
            """, (proveedor_id, ln['producto_id'], pres_id)).fetchone()
            
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

    # Recostear solo si es modificacion de documento existente
    # (se elimino y re-registro, cambiando los movimientos)
    # Compra nueva NO necesita recosteo — solo actualiza saldos_inventario
    if es_modificacion:
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
        _sync_precio(conn, int(negocio_id), row[0])
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
        solo_venta = request.args.get('solo_venta') == '1'
        extra_where = " AND p.disponible = TRUE AND p.precio > 0" if solo_venta else ""

        rows = conn.execute(f"""
            SELECT p.id, p.nombre, p.categoria, p.precio,
                   COALESCE(s.costo_und, p.costo) AS costo,
                   p.codigo_barra, p.iva_pct, p.disponible, p.orden,
                   COALESCE(s.stock, 0) AS stock
            FROM productos p
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id
                AND s.negocio_id = p.negocio_id AND s.bodega = 1
            WHERE p.negocio_id = %s{extra_where}
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
        usuario_tercero_id = session.get('chat_tercero_id') or session['usuario_id']
        linea_ids = []
        for ln in lineas:
            cid = int(ln['componente_id'])
            linea_ids.append(cid)
            conn.execute("""
                INSERT INTO tarjeta_estandar (producto_id, componente_id, cantidad, tercero_id, creado_en, actualizado_en)
                VALUES (%s,%s,%s,%s, NOW(), NOW())
                ON CONFLICT (producto_id, componente_id) DO UPDATE
                    SET cantidad = EXCLUDED.cantidad,
                        actualizado_en = NOW(),
                        tercero_id = EXCLUDED.tercero_id
            """, (producto_id, cid, float(ln['cantidad']), usuario_tercero_id))
        if linea_ids:
            conn.execute("""
                DELETE FROM tarjeta_estandar
                WHERE producto_id = %s AND componente_id NOT IN %s
            """, (producto_id, tuple(linea_ids)))
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


@bp.route('/api/inventario/producto/<int:producto_id>/tarjeta/update-proportions', methods=['POST'])
def api_inventario_tarjeta_update_proportions(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    lineas = data.get('componentes', [])
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
        usuario_tercero_id = session.get('chat_tercero_id') or session['usuario_id']
        linea_ids = []
        for ln in lineas:
            cid = int(ln['componente_id'])
            linea_ids.append(cid)
            conn.execute("""
                INSERT INTO tarjeta_estandar (producto_id, componente_id, cantidad, tercero_id, creado_en, actualizado_en)
                VALUES (%s,%s,%s,%s, NOW(), NOW())
                ON CONFLICT (producto_id, componente_id) DO UPDATE
                    SET cantidad = EXCLUDED.cantidad,
                        actualizado_en = NOW(),
                        tercero_id = EXCLUDED.tercero_id
            """, (producto_id, cid, float(ln['cantidad_unidad']), usuario_tercero_id))
        if linea_ids:
            conn.execute("""
                DELETE FROM tarjeta_estandar
                WHERE producto_id = %s AND componente_id NOT IN %s
            """, (producto_id, tuple(linea_ids)))
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
                   m.documento_numero, m.documento_fecha, m.tipo_documento_id, m.proveedor_id,
                   COALESCE(t.nombre, m.proveedor_nombre) AS proveedor_nombre, m.iva_total, m.documento_total,
                   COALESCE(TO_CHAR(m.documento_fecha, 'DD/MM/YY') || ' ' || TO_CHAR(m.created_at, 'HH24:MI'), TO_CHAR(m.created_at, 'DD/MM/YY HH24:MI')) AS fecha,
                   TO_CHAR(m.created_at, 'HH24:MI') AS hora_documento,
                   TO_CHAR(m.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at_iso,
                   TO_CHAR(m.documento_fecha, 'YYYY-MM-DD') AS documento_fecha_iso,
                   p_padre.nombre AS producto_padre_nombre
            FROM movimientos_inventario m
            LEFT JOIN terceros t ON t.id = m.proveedor_id
            LEFT JOIN productos p_padre ON p_padre.id = m.producto_padre_id
            WHERE m.producto_id = %s
            ORDER BY COALESCE(m.documento_fecha, m.created_at::date) DESC, m.created_at DESC, m.id DESC LIMIT 300
        """, (producto_id,)).fetchall()
        prod_info = conn.execute("""
            SELECT p.costo, COALESCE(s.stock, 0.0) AS stock,
                   COALESCE(s.valor_existencia, 0.0) AS valor_existencia
            FROM productos p
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.bodega = 1
            WHERE p.id = %s
        """, (producto_id,)).fetchone()
        totales = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN cantidad ELSE 0 END), 0) AS entradas,
                COALESCE(SUM(CASE WHEN tipo = 'salida' THEN cantidad ELSE 0 END), 0) AS salidas
            FROM movimientos_inventario
            WHERE negocio_id = %s AND producto_id = %s
        """, (negocio_id, producto_id)).fetchone()
        
        costo_actual = float(prod_info['costo']) if prod_info and prod_info['costo'] is not None else 0.0
        stock_actual = float(prod_info['stock']) if prod_info and prod_info['stock'] is not None else 0.0
        valor_existencia = float(prod_info['valor_existencia']) if prod_info else 0.0
        auditoria = _auditar_producto_recosteo(conn, negocio_id, producto_id)

        return jsonify({
            'ok': True, 
            'movimientos': [dict(r) for r in rows],
            'costo_actual': costo_actual,
            'stock_actual': stock_actual,
            'valor_existencia': valor_existencia,
            'totales': {
                'entradas': float(totales['entradas'] or 0),
                'salidas': float(totales['salidas'] or 0)
            },
            'auditoria': auditoria
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Debug: Analisis Kardex vs Contabilidad por factura ────────────────────────
@bp.route('/api/debug/analisis-factura/<int:negocio_id>/<numero_doc>')
def api_debug_analisis_factura(negocio_id, numero_doc):
    """Devuelve JSON con los registros de Kardex y Contabilidad para una factura."""
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        kardex = conn.execute("""
            SELECT m.producto_id, m.producto_padre_id, m.nombre_producto,
                   m.cantidad, m.costo_und,
                   COALESCE(m.valor_total, m.cantidad * m.costo_und, 0) AS total,
                   m.tipo, m.documento_numero
            FROM movimientos_inventario m
            WHERE m.negocio_id = %s
              AND m.documento_numero = %s
              AND m.tipo = 'salida'
            ORDER BY m.nombre_producto
        """, (negocio_id, numero_doc)).fetchall()

        contab_rows = conn.execute("""
            SELECT mc.id, mc.cuenta, c.codigo AS cuenta_codigo, c.nombre AS cuenta_nombre,
                   mc.concepto, mc.tipo, mc.monto,
                   mc.producto_id, mc.producto_padre_id, mc.numero_documento,
                   mc.tipo_documento_id, mc.fecha
            FROM movimientos_contables mc
            LEFT JOIN cuentas_puc c ON c.codigo = mc.cuenta
            WHERE mc.negocio_id = %s
              AND (mc.numero_documento = %s OR mc.numero_documento = %s OR mc.numero_documento = %s)
            ORDER BY mc.concepto
        """, (negocio_id, f'FACTURA_DE_VENTA-{numero_doc}', str(numero_doc), f'VENTA-{numero_doc}')).fetchall()

        contab = [c for c in contab_rows if str(c['cuenta_codigo']).startswith('14') and c['tipo'] == 'credito']

        grupos = conn.execute("""
            SELECT gi.id, gi.nombre, gi.cuenta_inve_id, gi.cuenta_cos_id, gi.cuenta_ingre_id,
                   c_inv.codigo AS cod_inve, c_cos.codigo AS cod_cos, c_ingre.codigo AS cod_ingre
            FROM grupos_inventario gi
            LEFT JOIN cuentas_puc c_inv ON c_inv.id = gi.cuenta_inve_id
            LEFT JOIN cuentas_puc c_cos ON c_cos.id = gi.cuenta_cos_id
            LEFT JOIN cuentas_puc c_ingre ON c_ingre.id = gi.cuenta_ingre_id
            WHERE gi.negocio_id = %s
        """, (negocio_id,)).fetchall()

        todos_contab = [{
                'id': c['id'],
                'cuenta': c['cuenta'],
                'cuenta_codigo': c['cuenta_codigo'],
                'cuenta_nombre': c['cuenta_nombre'],
                'concepto': c['concepto'],
                'tipo': c['tipo'],
                'monto': float(c['monto']),
                'producto_id': c['producto_id'],
                'producto_padre_id': c['producto_padre_id'],
                'numero_documento': c['numero_documento'],
                'tipo_documento_id': c['tipo_documento_id'],
                'fecha': str(c['fecha']) if c.get('fecha') else None,
            } for c in contab_rows]

        return jsonify({
            'ok': True,
            'factura': numero_doc,
            'kardex': [{
                'producto_id': k['producto_id'],
                'producto_padre_id': k['producto_padre_id'],
                'nombre': k['nombre_producto'],
                'cantidad': float(k['cantidad']),
                'costo_und': float(k['costo_und']),
                'total': float(k['total']),
            } for k in kardex],
            'contabilidad_todos': todos_contab,
            'contabilidad_14': [{
                'id': c['id'],
                'cuenta': c['cuenta'],
                'cuenta_codigo': c['cuenta_codigo'],
                'cuenta_nombre': c['cuenta_nombre'],
                'concepto': c['concepto'],
                'tipo': c['tipo'],
                'monto': float(c['monto']),
                'producto_id': c['producto_id'],
                'producto_padre_id': c['producto_padre_id'],
                'numero_documento': c['numero_documento'],
                'tipo_documento_id': c['tipo_documento_id'],
                'fecha': str(c['fecha']) if c.get('fecha') else None,
            } for c in contab],
            'resumen': {
                'kardex_registros': len(kardex),
                'contab_total': len(todos_contab),
                'contab_14': len(contab),
            },
            'grupos_inventario': [{
                'nombre': g['nombre'],
                'cuenta_inve': g['cod_inve'],
                'cuenta_cos': g['cod_cos'],
                'cuenta_ingre': g['cod_ingre'],
            } for g in grupos]
        })
    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500
    finally:
        conn.close()


# ── Vincular producto_id / producto_padre_id en registros contables ───────────
@bp.route('/api/inventario/<int:negocio_id>/vincular-ids-contabilidad', methods=['GET', 'POST'])
def api_vincular_ids_contabilidad(negocio_id):
    """GET=preview de matches, POST=ejecuta UPDATEs.
    Cruza movimientos_contables (Baja Inv 14* credito, producto_id NULL)
    con movimientos_inventario (salida) por nombre del componente y numero_documento.
    Acepta: numero_doc (factura especifica), producto_padre_id + rango fechas, o solo rango.
    """
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    numero_doc = request.args.get('numero_doc', '').strip()
    prod_padre_id = request.args.get('producto_padre_id', type=int)
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    es_ejecucion = request.method == 'POST'

    conn = get_db_connection()
    try:
        # 1. Construir WHERE para Baja Inv
        where_extra = ""
        params = [negocio_id]

        if numero_doc:
            where_extra += " AND (mc.numero_documento = %s OR mc.numero_documento = %s OR mc.numero_documento = %s)"
            params.extend([str(numero_doc), f'FACTURA_DE_VENTA-{numero_doc}', f'VENTA-{numero_doc}'])

        if fecha_desde:
            where_extra += " AND mc.fecha >= %s"
            params.append(fecha_desde)
        if fecha_hasta:
            where_extra += " AND mc.fecha <= %s"
            params.append(fecha_hasta)

        # Si hay producto_padre_id, buscar los documentos que tienen salidas de ese producto
        doc_filter = ""
        if prod_padre_id and not numero_doc:
            doc_rows = conn.execute("""
                SELECT DISTINCT documento_numero FROM movimientos_inventario
                WHERE negocio_id = %s AND producto_padre_id = %s AND tipo = 'salida'
            """, (negocio_id, prod_padre_id)).fetchall()
            doc_nums = list(set([d['documento_numero'] for d in doc_rows if d['documento_numero']]))
            if doc_nums:
                placeholders = ','.join(['%s'] * len(doc_nums))
                doc_filter = f" AND mc.numero_documento IN ({placeholders})"
                params.extend(doc_nums)
            else:
                doc_filter = " AND 1=0"

        contab_rows = conn.execute(f"""
            SELECT mc.id, mc.concepto, mc.monto, mc.numero_documento,
                   mc.cuenta
            FROM movimientos_contables mc
            WHERE mc.negocio_id = %s
              AND mc.cuenta LIKE '14%%'
              AND mc.tipo = 'credito'
              AND UPPER(mc.concepto) LIKE 'BAJA INV:%%'
              AND mc.producto_id IS NULL
              {where_extra}
              {doc_filter}
            ORDER BY mc.concepto, mc.monto
        """, params).fetchall()

        if not contab_rows:
            return jsonify({'ok': True, 'matches': [], 'resumen': {
                'total_contab': 0, 'vinculados': 0, 'sin_kardex': 0
            }})

        # 2. Obtener Kardex salidas - misma lógica de filtros
        k_params = [negocio_id]
        k_where = ""
        if numero_doc:
            k_where += " AND m.documento_numero = %s"
            k_params.append(str(numero_doc))
        if fecha_desde:
            k_where += " AND COALESCE(m.documento_fecha, m.created_at::date) >= %s"
            k_params.append(fecha_desde)
        if fecha_hasta:
            k_where += " AND COALESCE(m.documento_fecha, m.created_at::date) <= %s"
            k_params.append(fecha_hasta)
        if prod_padre_id:
            k_where += " AND m.producto_padre_id = %s"
            k_params.append(prod_padre_id)

        kardex_rows = conn.execute(f"""
            SELECT m.producto_id, m.producto_padre_id, m.nombre_producto,
                   m.documento_numero,
                   m.cantidad, m.costo_und,
                   COALESCE(m.valor_total, m.cantidad * m.costo_und, 0) AS total
            FROM movimientos_inventario m
            WHERE m.negocio_id = %s
              AND m.tipo = 'salida'
              {k_where}
            ORDER BY m.nombre_producto, COALESCE(m.valor_total, m.cantidad * m.costo_und, 0)
        """, k_params).fetchall()

        # Si hay prod_padre_id + numero_doc, filtrar contab_rows a solo los componentes de ese producto
        if prod_padre_id and numero_doc:
            comp_names = set()
            for k in kardex_rows:
                if k['producto_padre_id'] == prod_padre_id:
                    comp_names.add(k['nombre_producto'].strip().upper())
            if comp_names:
                contab_rows = [c for c in contab_rows
                               if c['concepto'].replace('Baja Inv:', '').replace('BAJA INV:', '').strip().upper() in comp_names]

        # 3. Indexar Kardex por nombre + documento
        from collections import defaultdict
        kardex_por_nombre_doc = defaultdict(list)
        for k in kardex_rows:
            nombre_norm = k['nombre_producto'].strip().upper()
            doc = str(k['documento_numero']) if k['documento_numero'] else ''
            kardex_por_nombre_doc[(nombre_norm, doc)].append({
                'producto_id': k['producto_id'],
                'producto_padre_id': k['producto_padre_id'],
                'nombre': k['nombre_producto'],
                'total': float(k['total']),
            })

        # 4. Emparejar: cada entrada Kardex busca su contab más cercana
        matches = []
        sin_kardex = 0

        # Indexar contab por (nombre, doc)
        contab_por_grupo = defaultdict(list)
        for c in contab_rows:
            nombre_comp = c['concepto'].replace('Baja Inv:', '').replace('BAJA INV:', '').strip().upper()
            doc = str(c['numero_documento']) if c['numero_documento'] else ''
            contab_por_grupo[(nombre_comp, doc)].append({
                'id': c['id'],
                'concepto': c['concepto'],
                'monto': float(c['monto']),
            })

        # Iterar Kardex, cada uno busca su pareja contab más cercana
        contab_used = set()
        for (nombre_comp, doc), kardex_list in kardex_por_nombre_doc.items():
            candidatos_contab = contab_por_grupo.get((nombre_comp, doc), [])
            for k in sorted(kardex_list, key=lambda x: x['total']):
                mejor = None
                mejor_dif = float('inf')
                for j, c in enumerate(candidatos_contab):
                    if (nombre_comp, doc, j) in contab_used:
                        continue
                    dif = abs(c['monto'] - k['total'])
                    if dif < mejor_dif:
                        mejor_dif = dif
                        mejor = j
                if mejor is not None:
                    contab_used.add((nombre_comp, doc, mejor))
                    c = candidatos_contab[mejor]
                    matches.append({
                        'contab_id': c['id'],
                        'componente': c['concepto'],
                        'contab_monto': c['monto'],
                        'kardex_producto_id': k['producto_id'],
                        'kardex_producto_padre_id': k['producto_padre_id'],
                        'kardex_nombre': k['nombre'],
                        'kardex_monto': k['total'],
                        'diferencia': c['monto'] - k['total'],
                    })
                else:
                    sin_kardex += 1
                    matches.append({
                        'contab_id': None,
                        'componente': f"Baja Inv: {k['nombre']}",
                        'contab_monto': None,
                        'kardex_producto_id': k['producto_id'],
                        'kardex_producto_padre_id': k['producto_padre_id'],
                        'kardex_nombre': k['nombre'],
                        'kardex_monto': k['total'],
                        'diferencia': None,
                    })

        # 5. Ejecutar si es POST
        vinculados = 0
        if es_ejecucion:
            # Si el frontend envía matches pre-calculados, usarlos directamente
            body_matches = (request.get_json(silent=True) or {}).get('matches')
            if body_matches is not None:
                for m in body_matches:
                    cid = m.get('contab_id')
                    kpid = m.get('kardex_producto_id')
                    kppid = m.get('kardex_producto_padre_id')
                    if cid is not None and kpid is not None:
                        conn.execute("""
                            UPDATE movimientos_contables
                            SET producto_id = %s, producto_padre_id = %s
                            WHERE id = %s AND negocio_id = %s
                        """, (kpid, kppid, cid, negocio_id))
                        vinculados += 1
            else:
                for m in matches:
                    if m['contab_id'] is not None and m['kardex_producto_id'] is not None:
                        conn.execute("""
                            UPDATE movimientos_contables
                            SET producto_id = %s, producto_padre_id = %s
                            WHERE id = %s AND negocio_id = %s
                        """, (m['kardex_producto_id'], m['kardex_producto_padre_id'],
                              m['contab_id'], negocio_id))
                        vinculados += 1
            conn.commit()

        return jsonify({
            'ok': True,
            'ejecutado': es_ejecucion,
            'matches': matches,
            'resumen': {
                'total_contab': len(contab_rows),
                'vinculados': vinculados if es_ejecucion else len([m for m in matches if m['kardex_producto_id']]),
                'sin_kardex': sin_kardex,
            }
        })
    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/desvincular-ids-contabilidad', methods=['POST'])
def api_desvincular_ids_contabilidad(negocio_id):
    """Desvincula: pone producto_id=NULL y producto_padre_id=NULL en movimientos_contables 14*
    para un documento + producto especifico.
    Body JSON: { numero_doc: str, producto_padre_id: int }
    """
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    data = request.get_json(silent=True) or {}
    numero_doc = data.get('numero_doc', '').strip()
    prod_padre_id = data.get('producto_padre_id')

    if not numero_doc and not prod_padre_id:
        return jsonify({'ok': False, 'error': 'numero_doc o producto_padre_id requerido'}), 400

    conn = get_db_connection()
    try:
        # Buscar todas las entradas 14* que tengan producto_padre_id para este documento
        where_extra = ""
        params = [negocio_id]
        if numero_doc:
            where_extra += " AND (mc.numero_documento = %s OR mc.numero_documento = %s OR mc.numero_documento = %s)"
            params.extend([str(numero_doc), f'FACTURA_DE_VENTA-{numero_doc}', f'VENTA-{numero_doc}'])
        if prod_padre_id:
            where_extra += " AND mc.producto_padre_id = %s"
            params.append(prod_padre_id)

        rows = conn.execute(f"""
            SELECT mc.id, mc.concepto, mc.monto, mc.producto_id, mc.producto_padre_id
            FROM movimientos_contables mc
            WHERE mc.negocio_id = %s
              AND mc.cuenta LIKE '14%%'
              AND mc.tipo = 'credito'
              AND UPPER(mc.concepto) LIKE 'BAJA INV:%%'
              AND mc.producto_id IS NOT NULL
              {where_extra}
        """, params).fetchall()

        if not rows:
            return jsonify({'ok': True, 'desvinculados': 0, 'mensaje': 'No hay registros vinculados para desvincular'})

        row_ids = [r['id'] for r in rows]
        placeholders = ','.join(['%s'] * len(row_ids))
        conn.execute(f"""
            UPDATE movimientos_contables
            SET producto_id = NULL, producto_padre_id = NULL
            WHERE id IN ({placeholders})
        """, row_ids)
        conn.commit()

        return jsonify({
            'ok': True,
            'desvinculados': len(rows),
            'detalles': [{'id': r['id'], 'concepto': r['concepto'], 'monto': float(r['monto'])} for r in rows]
        })
    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500
    finally:
        conn.close()


# ── Reparador de Costos de Venta ─────────────────────────────────────────────
@bp.route('/api/inventario/<int:negocio_id>/reparar-costos-venta', methods=['GET', 'POST'])
def api_reparar_costos_venta(negocio_id):
    """Preview (GET) o ejecucion (POST) de reparacion de costos de venta.
    Corrige pedido_items.costo_unitario y movimientos_contables asociados.
    Si no se pasa producto_padre_id, procesa TODOS los productos con salidas en el rango.
    Si se pasa numero_doc, filtra solo esa factura.
    """
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    prod_padre_id = _int_o_none(request.args.get('producto_padre_id'))
    numero_doc = request.args.get('numero_doc', '').strip()
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    es_ejecucion = request.method == 'POST'
    if not fecha_desde or not fecha_hasta:
        return jsonify({'ok': False, 'error': 'Fechas requeridas'}), 400
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto or not _puede_gestionar_negocio(contexto):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
        # 1. Obtener salidas — filtrar por producto padre si se indica, si no todos
        if prod_padre_id:
            padre = conn.execute(
                "SELECT id, nombre FROM productos WHERE id = %s AND negocio_id = %s",
                (prod_padre_id, negocio_id)
            ).fetchone()
            if not padre:
                return jsonify({'ok': False, 'error': 'Producto padre no encontrado'}), 404
            where_extra = "AND m.producto_padre_id = %s"
            params_where = [negocio_id, prod_padre_id, fecha_desde, fecha_hasta]
        else:
            where_extra = ""
            params_where = [negocio_id, fecha_desde, fecha_hasta]
        if numero_doc:
            where_extra += " AND m.documento_numero = %s"
            params_where.append(numero_doc)
        salidas = conn.execute(f"""
            SELECT
                m.documento_numero,
                m.tipo_documento,
                m.tipo_documento_id,
                COALESCE(m.documento_fecha, m.created_at::date) AS fecha,
                m.producto_padre_id,
                m.producto_id,
                m.nombre_producto,
                m.cantidad,
                m.costo_und,
                COALESCE(m.valor_total, m.cantidad * m.costo_und, 0) AS costo_total
            FROM movimientos_inventario m
            WHERE m.negocio_id = %s
              AND m.producto_padre_id IS NOT NULL
              AND m.tipo = 'salida'
              {where_extra}
              AND COALESCE(m.documento_fecha, m.created_at::date) >= %s
              AND COALESCE(m.documento_fecha, m.created_at::date) <= %s
            ORDER BY m.producto_padre_id, m.documento_numero, m.nombre_producto
        """, params_where).fetchall()
        if not salidas:
            return jsonify({'ok': True, 'productos': [], 'resumen': {
                'total_productos': 0, 'total_facturas': 0, 'con_diferencia': 0, 'monto_corregir': 0
            }})
        # Obtener nombres de productos padres
        padres_ids = list(set(s['producto_padre_id'] for s in salidas))
        placeholders = ','.join(['%s'] * len(padres_ids))
        padres_rows = conn.execute(f"""
            SELECT id, nombre FROM productos WHERE id IN ({placeholders}) AND negocio_id = %s
        """, padres_ids + [negocio_id]).fetchall()
        padres_map = {p['id']: p['nombre'] for p in padres_rows}
        # Mapear nombres y codigos de tipos de documento desde tipos_documento_negocio
        td_rows = conn.execute(
            "SELECT id, codigo, nombre FROM tipos_documento_negocio WHERE negocio_id = %s",
            (negocio_id,)
        ).fetchall()
        td_nombre_map = {}
        td_codigo_map = {}
        for td in td_rows:
            td_nombre_map[td['codigo'].upper()] = td['nombre']
            td_nombre_map[td['codigo'].lower()] = td['nombre']
            td_codigo_map[td['id']] = td['codigo']
        # 2. Agrupar por producto padre > factura
        por_producto = {}
        for s in salidas:
            ppid = s['producto_padre_id']
            doc = s['documento_numero']
            if ppid not in por_producto:
                por_producto[ppid] = {}
            if doc not in por_producto[ppid]:
                tipo_doc_codigo = s['tipo_documento'] or 'FACTURA_DE_VENTA'
                tipo_doc_nombre = td_nombre_map.get(tipo_doc_codigo, td_nombre_map.get(tipo_doc_codigo.upper(), tipo_doc_codigo.replace('_', ' ')))
                td_id = s['tipo_documento_id']
                td_code = td_codigo_map.get(td_id, tipo_doc_codigo) if td_id else tipo_doc_codigo
                por_producto[ppid][doc] = {
                    'documento_numero': doc,
                    'tipo_documento': tipo_doc_nombre,
                    'tipo_documento_codigo': td_code,
                    'fecha': s['fecha'].isoformat() if s['fecha'] else '',
                    'componentes': [],
                    'costo_real_kardex': 0,
                }
            ff = por_producto[ppid][doc]
            ff['componentes'].append({
                'producto_id': s['producto_id'],
                'nombre': s['nombre_producto'],
                'cantidad': float(s['cantidad']),
                'costo_und': float(s['costo_und'] or 0),
                'costo_total': float(s['costo_total'] or 0),
            })
            ff['costo_real_kardex'] += float(s['costo_total'] or 0)
        # 3. Para cada producto > factura: buscar costos actuales
        todos_resultados = []
        for ppid, docs in por_producto.items():
            nombre_padre = padres_map.get(ppid, f'ID {ppid}')
            padre_row = conn.execute("SELECT nombre FROM productos WHERE id = %s", (ppid,)).fetchone()
            padre_nombre = padre_row['nombre'] if padre_row else ''
            facturas_producto = []
            for doc_num, f in docs.items():
                consecutive = doc_num.split('-')[-1].strip() if '-' in doc_num else doc_num
                td_code = f.get('tipo_documento_codigo', 'FACTURA_DE_VENTA')
                num_completo = f"{td_code}-{consecutive}"
                # COGS (61*) — SUM
                cogs_row = conn.execute("""
                    SELECT SUM(monto) AS total_cogs
                    FROM movimientos_contables
                    WHERE negocio_id = %s
                      AND (numero_documento = %s OR numero_documento = %s)
                      AND REPLACE(UPPER(tipo_documento), '_', ' ') = REPLACE(UPPER(%s), '_', ' ')
                      AND LEFT(cuenta, 2) = '61'
                      AND (
                          UPPER(concepto) = 'COSTO VENTA: ' || UPPER(%s)
                          OR UPPER(concepto) = 'COSTO DE VENTA: ' || UPPER(%s)
                          OR producto_id = %s
                      )
                """, (negocio_id, consecutive, doc_num, td_code, padre_nombre, padre_nombre, ppid)).fetchone()
                cogs_monto = float(cogs_row['total_cogs']) if (cogs_row and cogs_row['total_cogs'] is not None) else 0.0
                # IDs de asientos 61* para posible correccion
                cogs_ids_row = conn.execute("""
                    SELECT ARRAY_AGG(id) AS ids
                    FROM movimientos_contables
                    WHERE negocio_id = %s
                      AND (numero_documento = %s OR numero_documento = %s)
                      AND REPLACE(UPPER(tipo_documento), '_', ' ') = REPLACE(UPPER(%s), '_', ' ')
                      AND LEFT(cuenta, 2) = '61'
                      AND (
                          UPPER(concepto) = 'COSTO VENTA: ' || UPPER(%s)
                          OR UPPER(concepto) = 'COSTO DE VENTA: ' || UPPER(%s)
                          OR producto_id = %s
                      )
                """, (negocio_id, consecutive, doc_num, td_code, padre_nombre, padre_nombre, ppid)).fetchone()
                cogs_ids = list(cogs_ids_row[0]) if (cogs_ids_row and cogs_ids_row[0]) else []
                # Contrapartidas de inventario (14xxx)
                contras_raw = conn.execute("""
                    SELECT id, monto, cuenta, concepto, producto_id
                    FROM movimientos_contables
                    WHERE negocio_id = %s
                      AND (numero_documento = %s OR numero_documento = %s)
                      AND REPLACE(UPPER(tipo_documento), '_', ' ') = REPLACE(UPPER(%s), '_', ' ')
                      AND LEFT(cuenta, 2) = '14'
                      AND UPPER(concepto) NOT LIKE '%%COSTO%%'
                      AND (producto_padre_id = %s)
                    ORDER BY id
                """, (negocio_id, consecutive, doc_num, td_code, ppid)).fetchall()
                # Indexar componentes por producto_id y por nombre
                comp_por_pid = {}
                comp_por_nombre = {}
                for comp in f['componentes']:
                    comp_por_nombre[comp['nombre'].strip().upper()] = comp
                    if comp.get('producto_id'):
                        comp_por_pid[comp['producto_id']] = comp
                contras = []
                for c in contras_raw:
                    c_pid = c['producto_id']
                    concepto_upper = (c['concepto'] or '').upper()
                    match = comp_por_pid.get(c_pid) if c_pid else None
                    match_tipo = 'producto_id' if match else None
                    if not match:
                        match = next((comp for nombre, comp in comp_por_nombre.items() if nombre in concepto_upper), None)
                        match_tipo = 'nombre' if match else None
                    if match:
                        contras.append({**c, '_comp_match': match, '_match_tipo': match_tipo})
                contras_list = []
                for c in contras:
                    monto = float(c['monto'] or 0)
                    comp_match = c['_comp_match']
                    contras_list.append({
                        'concepto': (c['concepto'] or c['cuenta'] or '').strip(),
                        'cuenta': c['cuenta'],
                        'monto_actual': monto,
                        'producto_id': c.get('producto_id'),
                        'comp_nombre': comp_match['nombre'] if comp_match else None,
                        'match_tipo': c['_match_tipo'],
                    })
                # Cantidad vendida
                ref_row = conn.execute("""
                    SELECT DISTINCT referencia_tipo, referencia_id
                    FROM movimientos_inventario
                    WHERE negocio_id = %s AND producto_padre_id = %s AND documento_numero = %s
                    LIMIT 1
                """, (negocio_id, ppid, doc_num)).fetchone()
                ref_type = ref_row['referencia_tipo'] if ref_row else None
                ref_id = ref_row['referencia_id'] if ref_row else None
                ref_id_int = _int_o_none(ref_id)
                pi_id = None
                qty = 0.0
                if ref_type == 'produccion':
                    qty_row = conn.execute("""
                        SELECT SUM(cantidad) FROM movimientos_inventario
                        WHERE negocio_id = %s AND producto_id = %s AND tipo = 'entrada'
                          AND referencia_tipo = 'produccion' AND (documento_numero = %s OR referencia_id = %s)
                    """, (negocio_id, ppid, doc_num, ref_id)).fetchone()
                    qty = float(qty_row[0]) if (qty_row and qty_row[0] is not None) else 0.0
                else:
                    qty_row = conn.execute("""
                        SELECT SUM(pi.cantidad), MAX(pi.id)
                        FROM pedido_items pi
                        JOIN pedidos p ON p.id = pi.pedido_id
                        WHERE p.negocio_id = %s AND pi.producto_id = %s
                          AND (p.numero_documento = %s OR p.numero_documento = %s OR p.id = %s)
                    """, (negocio_id, ppid, consecutive, doc_num, ref_id_int)).fetchone()
                    qty = float(qty_row[0]) if (qty_row and qty_row[0] is not None) else 0.0
                    pi_id = qty_row[1] if qty_row and qty_row[1] else None
                costo_real = f['costo_real_kardex']
                costo_unitario_real = costo_real / qty if qty > 0 else 0
                costo_actual_pi = 0.0
                if pi_id:
                    pi_cost_row = conn.execute("SELECT costo_unitario FROM pedido_items WHERE id = %s", (pi_id,)).fetchone()
                    costo_actual_pi = float(pi_cost_row['costo_unitario'] or 0) if pi_cost_row else 0
                dif_pi = (costo_actual_pi * qty) - costo_real if qty > 0 else 0
                dif_cogs = cogs_monto - costo_real
                facturas_producto.append({
                    'documento_numero': doc_num,
                    'tipo_documento': f['tipo_documento'],
                    'fecha': f['fecha'],
                    'componentes': f['componentes'],
                    'cantidad_vendida': qty,
                    'costo_real_kardex': costo_real,
                    'costo_unitario_real': round(costo_unitario_real, 2),
                    'pedido_item': {
                        'id': pi_id,
                        'costo_unitario_actual': costo_actual_pi,
                        'diferencia': dif_pi,
                    },
                    'cogs_contable': {
                        'ids': cogs_ids,
                        'monto_actual': cogs_monto,
                        'diferencia': dif_cogs,
                    },
                    'contrapartidas': contras_list,
                    'tiene_diferencia': abs(dif_pi) > 0.01 or abs(dif_cogs) > 0.01,
                })
            con_dif = sum(1 for ff in facturas_producto if ff['tiene_diferencia'])
            total_contable = sum(ff['cogs_contable']['monto_actual'] for ff in facturas_producto if ff['cogs_contable']['ids'])
            total_kardex = sum(ff['costo_real_kardex'] for ff in facturas_producto)
            todos_resultados.append({
                'producto_padre_id': ppid,
                'producto_padre_nombre': nombre_padre,
                'facturas': facturas_producto,
                'con_diferencia': con_dif,
                'costo_total_contable': total_contable,
                'costo_total_kardex': total_kardex,
            })
        # 4. Si es ejecucion, aplicar cambios
        cambios_aplicados = 0
        if es_ejecucion:
            for prod_res in todos_resultados:
                for r in prod_res['facturas']:
                    if not r['tiene_diferencia']:
                        continue
                    if r['pedido_item']['id'] and abs(r['pedido_item']['diferencia']) > 0.01:
                        cant = r['cantidad_vendida']
                        nuevo_costo_und = r['costo_real_kardex'] / cant if cant > 0 else 0
                        conn.execute(
                            "UPDATE pedido_items SET costo_unitario = %s WHERE id = %s",
                            (nuevo_costo_und, r['pedido_item']['id'])
                        )
                        cambios_aplicados += 1
                    if r['cogs_contable']['ids'] and abs(r['cogs_contable']['diferencia']) > 0.01:
                        ids_61 = r['cogs_contable']['ids']
                        conn.execute(
                            "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                            (r['costo_real_kardex'], ids_61[0])
                        )
                        if len(ids_61) > 1:
                            ids_borrar = ids_61[1:]
                            placeholders = ','.join(['%s'] * len(ids_borrar))
                            conn.execute(f"DELETE FROM movimientos_contables WHERE id IN ({placeholders})", ids_borrar)
                        cambios_aplicados += 1
            conn.commit()
        # 5. Resumen
        total_facturas = sum(len(pr['facturas']) for pr in todos_resultados)
        con_diferencia = sum(pr['con_diferencia'] for pr in todos_resultados)
        monto_corregir = 0
        for pr in todos_resultados:
            for ff in pr['facturas']:
                if ff['tiene_diferencia']:
                    monto_corregir += abs(ff['pedido_item']['diferencia'])
        return jsonify({
            'ok': True,
            'ejecutado': es_ejecucion,
            'cambios_aplicados': cambios_aplicados,
            'resumen': {
                'total_productos': len(todos_resultados),
                'total_facturas': total_facturas,
                'con_diferencia': con_diferencia,
                'monto_corregir': round(monto_corregir, 2),
            },
            'productos': todos_resultados,
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/reparar-costos-preview', methods=['GET'])
def api_reparar_costos_preview(negocio_id):
    """Preview de diferencias de costos. Detecta automaticamente:
    - Grupo 2 (produccion): tiene entradas kardex con referencia_tipo='produccion'
    - Grupo 3 (ventas): tiene salidas kardex normales
    Retorna asientos contables correctos segun el tipo.
    """
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    prod_padre_id = request.args.get('producto_padre_id', type=int)
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    numero_doc = request.args.get('numero_doc', '').strip()

    if not fecha_desde or not fecha_hasta:
        return jsonify({'ok': False, 'error': 'Fechas requeridas'}), 400

    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto or not _puede_gestionar_negocio(contexto):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403

        # 1. Obtener productos con movimientos en el rango
        where_extra = ""
        params = [negocio_id, fecha_desde, fecha_hasta]
        if prod_padre_id:
            where_extra = "AND m.producto_padre_id = %s"
            params.append(prod_padre_id)
        if numero_doc:
            where_extra += " AND m.documento_numero = %s"
            params.append(str(numero_doc))

        # Detectar tipo de producto: produccion o venta
        productos_tipo = conn.execute(f"""
            SELECT DISTINCT
                COALESCE(m.producto_padre_id, m.producto_id) AS prod_id,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM movimientos_inventario mi2
                        WHERE mi2.negocio_id = m.negocio_id
                          AND mi2.producto_id = COALESCE(m.producto_padre_id, m.producto_id)
                          AND mi2.tipo = 'entrada'
                          AND mi2.referencia_tipo = 'produccion'
                    ) THEN 'produccion'
                    ELSE 'venta'
                END AS tipo_producto
            FROM movimientos_inventario m
            WHERE m.negocio_id = %s
              AND COALESCE(m.documento_fecha, m.created_at::date) >= %s
              AND COALESCE(m.documento_fecha, m.created_at::date) <= %s
              {where_extra}
        """, params).fetchall()

        tipo_map = {r['prod_id']: r['tipo_producto'] for r in productos_tipo}

        # 2. Para cada tipo, buscar los asientos correspondientes
        todos_resultados = []

        # Grupo 2: Productos de produccion
        prod_produccion = [pid for pid, t in tipo_map.items() if t == 'produccion']
        if prod_produccion:
            ph = ','.join(['%s'] * len(prod_produccion))
            docs_prod = conn.execute(f"""
                SELECT DISTINCT documento_numero
                FROM movimientos_inventario
                WHERE negocio_id = %s AND producto_id IN ({ph})
                  AND tipo = 'entrada' AND referencia_tipo = 'produccion'
                  AND COALESCE(documento_fecha, created_at::date) >= %s
                  AND COALESCE(documento_fecha, created_at::date) <= %s
            """, [negocio_id] + prod_produccion + [fecha_desde, fecha_hasta]).fetchall()

            for doc_row in docs_prod:
                doc_num = str(doc_row['documento_numero'])
                for ppid in prod_produccion:
                    # Buscar entrada kardex del producto terminado
                    kardex_prod = conn.execute("""
                        SELECT id, cantidad, costo_und,
                               COALESCE(valor_total, cantidad * costo_und, 0) AS total
                        FROM movimientos_inventario
                        WHERE negocio_id = %s AND producto_id = %s
                          AND tipo = 'entrada' AND referencia_tipo = 'produccion'
                          AND documento_numero = %s
                        LIMIT 1
                    """, (negocio_id, ppid, doc_num)).fetchone()

                    if not kardex_prod:
                        continue

                    # Buscar asiento 14xx debito (producto terminado) - buscar por cuenta, no por concepto
                    contab_debito = conn.execute("""
                        SELECT id, monto, concepto
                        FROM movimientos_contables
                        WHERE negocio_id = %s
                          AND cuenta LIKE '14%%' AND tipo = 'debito'
                          AND numero_documento = %s
                        ORDER BY id
                        LIMIT 1
                    """, (negocio_id, doc_num)).fetchone()

                    # Buscar asientos 14xx credito (materias primas de produccion)
                    # Excluir BAJA INV (es de ventas) y COSTO (es de costo de venta)
                    contab_creditos = conn.execute("""
                        SELECT id, monto, concepto, cuenta
                        FROM movimientos_contables
                        WHERE negocio_id = %s
                          AND cuenta LIKE '14%%' AND tipo = 'credito'
                          AND numero_documento = %s
                          AND UPPER(concepto) NOT LIKE '%%COSTO%%'
                          AND UPPER(concepto) NOT LIKE '%%BAJA%%'
                        ORDER BY id
                    """, (negocio_id, doc_num)).fetchall()

                    # Buscar salidas kardex de materias primas (las que alimentan la produccion)
                    # Las materias primas salen con referencia_tipo='produccion' y referencia_id apuntando a la produccion
                    ref_id = conn.execute("""
                        SELECT referencia_id FROM movimientos_inventario
                        WHERE negocio_id = %s AND producto_id = %s
                          AND tipo = 'entrada' AND referencia_tipo = 'produccion'
                          AND documento_numero = %s
                        LIMIT 1
                    """, (negocio_id, ppid, doc_num)).fetchone()

                    mp_kardex = []
                    if ref_id and ref_id['referencia_id']:
                        mp_kardex = conn.execute("""
                            SELECT producto_id, nombre_producto,
                                   COALESCE(valor_total, cantidad * costo_und, 0) AS total
                            FROM movimientos_inventario
                            WHERE negocio_id = %s
                              AND tipo = 'salida'
                              AND referencia_tipo = 'produccion'
                              AND referencia_id = %s
                            ORDER BY nombre_producto
                        """, (negocio_id, ref_id['referencia_id'])).fetchall()

                    # Indexar kardex MP por nombre
                    mp_por_nombre = {}
                    for mp in mp_kardex:
                        nombre = mp['nombre_producto'].strip().upper()
                        mp_por_nombre[nombre] = {
                            'producto_id': mp['producto_id'],
                            'nombre': mp['nombre_producto'],
                            'total': float(mp['total']),
                        }

                    # Emparejar creditos contables con kardex MP
                    contrapartidas = []
                    total_contab_debito = float(contab_debito['monto']) if contab_debito else 0
                    total_contab_creditos = 0
                    for c in contab_creditos:
                        nombre_c = (c['concepto'] or '').strip().upper()
                        match = mp_por_nombre.get(nombre_c)
                        if not match:
                            match = next((v for k, v in mp_por_nombre.items() if k in nombre_c or nombre_c in k), None)
                        contrapartidas.append({
                            'id': c['id'],
                            'concepto': c['concepto'],
                            'monto': float(c['monto']),
                            'kardex_nombre': match['nombre'] if match else None,
                            'kardex_total': match['total'] if match else None,
                            'match': match is not None,
                        })
                        total_contab_creditos += float(c['monto'])

                    kardex_total = float(kardex_prod['total'])
                    nombre_prod = conn.execute(
                        "SELECT nombre FROM productos WHERE id = %s AND negocio_id = %s",
                        (ppid, negocio_id)
                    ).fetchone()
                    nombre = nombre_prod['nombre'] if nombre_prod else f'ID {ppid}'

                    todos_resultados.append({
                        'producto_padre_id': ppid,
                        'producto_padre_nombre': nombre,
                        'tipo': 'produccion',
                        'documento_numero': doc_num,
                        'kardex_total': kardex_total,
                        'contab_total': total_contab_debito,
                        'diferencia': total_contab_debito - kardex_total,
                        'contrapartidas': contrapartidas,
                        'tiene_diferencia': abs(total_contab_debito - kardex_total) > 0.01,
                    })

        # Grupo 3: Productos de venta (logica existente simplificada)
        prod_venta = [pid for pid, t in tipo_map.items() if t == 'venta']
        if prod_venta:
            ph = ','.join(['%s'] * len(prod_venta))
            salidas = conn.execute(f"""
                SELECT
                    m.documento_numero,
                    m.producto_padre_id,
                    m.producto_id,
                    m.nombre_producto,
                    COALESCE(m.valor_total, m.cantidad * m.costo_und, 0) AS total
                FROM movimientos_inventario m
                WHERE m.negocio_id = %s
                  AND m.producto_padre_id IN ({ph})
                  AND m.tipo = 'salida'
                  AND COALESCE(m.documento_fecha, m.created_at::date) >= %s
                  AND COALESCE(m.documento_fecha, m.created_at::date) <= %s
                ORDER BY m.producto_padre_id, m.documento_numero
            """, [negocio_id] + prod_venta + [fecha_desde, fecha_hasta]).fetchall()

            # Agrupar por producto > documento
            por_producto = {}
            for s in salidas:
                ppid = s['producto_padre_id']
                doc = str(s['documento_numero'])
                if ppid not in por_producto:
                    por_producto[ppid] = {}
                if doc not in por_producto[ppid]:
                    por_producto[ppid][doc] = {'componentes': [], 'kardex_total': 0}
                por_producto[ppid][doc]['componentes'].append({
                    'nombre': s['nombre_producto'],
                    'total': float(s['total']),
                })
                por_producto[ppid][doc]['kardex_total'] += float(s['total'])

            # Buscar asientos 61* para cada producto/documento
            td_rows = conn.execute(
                "SELECT id, codigo FROM tipos_documento_negocio WHERE negocio_id = %s",
                (negocio_id,)
            ).fetchall()
            td_codigo_map = {td['id']: td['codigo'] for td in td_rows}

            for ppid, docs in por_producto.items():
                nombre_row = conn.execute(
                    "SELECT nombre FROM productos WHERE id = %s AND negocio_id = %s",
                    (ppid, negocio_id)
                ).fetchone()
                nombre = nombre_row['nombre'] if nombre_row else f'ID {ppid}'

                for doc_num, f in docs.items():
                    consecutive = doc_num.split('-')[-1].strip() if '-' in doc_num else doc_num

                    # Buscar tipo documento
                    td_id_row = conn.execute("""
                        SELECT tipo_documento_id FROM movimientos_contables
                        WHERE negocio_id = %s AND numero_documento = %s LIMIT 1
                    """, (negocio_id, consecutive)).fetchone()
                    td_id = td_id_row['tipo_documento_id'] if td_id_row else None
                    td_code = td_codigo_map.get(td_id, 'FACTURA_DE_VENTA') if td_id else 'FACTURA_DE_VENTA'

                    cogs_row = conn.execute("""
                        SELECT id, monto
                        FROM movimientos_contables
                        WHERE negocio_id = %s
                          AND (numero_documento = %s OR numero_documento = %s)
                          AND LEFT(cuenta, 2) = '61'
                          AND (
                              UPPER(concepto) = 'COSTO VENTA: ' || UPPER(%s)
                              OR UPPER(concepto) = 'COSTO DE VENTA: ' || UPPER(%s)
                              OR producto_id = %s
                          )
                        LIMIT 1
                    """, (negocio_id, consecutive, doc_num, nombre, nombre, ppid)).fetchone()

                    contab_total = float(cogs_row['monto']) if cogs_row and cogs_row['monto'] else 0

                    # Buscar contrapartidas 14xx (Baja Inv) y comparar con kardex
                    contras_raw = conn.execute("""
                        SELECT id, monto, cuenta, concepto, producto_id
                        FROM movimientos_contables
                        WHERE negocio_id = %s
                          AND (numero_documento = %s OR numero_documento = %s)
                          AND LEFT(cuenta, 2) = '14'
                          AND UPPER(concepto) NOT LIKE '%%COSTO%%'
                          AND UPPER(concepto) LIKE '%%BAJA%%'
                        ORDER BY id
                    """, (negocio_id, consecutive, doc_num)).fetchall()

                    # Agregar kardex por nombre (sumar si hay multiples entradas del mismo componente)
                    kardex_agregado = {}
                    for comp in f['componentes']:
                        nombre = comp['nombre'].strip().upper()
                        if nombre not in kardex_agregado:
                            kardex_agregado[nombre] = {'nombre': comp['nombre'], 'total': 0.0, 'count': 0}
                        kardex_agregado[nombre]['total'] += float(comp['total'])
                        kardex_agregado[nombre]['count'] += 1

                    # Agregar contable BAJA por nombre
                    contab_agregado = {}
                    for c in contras_raw:
                        concepto_upper = (c['concepto'] or '').strip().upper()
                        nombre_limpio = concepto_upper.replace('BAJA INV:', '').strip()
                        if nombre_limpio not in contab_agregado:
                            contab_agregado[nombre_limpio] = {'monto': 0.0, 'count': 0}
                        contab_agregado[nombre_limpio]['monto'] += float(c['monto'])
                        contab_agregado[nombre_limpio]['count'] += 1

                    # Construir contrapartidas: unirse por nombre
                    todos_nombres = sorted(set(list(kardex_agregado.keys()) + list(contab_agregado.keys())))
                    contrapartidas = []
                    for nombre in todos_nombres:
                        k = kardex_agregado.get(nombre)
                        c = contab_agregado.get(nombre)
                        monto_c = c['monto'] if c else 0
                        total_k = k['total'] if k else None
                        match = k is not None
                        contrapartidas.append({
                            'concepto': k['nombre'] if k else nombre,
                            'monto': monto_c,
                            'kardex_nombre': k['nombre'] if k else None,
                            'kardex_total': total_k,
                            'match': match,
                            'contab_count': c['count'] if c else 0,
                            'kardex_count': k['count'] if k else 0,
                        })

                    todos_resultados.append({
                        'producto_padre_id': ppid,
                        'producto_padre_nombre': nombre,
                        'tipo': 'venta',
                        'documento_numero': doc_num,
                        'kardex_total': f['kardex_total'],
                        'contab_total': contab_total,
                        'diferencia': contab_total - f['kardex_total'],
                        'contrapartidas': contrapartidas,
                        'tiene_diferencia': abs(contab_total - f['kardex_total']) > 0.01,
                    })

        # Ordenar por nombre
        todos_resultados.sort(key=lambda x: x['producto_padre_nombre'])

        con_diferencia = sum(1 for r in todos_resultados if r['tiene_diferencia'])
        return jsonify({
            'ok': True,
            'productos': todos_resultados,
            'resumen': {
                'total_documentos': len(todos_resultados),
                'con_diferencia': con_diferencia,
            }
        })

    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/reparar-costos-documento', methods=['POST'])
def api_reparar_costos_documento(negocio_id):
    """Repara costos. Acepta tres alcances:
    - Documento: { numero_doc, producto_padre_id }
    - Producto: { producto_padre_id, fecha_desde, fecha_hasta }
    - Global: { fecha_desde, fecha_hasta }
    Ajusta movimientos_contables 14*, contrapartida 6xxx y pedido_items.costo_unitario.
    """
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    data = request.get_json(silent=True) or {}
    numero_doc = str(data.get('numero_doc', '')).strip()
    prod_padre_id = data.get('producto_padre_id')
    fecha_desde = data.get('fecha_desde', '').strip()
    fecha_hasta = data.get('fecha_hasta', '').strip()

    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto or not _puede_gestionar_negocio(contexto):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403

        # Mapa de tipos de documento
        td_rows = conn.execute(
            "SELECT id, codigo FROM tipos_documento_negocio WHERE negocio_id = %s",
            (negocio_id,)
        ).fetchall()
        td_codigo_map = {td['id']: td['codigo'] for td in td_rows}

        # Determinar pares (producto_padre_id, numero_doc) a reparar
        pares = []

        if numero_doc and prod_padre_id:
            # Nivel documento
            pares.append((prod_padre_id, numero_doc))

        elif prod_padre_id and not numero_doc:
            # Nivel producto: todos los documentos de ese producto en rango
            where_fechas = ""
            params_k = [negocio_id, prod_padre_id]
            if fecha_desde:
                where_fechas += " AND COALESCE(m.documento_fecha, m.created_at::date) >= %s"
                params_k.append(fecha_desde)
            if fecha_hasta:
                where_fechas += " AND COALESCE(m.documento_fecha, m.created_at::date) <= %s"
                params_k.append(fecha_hasta)
            docs = conn.execute(f"""
                SELECT DISTINCT documento_numero
                FROM movimientos_inventario
                WHERE negocio_id = %s AND producto_padre_id = %s AND tipo = 'salida'
                  {where_fechas}
            """, params_k).fetchall()
            for d in docs:
                if d['documento_numero']:
                    pares.append((prod_padre_id, str(d['documento_numero'])))

        elif fecha_desde and fecha_hasta:
            # Nivel global: todos los productos con salidas en rango
            docs = conn.execute("""
                SELECT DISTINCT producto_padre_id, documento_numero
                FROM movimientos_inventario
                WHERE negocio_id = %s
                  AND tipo = 'salida'
                  AND producto_padre_id IS NOT NULL
                  AND COALESCE(documento_fecha, created_at::date) >= %s
                  AND COALESCE(documento_fecha, created_at::date) <= %s
            """, (negocio_id, fecha_desde, fecha_hasta)).fetchall()
            for d in docs:
                if d['documento_numero']:
                    pares.append((d['producto_padre_id'], str(d['documento_numero'])))
        else:
            return jsonify({'ok': False, 'error': 'Parmetros insuficientes. Envía numero_doc+producto_padre_id, o producto_padre_id+fechas, o solo fechas.'}), 400

        if not pares:
            return jsonify({'ok': True, 'documentos_procesados': 0, 'mensaje': 'No hay documentos para reparar con los filtros indicados'})

        # Procesar cada par (producto, documento)
        resultados = []
        for ppid, doc_num in pares:
            resultado = _reparar_un_documento(conn, negocio_id, ppid, doc_num, td_codigo_map)
            resultados.append(resultado)

        conn.commit()

        total_cambios = sum(len(r['cambios_contables']) for r in resultados)
        total_docs_modificados = sum(1 for r in resultados if r['cambios_contables'] or r['cogs_modificado'] or r['pedido_item_modificado'])

        return jsonify({
            'ok': True,
            'documentos_procesados': len(resultados),
            'documentos_modificados': total_docs_modificados,
            'total_cambios_contables': total_cambios,
            'resultados': resultados,
        })

    except Exception as e:
        conn.rollback()
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500
    finally:
        conn.close()


def _reparar_un_documento(conn, negocio_id, prod_padre_id, numero_doc, td_codigo_map):
    """Repara un par (producto_padre, documento) puntual.
    Detecta automaticamente si es grupo 2 (produccion) o grupo 3 (ventas).
    """
    # Detectar tipo: buscar si hay entradas de produccion para este producto/documento
    es_produccion = conn.execute("""
        SELECT 1 FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s
          AND tipo = 'entrada' AND referencia_tipo = 'produccion'
          AND documento_numero = %s
        LIMIT 1
    """, (negocio_id, prod_padre_id, numero_doc)).fetchone()

    if es_produccion:
        return _reparar_produccion(conn, negocio_id, prod_padre_id, numero_doc)
    else:
        return _reparar_venta(conn, negocio_id, prod_padre_id, numero_doc, td_codigo_map)


def _reparar_produccion(conn, negocio_id, prod_padre_id, numero_doc):
    """Repara un documento de produccion (grupo 2).
    Ajusta los asientos 14xx (debito=producto terminado, creditos=materias primas).
    """
    # 1. Buscar entrada kardex del producto terminado
    kardex_prod = conn.execute("""
        SELECT id, cantidad, costo_und,
               COALESCE(valor_total, cantidad * costo_und, 0) AS total,
               referencia_id
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s
          AND tipo = 'entrada' AND referencia_tipo = 'produccion'
          AND documento_numero = %s
        LIMIT 1
    """, (negocio_id, prod_padre_id, numero_doc)).fetchone()

    if not kardex_prod:
        return {'numero_doc': numero_doc, 'producto_padre_id': prod_padre_id,
                'cambios_contables': [], 'tipo': 'produccion', 'skip': True}

    ref_id = kardex_prod['referencia_id']

    # 2. Buscar asiento 14xx debito (producto terminado)
    padre_row = conn.execute(
        "SELECT nombre FROM productos WHERE id = %s AND negocio_id = %s",
        (prod_padre_id, negocio_id)
    ).fetchone()
    padre_nombre = padre_row['nombre'] if padre_row else ''

    contab_debito = conn.execute("""
        SELECT id, monto, concepto
        FROM movimientos_contables
        WHERE negocio_id = %s
          AND cuenta LIKE '14%%' AND tipo = 'debito'
          AND numero_documento = %s
        ORDER BY id
        LIMIT 1
    """, (negocio_id, numero_doc)).fetchone()

    # 3. Buscar asientos 14xx credito (materias primas de produccion)
    # Excluir BAJA INV (es de ventas) y COSTO (es de costo de venta)
    contab_creditos = conn.execute("""
        SELECT id, monto, concepto, cuenta
        FROM movimientos_contables
        WHERE negocio_id = %s
          AND cuenta LIKE '14%%' AND tipo = 'credito'
          AND numero_documento = %s
          AND UPPER(concepto) NOT LIKE '%%COSTO%%'
          AND UPPER(concepto) NOT LIKE '%%BAJA%%'
        ORDER BY id
    """, (negocio_id, numero_doc)).fetchall()

    # 4. Buscar salidas kardex de materias primas
    mp_kardex = []
    if ref_id:
        mp_kardex = conn.execute("""
            SELECT producto_id, nombre_producto,
                   COALESCE(valor_total, cantidad * costo_und, 0) AS total
            FROM movimientos_inventario
            WHERE negocio_id = %s
              AND tipo = 'salida'
              AND referencia_tipo = 'produccion'
              AND referencia_id = %s
            ORDER BY nombre_producto
        """, (negocio_id, ref_id)).fetchall()

    # Indexar kardex MP por nombre
    mp_por_nombre = {}
    for mp in mp_kardex:
        nombre = mp['nombre_producto'].strip().upper()
        mp_por_nombre[nombre] = {
            'producto_id': mp['producto_id'],
            'nombre': mp['nombre_producto'],
            'total': float(mp['total']),
        }

    # 5. Emparejar y actualizar creditos (materias primas)
    cambios = []
    total_nuevo_creditos = 0
    for c in contab_creditos:
        nombre_c = (c['concepto'] or '').strip().upper()
        match = mp_por_nombre.get(nombre_c)
        if not match:
            match = next((v for k, v in mp_por_nombre.items() if k in nombre_c or nombre_c in k), None)

        if match:
            nuevo_monto = match['total']
            if abs(float(c['monto']) - nuevo_monto) > 0.01:
                conn.execute(
                    "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                    (nuevo_monto, c['id'])
                )
                cambios.append({
                    'id': c['id'],
                    'concepto': c['concepto'],
                    'monto_anterior': float(c['monto']),
                    'monto_nuevo': nuevo_monto,
                    'componente': match['nombre'],
                })
            total_nuevo_creditos += nuevo_monto
        else:
            total_nuevo_creditos += float(c['monto'])

    # 6. Actualizar debito (producto terminado) = suma de creditos
    debito_modificado = False
    if contab_debito:
        monto_actual = float(contab_debito['monto'] or 0)
        if abs(monto_actual - total_nuevo_creditos) > 0.01:
            conn.execute(
                "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                (total_nuevo_creditos, contab_debito['id'])
            )
            debito_modificado = True

    return {
        'numero_doc': numero_doc,
        'producto_padre_id': prod_padre_id,
        'tipo': 'produccion',
        'cambios_contables': cambios,
        'debito_modificado': debito_modificado,
        'debito_id': contab_debito['id'] if contab_debito else None,
    }


def _reparar_venta(conn, negocio_id, prod_padre_id, numero_doc, td_codigo_map):
    """Repara un documento de venta (grupo 3).
    Ajusta 14* credito (Baja Inv), 61* debito (Costo Venta) y pedido_items.
    """
    # 1. Buscar entradas 14* vinculadas
    contab_rows = conn.execute("""
        SELECT id, monto, cuenta, concepto, producto_id
        FROM movimientos_contables
        WHERE negocio_id = %s
          AND cuenta LIKE '14%%'
          AND tipo = 'credito'
          AND UPPER(concepto) LIKE 'BAJA INV:%%'
          AND producto_padre_id = %s
          AND (numero_documento = %s OR numero_documento = %s)
        ORDER BY id
    """, (negocio_id, prod_padre_id, numero_doc, str(numero_doc))).fetchall()

    if not contab_rows:
        return {'numero_doc': numero_doc, 'producto_padre_id': prod_padre_id,
                'cambios_contables': [], 'tipo': 'venta', 'skip': True}

    # 2. Buscar salidas kardex
    kardex_rows = conn.execute("""
        SELECT producto_id, nombre_producto,
               cantidad, costo_und,
               COALESCE(valor_total, cantidad * costo_und, 0) AS total
        FROM movimientos_inventario
        WHERE negocio_id = %s
          AND producto_padre_id = %s
          AND tipo = 'salida'
          AND documento_numero = %s
        ORDER BY nombre_producto
    """, (negocio_id, prod_padre_id, numero_doc)).fetchall()

    if not kardex_rows:
        return {'numero_doc': numero_doc, 'producto_padre_id': prod_padre_id,
                'cambios_contables': [], 'tipo': 'venta', 'skip': True}

    # 3. Indexar kardex
    comp_por_pid = {}
    comp_por_nombre = {}
    for k in kardex_rows:
        total = float(k['total'])
        comp_por_nombre[k['nombre_producto'].strip().upper()] = {
            'producto_id': k['producto_id'],
            'nombre': k['nombre_producto'],
            'total': total,
        }
        if k['producto_id']:
            comp_por_pid[k['producto_id']] = {
                'nombre': k['nombre_producto'],
                'total': total,
            }

    # 4. Emparejar y actualizar cada 14*
    cambios = []
    total_nuevo_14 = 0
    for c in contab_rows:
        c_pid = c['producto_id']
        match = comp_por_pid.get(c_pid) if c_pid else None
        if not match:
            concepto_upper = (c['concepto'] or '').upper()
            match = next((v for kn, v in comp_por_nombre.items() if kn in concepto_upper), None)

        if match:
            nuevo_monto = match['total']
            if abs(float(c['monto']) - nuevo_monto) > 0.01:
                conn.execute(
                    "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                    (nuevo_monto, c['id'])
                )
                cambios.append({
                    'id': c['id'],
                    'concepto': c['concepto'],
                    'monto_anterior': float(c['monto']),
                    'monto_nuevo': nuevo_monto,
                    'componente': match['nombre'],
                })
            total_nuevo_14 += nuevo_monto
        else:
            total_nuevo_14 += float(c['monto'])

    # 5. Buscar y actualizar contrapartida 6xxx
    td_id_row = conn.execute("""
        SELECT tipo_documento_id FROM movimientos_contables WHERE id = %s
    """, (contab_rows[0]['id'],)).fetchone()
    td_id = td_id_row['tipo_documento_id'] if td_id_row else None
    td_code = td_codigo_map.get(td_id, 'FACTURA_DE_VENTA') if td_id else 'FACTURA_DE_VENTA'
    consecutive = numero_doc.split('-')[-1].strip() if '-' in numero_doc else numero_doc

    padre_row = conn.execute(
        "SELECT nombre FROM productos WHERE id = %s AND negocio_id = %s",
        (prod_padre_id, negocio_id)
    ).fetchone()
    padre_nombre = padre_row['nombre'] if padre_row else ''

    cogs_row = conn.execute("""
        SELECT id, monto
        FROM movimientos_contables
        WHERE negocio_id = %s
          AND (numero_documento = %s OR numero_documento = %s)
          AND REPLACE(UPPER(tipo_documento), '_', ' ') = REPLACE(UPPER(%s), '_', ' ')
          AND LEFT(cuenta, 2) = '61'
          AND (
              UPPER(concepto) = 'COSTO VENTA: ' || UPPER(%s)
              OR UPPER(concepto) = 'COSTO DE VENTA: ' || UPPER(%s)
              OR producto_id = %s
          )
        LIMIT 1
    """, (negocio_id, consecutive, numero_doc, td_code, padre_nombre, padre_nombre, prod_padre_id)).fetchone()

    cogs_modificado = False
    if cogs_row:
        monto_actual_cogs = float(cogs_row['monto'] or 0)
        if abs(monto_actual_cogs - total_nuevo_14) > 0.01:
            conn.execute(
                "UPDATE movimientos_contables SET monto = %s WHERE id = %s",
                (total_nuevo_14, cogs_row['id'])
            )
            cogs_modificado = True

    # 6. Actualizar pedido_items.costo_unitario
    ref_row = conn.execute("""
        SELECT DISTINCT referencia_tipo, referencia_id
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_padre_id = %s AND documento_numero = %s
        LIMIT 1
    """, (negocio_id, prod_padre_id, numero_doc)).fetchone()

    ref_type = ref_row['referencia_tipo'] if ref_row else None
    ref_id = ref_row['referencia_id'] if ref_row else None
    ref_id_int = _int_o_none(ref_id)

    pi_modificado = False
    qty = 0.0
    if ref_type != 'produccion':
        qty_row = conn.execute("""
            SELECT SUM(pi.cantidad), MAX(pi.id)
            FROM pedido_items pi
            JOIN pedidos p ON p.id = pi.pedido_id
            WHERE p.negocio_id = %s AND pi.producto_id = %s
              AND (p.numero_documento = %s OR p.numero_documento = %s OR p.id = %s)
        """, (negocio_id, prod_padre_id, consecutive, numero_doc, ref_id_int)).fetchone()
        qty = float(qty_row[0]) if (qty_row and qty_row[0] is not None) else 0.0
        pi_id = qty_row[1] if qty_row and qty_row[1] else None

        if pi_id and qty > 0:
            nuevo_costo_und = total_nuevo_14 / qty
            conn.execute(
                "UPDATE pedido_items SET costo_unitario = %s WHERE id = %s",
                (nuevo_costo_und, pi_id)
            )
            pi_modificado = True

    return {
        'numero_doc': numero_doc,
        'producto_padre_id': prod_padre_id,
        'tipo': 'venta',
        'cambios_contables': cambios,
        'cogs_modificado': cogs_modificado,
        'cogs_id': cogs_row['id'] if cogs_row else None,
        'pedido_item_modificado': pi_modificado,
    }


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
                'cant_tarjeta':  float(c['cant_tarjeta']),
                'a_consumir':   float(a_consumir),
                'stock_actual': float(stock_actual),
                'costo_und':    float(costo_und),
                'costo_total':  float(costo_total),
                'suficiente':   suficiente,
            })
            
        costo_unitario_produccion = costo_total_produccion / qty if qty > 0 else Decimal('0')
        return jsonify({
            'ok': True,
            'producto_id': producto_id,
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
    tercero_id  = _int_o_none(data.get('tercero_id'))
    tercero_nombre = data.get('tercero_nombre') or None
    fecha_raw   = (_txt(data.get('fecha')) or '').strip()
    fecha_prod  = _fecha_o_none(fecha_raw) or date.today()

    if not producto_id or cantidad <= 0:
        return jsonify({'ok': False, 'error': 'producto_id y cantidad requeridos'}), 400
    if fecha_prod > date.today():
        return jsonify({'ok': False, 'error': 'La fecha de producción no puede ser futura'}), 400

    conn = get_db_connection()
    try:
        _crear_tablas(conn)
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error

        try:
            from .contabilidad import _verificar_periodo_cerrado
            _verificar_periodo_cerrado(conn, negocio_id, fecha_prod)
        except Exception as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400
        
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
                    try:
                        documento_numero = str(int(res_num))
                    except (ValueError, TypeError):
                        documento_numero = str(res_num)
            else:
                if not documento_numero:
                    return jsonify({'ok': False, 'error': f'El número de documento es obligatorio para el tipo de documento externo {tipo_documento}.'}), 400

        producto = conn.execute(
            "SELECT nombre FROM productos WHERE id=%s AND negocio_id=%s",
            (producto_id, negocio_id)
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no encontrado'}), 404
        # Cargar componentes
        componentes_override = data.get('componentes')
        if componentes_override:
            # Viene override de componentes en la petición
            componentes_datos = []
            for c in componentes_override:
                componentes_datos.append({
                    'componente_id': int(c['componente_id']),
                    'cantidad_total': Decimal(str(c['cantidad']))
                })
        else:
            # Por defecto, leer de la tarjeta estándar y multiplicar por la cantidad producida
            componentes_db = conn.execute(
                "SELECT componente_id, cantidad FROM tarjeta_estandar WHERE producto_id=%s",
                (producto_id,)
            ).fetchall()
            if not componentes_db:
                return jsonify({'ok': False, 'error': 'Sin tarjeta estándar'}), 400
            componentes_datos = []
            for c in componentes_db:
                componentes_datos.append({
                    'componente_id': c['componente_id'],
                    'cantidad_total': Decimal(str(c['cantidad'])) * cantidad
                })

        # Verificar stock suficiente y leer costos ANTES de aplicar salidas
        faltantes    = []
        costo_total  = Decimal('0')
        comps_cont   = []
        for c in componentes_datos:
            a_consumir = c['cantidad_total']
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
        for i, c in enumerate(componentes_datos):
            cant_comp = c['cantidad_total']
            comp_cost = comps_cont[i]['costo_und']
            _mov_directo(conn, negocio_id, c['componente_id'], cant_comp,
                         'salida', 'produccion', session['usuario_id'],
                         valor_unitario=comp_cost,
                         notas=notas, referencia_tipo='produccion', referencia_id=prod_token,
                         producto_padre_id=producto_id,
                         tipo_documento=tipo_documento, documento_numero=documento_numero,
                         documento_fecha=fecha_prod,
                         tipo_documento_id=tipo_doc_id,
                         proveedor_id=tercero_id,
                         proveedor_nombre=tercero_nombre)

        # Entrada del terminado con costo calculado desde componentes
        _mov_directo(conn, negocio_id, producto_id, cantidad,
                     'entrada', 'produccion', session['usuario_id'],
                     valor_unitario=costo_unitario,
                     notas=notas, referencia_tipo='produccion', referencia_id=prod_token,
                     tipo_documento=tipo_documento, documento_numero=documento_numero,
                     documento_fecha=fecha_prod,
                     tipo_documento_id=tipo_doc_id,
                     proveedor_id=tercero_id,
                     proveedor_nombre=tercero_nombre)

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
                    tipo_documento_id=tipo_doc_id,
                    tercero_id=tercero_id,
                    fecha=fecha_prod
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


def _auditar_producto_recosteo(conn, negocio_id, producto_id):
    """Reconstruye un producto sin modificarlo y devuelve sus inconsistencias."""
    producto = conn.execute(
        "SELECT id, nombre FROM productos WHERE id = %s AND negocio_id = %s",
        (producto_id, negocio_id)
    ).fetchone()
    if not producto:
        return None

    movimientos = conn.execute("""
        SELECT id, tipo, cantidad, valor_unitario, stock_anterior,
               stock_nuevo, costo_und, documento_fecha, created_at
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s
        ORDER BY COALESCE(documento_fecha, created_at::date) ASC,
                 created_at ASC, id ASC
    """, (negocio_id, producto_id)).fetchall()

    stock = Decimal('0')
    valor_existencia = Decimal('0')
    costo_und = Decimal('0')
    negativos = []
    inconsistencias = []

    def diferente(a, b):
        return abs(Decimal(str(a or 0)) - Decimal(str(b or 0))) > Decimal('0.0001')

    for mov in movimientos:
        cantidad = Decimal(str(mov['cantidad'] or 0))
        signo = Decimal('1') if mov['tipo'] == 'entrada' else Decimal('-1')
        stock_anterior = stock
        stock_nuevo = stock_anterior + cantidad * signo

        if mov['tipo'] == 'entrada' and mov['valor_unitario'] is not None:
            valor_unitario = Decimal(str(mov['valor_unitario']))
            costo_und = ((valor_existencia + cantidad * valor_unitario) / stock_nuevo
                         if stock_nuevo > 0 else valor_unitario)
            valor_existencia = (stock_nuevo * costo_und
                                if stock_nuevo > 0 else Decimal('0'))
        else:
            valor_existencia = (stock_nuevo * costo_und
                                if stock_nuevo > 0 else Decimal('0'))

        fecha = mov['documento_fecha'] or mov['created_at']
        fecha_texto = fecha.isoformat() if hasattr(fecha, 'isoformat') else str(fecha or '')
        if stock_nuevo < 0:
            negativos.append({
                'movimiento_id': mov['id'],
                'fecha': fecha_texto,
                'tipo': mov['tipo'],
                'stock': float(stock_nuevo)
            })

        if (diferente(mov['stock_anterior'], stock_anterior)
                or diferente(mov['stock_nuevo'], stock_nuevo)):
            inconsistencias.append({
                'movimiento_id': mov['id'],
                'fecha': fecha_texto,
                'guardado_anterior': float(mov['stock_anterior'] or 0),
                'calculado_anterior': float(stock_anterior),
                'guardado_nuevo': float(mov['stock_nuevo'] or 0),
                'calculado_nuevo': float(stock_nuevo)
            })

        stock = stock_nuevo

    saldo = conn.execute("""
        SELECT stock, costo_und, valor_existencia
        FROM saldos_inventario
        WHERE negocio_id = %s AND producto_id = %s AND bodega = 1
    """, (negocio_id, producto_id)).fetchone()
    stock_inconsistente = bool(saldo and diferente(saldo['stock'], stock))
    costo_inconsistente = bool(saldo and diferente(saldo['costo_und'], costo_und))
    valor_inconsistente = bool(
        saldo and abs(Decimal(str(saldo['valor_existencia'] or 0)) - valor_existencia)
        >= Decimal('1')
    )

    return {
        'producto_id': producto_id,
        'producto_nombre': producto['nombre'],
        'movimientos': len(movimientos),
        'stock_final': float(stock),
        'costo_reconstruido': float(costo_und),
        'stock_almacenado': float(saldo['stock']) if saldo else None,
        'costo_almacenado': float(saldo['costo_und']) if saldo else None,
        'valor_almacenado': float(saldo['valor_existencia']) if saldo else None,
        'valor_reconstruido': float(valor_existencia),
        'diferencia_valor': float((saldo['valor_existencia'] - valor_existencia) if saldo else 0),
        'stock_inconsistente': stock_inconsistente,
        'costo_inconsistente': costo_inconsistente,
        'valor_inconsistente': valor_inconsistente,
        'saldo_inconsistente': stock_inconsistente or costo_inconsistente or valor_inconsistente,
        'negativo_final': stock < 0,
        'negativos_intermedios': negativos,
        'inconsistencias_movimientos': inconsistencias,
        'problemas': bool(stock < 0 or negativos or inconsistencias
                          or stock_inconsistente or costo_inconsistente
                          or valor_inconsistente)
    }


@bp.route('/api/inventario/<int:negocio_id>/recosteo/auditoria', methods=['GET'])
def api_auditoria_recosteo(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        ids_raw = request.args.get('producto_ids', '').strip()
        if ids_raw:
            producto_ids = sorted({int(x) for x in ids_raw.split(',') if x.strip()})
        else:
            rows = conn.execute("""
                SELECT DISTINCT producto_id
                FROM movimientos_inventario
                WHERE negocio_id = %s
                ORDER BY producto_id
            """, (negocio_id,)).fetchall()
            producto_ids = [r['producto_id'] for r in rows]

        productos_auditados = []
        for producto_id in producto_ids:
            resultado = _auditar_producto_recosteo(conn, negocio_id, producto_id)
            if resultado:
                productos_auditados.append(resultado)

        return jsonify({
            'ok': True,
            'productos_revisados': len(productos_auditados),
            'productos': productos_auditados,
            'resumen': {
                'negativos_finales': sum(1 for p in productos_auditados if p['negativo_final']),
                'negativos_intermedios': sum(1 for p in productos_auditados if p['negativos_intermedios']),
                'cadenas_inconsistentes': sum(1 for p in productos_auditados if p['inconsistencias_movimientos']),
                'saldos_inconsistentes': sum(1 for p in productos_auditados if p['saldo_inconsistente']),
                'stocks_inconsistentes': sum(1 for p in productos_auditados if p['stock_inconsistente']),
                'costos_inconsistentes': sum(1 for p in productos_auditados if p['costo_inconsistente']),
                'valores_inconsistentes': sum(1 for p in productos_auditados if p['valor_inconsistente'])
            }
        })
    except ValueError:
        return jsonify({'ok': False, 'error': 'Lista de productos inválida'}), 400
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/recosteo/ejecutar', methods=['POST'])
def api_ejecutar_recosteo(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        producto_ids = data.get('producto_ids')
        if data.get('todos') or not producto_ids:
            rows = conn.execute("""
                SELECT DISTINCT producto_id
                FROM movimientos_inventario
                WHERE negocio_id = %s
            """, (negocio_id,)).fetchall()
            producto_ids = [r['producto_id'] for r in rows]
        producto_ids = sorted({int(x) for x in producto_ids})

        for producto_id in producto_ids:
            if not conn.execute(
                "SELECT 1 FROM productos WHERE id = %s AND negocio_id = %s",
                (producto_id, negocio_id)
            ).fetchone():
                return jsonify({'ok': False, 'error': f'Producto no pertenece al negocio: {producto_id}'}), 400
            _recostear_producto(conn, negocio_id, producto_id)

        conn.commit()
        return jsonify({
            'ok': True,
            'productos_recosteados': len(producto_ids),
            'auditoria': 'Ejecute la auditoría nuevamente para verificar resultados.'
        })
    except (TypeError, ValueError):
        conn.rollback()
        return jsonify({'ok': False, 'error': 'Lista de productos inválida'}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/documento/verificar-cambio-fecha', methods=['POST'])
def api_verificar_cambio_fecha_documento(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    data = request.get_json() or {}
    tipo_documento_id = _int_o_none(data.get('tipo_documento_id'))
    tipo_documento = (_txt(data.get('tipo_documento')) or '').strip()
    documento_numero = (_txt(data.get('documento_numero')) or '').strip()
    nueva_fecha_raw = (_txt(data.get('nueva_fecha')) or '').strip()
    nueva_hora = (_txt(data.get('nueva_hora')) or '').strip() or None

    if (not tipo_documento_id and not tipo_documento) or not documento_numero:
        return jsonify({'ok': False, 'error': 'Tipo de documento y número son requeridos'}), 400

    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error

        if not tipo_documento_id:
            tipo_row = conn.execute("""
                SELECT id, codigo, nombre FROM tipos_documento_negocio
                WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))
                LIMIT 1
            """, (negocio_id, tipo_documento, tipo_documento)).fetchone()
            if tipo_row:
                tipo_documento_id = tipo_row['id']
                tipo_documento = tipo_row['codigo'] or tipo_row['nombre']
        else:
            tipo_row = conn.execute("SELECT codigo, nombre FROM tipos_documento_negocio WHERE id = %s", (tipo_documento_id,)).fetchone()
            if tipo_row:
                tipo_documento = tipo_row['codigo'] or tipo_row['nombre']

        rows = conn.execute("""
            SELECT m.id, m.producto_id, p.nombre AS producto_nombre, m.tipo, m.cantidad, 
                   m.valor_unitario, m.costo_und, m.documento_fecha, m.created_at,
                   COALESCE(t.nombre, m.proveedor_nombre) AS proveedor_nombre,
                   m.tipo_documento, m.documento_numero
            FROM movimientos_inventario m
            JOIN productos p ON p.id = m.producto_id
            LEFT JOIN terceros t ON t.id = m.proveedor_id
            WHERE m.negocio_id = %s 
              AND (m.tipo_documento_id = %s OR LOWER(m.tipo_documento) = LOWER(%s))
              AND m.documento_numero = %s
            ORDER BY m.id ASC
        """, (negocio_id, tipo_documento_id, tipo_documento, documento_numero)).fetchall()

        if not rows:
            return jsonify({'ok': False, 'error': 'No se encontraron movimientos para ese documento'}), 404

        fecha_original = min((r['documento_fecha'] or r['created_at'].date()) for r in rows)
        hora_original = rows[0]['created_at'].strftime('%H:%M') if rows[0]['created_at'] else '00:00'
        created_at_original = rows[0]['created_at']

        target_fecha = nueva_fecha_raw[:10] if nueva_fecha_raw else fecha_original.isoformat()
        target_hora = nueva_hora if nueva_hora else hora_original

        from datetime import datetime, time
        try:
            d_obj = date.fromisoformat(target_fecha)
            h_obj = time.fromisoformat(target_hora if len(target_hora) == 5 else target_hora[:5])
            target_dt = datetime.combine(d_obj, h_obj)
        except Exception:
            target_dt = created_at_original

        min_dt = min(target_dt, created_at_original) if (target_dt and created_at_original) else (target_dt or created_at_original)

        items = []
        total_movimientos_posteriores = 0

        for r in rows:
            p_id = r['producto_id']
            posteriores = conn.execute("""
                SELECT COUNT(*) AS total
                FROM movimientos_inventario
                WHERE negocio_id = %s AND producto_id = %s AND created_at >= %s AND id != %s
            """, (negocio_id, p_id, min_dt, r['id'])).fetchone()['total']

            total_movimientos_posteriores += posteriores

            items.append({
                'movimiento_id': r['id'],
                'producto_id': p_id,
                'producto_nombre': r['producto_nombre'],
                'tipo': r['tipo'],
                'cantidad': float(r['cantidad'] or 0),
                'valor_unitario': float(r['valor_unitario'] or 0),
                'costo_und': float(r['costo_und'] or 0),
                'movimientos_posteriores': posteriores
            })

        return jsonify({
            'ok': True,
            'documento': {
                'tipo_documento': tipo_documento or rows[0]['tipo_documento'],
                'tipo_documento_id': tipo_documento_id,
                'documento_numero': documento_numero,
                'fecha_actual': fecha_original.isoformat(),
                'hora_actual': hora_original,
                'nueva_fecha': target_fecha,
                'nueva_hora': target_hora[:5],
                'proveedor_nombre': rows[0]['proveedor_nombre']
            },
            'items': items,
            'total_items': len(items),
            'total_movimientos_posteriores': total_movimientos_posteriores
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/documento/cambiar-fecha', methods=['POST'])
def api_cambiar_fecha_documento_inventario(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    data = request.get_json() or {}
    tipo_documento_id = _int_o_none(data.get('tipo_documento_id'))
    tipo_documento = (_txt(data.get('tipo_documento')) or '').strip()
    documento_numero = (_txt(data.get('documento_numero')) or '').strip()
    nueva_fecha_raw = (_txt(data.get('nueva_fecha')) or '').strip()
    nueva_hora = (_txt(data.get('nueva_hora')) or '').strip() or None
    if (not tipo_documento_id and not tipo_documento) or not documento_numero or not nueva_fecha_raw:
        return jsonify({'ok': False, 'error': 'Tipo de documento, número y nueva fecha son requeridos'}), 400

    try:
        from datetime import datetime, time
        nueva_fecha = date.fromisoformat(nueva_fecha_raw[:10])
        hora = time.fromisoformat(nueva_hora if len(nueva_hora or '') == 5 else (nueva_hora[:5] if nueva_hora else '00:00')) if nueva_hora else None
    except ValueError:
        return jsonify({'ok': False, 'error': 'Fecha u hora inválida'}), 400

    if nueva_fecha > date.today():
        return jsonify({'ok': False, 'error': 'La fecha del documento no puede ser futura'}), 400

    conn = get_db_connection()
    try:
        _contexto, error = _validar_negocio_json(conn, negocio_id)
        if error:
            return error
        if not tipo_documento_id:
            tipo_row = conn.execute("""
                SELECT id, codigo, nombre FROM tipos_documento_negocio
                WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))
                LIMIT 1
            """, (negocio_id, tipo_documento, tipo_documento)).fetchone()
            if not tipo_row:
                return jsonify({'ok': False, 'error': 'No se pudo identificar el tipo de documento'}), 400
            tipo_documento_id = tipo_row['id']
            tipo_documento = tipo_row['codigo'] or tipo_row['nombre']
        else:
            tipo_row = conn.execute("SELECT codigo, nombre FROM tipos_documento_negocio WHERE id = %s", (tipo_documento_id,)).fetchone()
            if tipo_row:
                tipo_documento = tipo_row['codigo'] or tipo_row['nombre']

        rows = conn.execute("""
            SELECT id, producto_id, documento_fecha, created_at
            FROM movimientos_inventario
            WHERE negocio_id = %s AND (tipo_documento_id = %s OR LOWER(tipo_documento) = LOWER(%s)) AND documento_numero = %s
        """, (negocio_id, tipo_documento_id, tipo_documento, documento_numero)).fetchall()
        if not rows:
            return jsonify({'ok': False, 'error': 'No se encontraron movimientos para ese documento'}), 404

        fecha_anterior = min((r['documento_fecha'] or r['created_at'].date()) for r in rows)
        try:
            _verificar_periodo_cerrado(conn, negocio_id, fecha_anterior)
            _verificar_periodo_cerrado(conn, negocio_id, nueva_fecha)
        except Exception as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400

        hora_uso = hora or (rows[0]['created_at'].time() if rows[0]['created_at'] else time(0, 0))
        fecha_hora = datetime.combine(nueva_fecha, hora_uso)

        # 1. Actualizar movimientos de inventario
        conn.execute("""
            UPDATE movimientos_inventario
            SET documento_fecha = %s, created_at = %s
            WHERE negocio_id = %s 
              AND (tipo_documento_id = %s OR LOWER(COALESCE(tipo_documento, '')) = LOWER(%s)) 
              AND documento_numero = %s
        """, (nueva_fecha, fecha_hora, negocio_id, tipo_documento_id, tipo_documento, documento_numero))

        # 2. Actualizar movimientos contables
        conn.execute("""
            UPDATE movimientos_contables
            SET fecha = %s, created_at = %s
            WHERE negocio_id = %s 
              AND (tipo_documento_id = %s OR LOWER(COALESCE(tipo_documento, '')) = LOWER(%s)) 
              AND numero_documento = %s
        """, (nueva_fecha, fecha_hora, negocio_id, tipo_documento_id, tipo_documento, documento_numero))

        # 3. Actualizar saldo_por_documentos
        conn.execute("""
            UPDATE saldo_por_documentos
            SET fecha_hora = %s, created_at = %s
            WHERE negocio_id = %s 
              AND (tipo_documento_id = %s OR LOWER(COALESCE(tipo_documento, '')) = LOWER(%s)) 
              AND numero_documento = %s
        """, (fecha_hora, fecha_hora, negocio_id, tipo_documento_id, tipo_documento, documento_numero))

        # Recostear en cascada todos los productos de este documento
        producto_ids = sorted({r['producto_id'] for r in rows})
        for producto_id in producto_ids:
            _recostear_producto(conn, negocio_id, producto_id)

        conn.commit()
        return jsonify({
            'ok': True,
            'productos_recosteados': len(producto_ids),
            'movimientos_actualizados': len(rows),
            'fecha': nueva_fecha.isoformat(),
            'hora': hora_uso.strftime('%H:%M')
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


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
                SELECT comprobante_id AS id, 
                       CASE WHEN tipo_documento IS NOT NULL AND tipo_documento <> '' AND POSITION('-' IN numero_documento) = 0 THEN tipo_documento || '-' || numero_documento ELSE numero_documento END AS numero_comprobante,
                       tipo_documento AS tipo, 
                       SUM(CASE WHEN tipo = 'debito' THEN monto ELSE 0 END) AS total_debitos, 
                       MAX(descripcion_general) AS descripcion, 
                       fecha
                FROM movimientos_contables
                WHERE negocio_id = %s AND origen_tipo = %s AND origen_id = %s
                GROUP BY comprobante_id, numero_documento, tipo_documento, fecha
                LIMIT 1
            """, (negocio_id, origen_tipo, origen_id)).fetchone()
            if comp_row:
                comprobante = dict(comp_row)
                comprobante['total_debitos'] = float(comprobante['total_debitos'])

        if not comprobante and mov['tipo_documento'] and mov['documento_numero']:
            comp_row = conn.execute("""
                SELECT comprobante_id AS id, 
                       CASE WHEN tipo_documento IS NOT NULL AND tipo_documento <> '' AND POSITION('-' IN numero_documento) = 0 THEN tipo_documento || '-' || numero_documento ELSE numero_documento END AS numero_comprobante,
                       tipo_documento AS tipo, 
                       SUM(CASE WHEN tipo = 'debito' THEN monto ELSE 0 END) AS total_debitos, 
                       MAX(descripcion_general) AS descripcion, 
                       fecha
                FROM movimientos_contables
                WHERE negocio_id = %s AND tipo_documento = 'COMPRA' AND fecha = %s::date
                GROUP BY comprobante_id, numero_documento, tipo_documento, fecha
                HAVING ABS(SUM(CASE WHEN tipo = 'debito' THEN monto ELSE 0 END) - %s) < 0.05
                LIMIT 1
            """, (negocio_id, mov['created_at'].date(), float(mov['documento_total'] or 0))).fetchone()
            if comp_row:
                comprobante = dict(comp_row)
                comprobante['total_debitos'] = float(comprobante['total_debitos'])

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
                    SELECT DISTINCT comprobante_id AS id FROM movimientos_contables
                    WHERE negocio_id = %s AND origen_tipo = %s AND origen_id = %s
                """, (negocio_id, origen_tipo, origen_id)).fetchone()
                if comp_row:
                    comprobantes_a_borrar.append(comp_row['id'])

            if not comprobantes_a_borrar and mov['tipo_documento'] and mov['documento_numero']:
                comp_row = conn.execute("""
                    SELECT comprobante_id AS id
                    FROM movimientos_contables
                    WHERE negocio_id = %s AND tipo_documento = 'COMPRA' AND fecha = %s::date
                    GROUP BY comprobante_id
                    HAVING ABS(SUM(CASE WHEN tipo = 'debito' THEN monto ELSE 0 END) - %s) < 0.05
                """, (negocio_id, mov['created_at'].date(), float(mov['documento_total'] or 0))).fetchone()
                if comp_row:
                    comprobantes_a_borrar.append(comp_row['id'])

        else:
            movimientos_a_borrar.append(mov['id'])
            productos_a_recostear.add(mov['producto_id'])

        for comp_id in comprobantes_a_borrar:
            conn.execute("DELETE FROM movimientos_contables WHERE comprobante_id = %s", (comp_id,))

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


@bp.route('/api/inventario/<int:negocio_id>/productos/buscar')
def api_buscar_productos_inventario(negocio_id):
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'ok': True, 'productos': []})
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, nombre, COALESCE(costo, 0) AS costo, COALESCE(precio, 0) AS precio
            FROM productos
            WHERE negocio_id = %s AND disponible = TRUE AND nombre ILIKE %s
            ORDER BY nombre
            LIMIT 50
        """, (negocio_id, f'%{q}%')).fetchall()
        return jsonify({'ok': True, 'productos': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
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
        # Mapeo de tipos de documentos del negocio
        types_rows = conn.execute("SELECT id, nombre, codigo FROM tipos_documento_negocio WHERE negocio_id = %s", (negocio_id,)).fetchall()
        types_map = {r['id']: r['nombre'] for r in types_rows}
        types_code = {r['id']: r['codigo'] for r in types_rows}

        # Query unique documents in movimientos_inventario (purchases/entries)
        rows_inv = conn.execute("""
            SELECT mi.tipo_documento_id, mi.tipo_documento, mi.documento_numero, mi.documento_fecha, SUM(mi.valor_total) AS total,
                   MIN(sd.saldo) AS saldo_pendiente
            FROM movimientos_inventario mi
            LEFT JOIN saldo_por_documentos sd ON sd.negocio_id = mi.negocio_id 
                                            AND sd.tercero_id = mi.proveedor_id
                                            AND sd.tipo_documento = mi.tipo_documento
                                            AND sd.numero_documento = mi.documento_numero
            WHERE mi.negocio_id = %s AND mi.proveedor_id = %s
            GROUP BY mi.tipo_documento_id, mi.tipo_documento, mi.documento_numero, mi.documento_fecha
            ORDER BY mi.documento_fecha DESC, mi.documento_numero DESC
        """, (negocio_id, tercero_id)).fetchall()
        
        documentos = []
        for r in rows_inv:
            td_id = r['tipo_documento_id']
            td_name = r['tipo_documento'] or 'otro'
            if td_id and td_id in types_map:
                td_name = types_map[td_id]
            doc_num = r['documento_numero']
            documentos.append({
                'tipo_documento_id': td_id,
                'tipo_documento': td_name,
                'documento_numero': _num_documento_limpio(doc_num, td_id, types_code),
                'documento_numero_completo': doc_num,
                'fecha': r['documento_fecha'].isoformat() if r['documento_fecha'] else None,
                'origen': 'inventario',
                'total': float(r['total'] or 0),
                'saldo_pendiente': float(r['saldo_pendiente']) if r['saldo_pendiente'] is not None else None
            })
            
        # Query documents in pedidos (sales/orders) — solo ventas facturadas (con tipo de documento)
        rows_ped = conn.execute("""
            SELECT id, tipo_documento_id, numero_documento, fecha, created_at, total, estado
            FROM pedidos
            WHERE (cliente_id = %s OR id_tercero = %s)
              AND tipo_documento_id IS NOT NULL
            ORDER BY COALESCE(fecha, created_at) DESC, id DESC
        """, (tercero_id, tercero_id)).fetchall()
        
        for r in rows_ped:
            doc_num = r['numero_documento'] or str(r['id'])
            # Fallback to created_at if fecha is null
            f_val = r['fecha'] or r['created_at']
            td_id = r['tipo_documento_id']
            td_name = types_map.get(td_id) if td_id else 'pedido_venta'
            documentos.append({
                'tipo_documento_id': td_id,
                'tipo_documento': td_name,
                'documento_numero': _num_documento_limpio(doc_num, td_id, types_code),
                'documento_numero_completo': doc_num,
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


def _num_documento_limpio(num_str, tipo_doc_id, types_code):
    """Devuelve el número de documento sin el prefijo del código del tipo y sin ceros a la izquierda si es numérico."""
    if not num_str:
        return num_str
    s = str(num_str).strip()
    cod = types_code.get(tipo_doc_id)
    if cod and s.upper().startswith(str(cod).upper() + '-'):
        s = s[len(str(cod)) + 1:].strip()
    if '-' in s:
        parts = s.split('-')
        suffix = parts[-1].strip()
        if suffix.isdigit():
            return str(int(suffix))
    elif s.isdigit():
        return str(int(s))
    return s


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
        types_code = {r['id']: r['codigo'] for r in types_rows}

        # 1. Fetch recent inventory documents
        sql_inv = """
            SELECT mi.tipo_documento_id, mi.tipo_documento, mi.documento_numero, mi.documento_fecha, SUM(mi.valor_total) AS total_inventario,
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
            
            pure_num = _num_documento_limpio(doc_num, td_id, types_code)
            
            td_name = r['tipo_documento'] or 'otro'
            if td_id and td_id in types_map:
                td_name = types_map[td_id]
                
            key = (td_id, pure_num) if td_id else (td_name.lower(), pure_num)
            
            consolidated[key] = {
                'tipo_documento_id': td_id,
                'tipo_documento': td_name,
                'documento_numero': _num_documento_limpio(doc_num, td_id, types_code),
                'documento_numero_completo': doc_num,
                'fecha': r['documento_fecha'].isoformat() if r['documento_fecha'] else None,
                'origen': 'inventario',
                'total_inventario': float(r['total_inventario'] or 0),
                'total_contable': None,
                'total_pedidos': None,
                'tercero_nombre': r['proveedor_nombre'] or '—',
                'tercero_id': r['proveedor_id']
            }
            
        # 2. Fetch recent orders (sales) — solo pedidos convertidos en venta facturada (con tipo de documento)
        sql_ped = """
            SELECT p.id, p.tipo_documento_id, p.numero_documento, p.fecha, p.created_at, p.total, p.cliente_id, p.id_tercero, p.nombre_cliente, p.estado
            FROM pedidos p
            WHERE p.negocio_id = %s AND p.tipo_documento_id IS NOT NULL
        """
        params_ped = [negocio_id]
        
        if q:
            sql_ped += " AND (p.numero_documento ILIKE %s OR p.nombre_cliente ILIKE %s)"
            params_ped.extend([f'%{q}%', f'%{q}%'])
            
        if tipo and tipo != 'todos':
            if tipo == 'pedido_venta':
                sql_ped += " AND p.tipo_documento_id IN (SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND tipo_movimiento = 'venta')"
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
            pure_num = _num_documento_limpio(doc_num, td_id, types_code)
            
            td_name = 'pedido_venta'
            if td_id and td_id in types_map:
                td_name = types_map[td_id]
                
            key = (td_id, pure_num) if td_id else (td_name.lower(), pure_num)
            f_val = r['fecha'] or r['created_at']
            # Normalizar fecha a YYYY-MM-DD para consistencia en consolidado
            date_str = f_val.strftime('%Y-%m-%d') if f_val else None
            
            # Consolidación: si ya existe el documento por inventario, unificar
            if key in consolidated:
                consolidated[key]['origen'] = 'ambos'
                if not consolidated[key]['tercero_id'] and c_id:
                    consolidated[key]['tercero_id'] = c_id
                    consolidated[key]['tercero_nombre'] = c_name or 'Cliente general'
                if r['total'] and float(r['total']) > (consolidated[key]['total_pedidos'] or 0):
                    consolidated[key]['total_pedidos'] = float(r['total'])
                # Prefer showing original prefix code if existing display name is shorter
                if doc_num and len(doc_num) > len(consolidated[key].get('documento_numero_completo') or ''):
                    consolidated[key]['documento_numero_completo'] = doc_num
            else:
                consolidated[key] = {
                    'tipo_documento_id': td_id,
                    'tipo_documento': td_name,
                    'documento_numero': _num_documento_limpio(doc_num, td_id, types_code),
                    'documento_numero_completo': doc_num,
                    'fecha': date_str,
                    'origen': 'ventas',
                    'total_inventario': None,
                    'total_contable': None,
                    'total_pedidos': float(r['total'] or 0),
                    'tercero_nombre': c_name or 'Cliente general',
                    'tercero_id': c_id,
                    'estado': r['estado']
                }
            
        # 3. Fetch accounting totals for the source documents.
        sql_cont = """
            SELECT mc.tipo_documento_id, mc.numero_documento AS documento_numero,
                   SUM(CASE WHEN mc.tipo IN ('debito', 'D', 'deb') THEN mc.monto ELSE 0 END) AS total_contable,
                   MIN(mc.tercero_id) AS proveedor_id,
                   MIN(mc.fecha) AS documento_fecha
            FROM movimientos_contables mc
            WHERE mc.negocio_id = %s
        """
        params_cont = [negocio_id]
        
        if q:
            sql_cont += """ AND (
                mc.numero_documento ILIKE %s 
                OR mc.tipo_documento ILIKE %s 
                OR mc.concepto ILIKE %s 
                OR mc.tercero_id IN (SELECT id FROM terceros WHERE nombre ILIKE %s)
            )"""
            params_cont.extend([f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%'])
            
        if tipo and tipo != 'todos':
            if tipo == 'pedido_venta':
                sql_cont += " AND LOWER(mc.tipo_documento) IN ('factura', 'factura_de_venta', 'venta')"
            else:
                try:
                    tipo_id = int(tipo)
                    sql_cont += " AND (mc.tipo_documento_id = %s OR mc.tipo_documento IN (SELECT codigo FROM tipos_documento_negocio WHERE id = %s))"
                    params_cont.extend([tipo_id, tipo_id])
                except ValueError:
                    sql_cont += " AND (LOWER(mc.tipo_documento) = LOWER(%s) OR mc.tipo_documento_id IN (SELECT id FROM tipos_documento_negocio WHERE negocio_id = %s AND LOWER(codigo) = LOWER(%s)))"
                    params_cont.extend([tipo, negocio_id, tipo])
                    
        if desde:
            sql_cont += " AND mc.fecha >= %s"
            params_cont.append(desde)
        if hasta:
            sql_cont += " AND mc.fecha <= %s"
            params_cont.append(hasta)
            
        sql_cont += """
            GROUP BY mc.tipo_documento_id, mc.numero_documento
            ORDER BY MIN(mc.fecha) DESC, mc.numero_documento DESC
            LIMIT 1000
        """
        
        rows_cont = conn.execute(sql_cont, tuple(params_cont)).fetchall()
        
        for r in rows_cont:
            td_id = r['tipo_documento_id']
            
            doc_num = r['documento_numero']
            pure_num = _num_documento_limpio(doc_num, td_id, types_code)
            
            td_name = types_map.get(td_id) if td_id else 'comprobante'
                
            key = (td_id, pure_num) if td_id else ('comprobante', pure_num)
            
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
                # El total contable se completa desde el asiento, sin reemplazar inventario/pedidos
                consolidated[key]['total_contable'] = float(r['total_contable'] or 0)
            else:
                consolidated[key] = {
                    'tipo_documento_id': td_id,
                    'tipo_documento': td_name,
                    'documento_numero': _num_documento_limpio(doc_num, td_id, types_code),
                    'documento_numero_completo': doc_num,
                    'fecha': date_str,
                    'origen': 'contabilidad',
                    'total_inventario': None,
                    'total_contable': float(r['total_contable'] or 0),
                    'total_pedidos': None,
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
        
    # Si es puramente numérico, agregar variantes con ceros a la izquierda
    if num_str_clean.isdigit():
        val_num = int(num_str_clean)
        for length in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            v_padded = f"{val_num:0{length}d}"
            if v_padded not in variantes:
                variantes.append(v_padded)
                
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
                
            # Agregar variantes con ceros a la izquierda para el sufijo y el prefijo-sufijo
            for length in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
                v_padded_suffix = f"{val_num:0{length}d}"
                v_padded = f"{prefix}-{v_padded_suffix}"
                if v_padded not in variantes:
                    variantes.append(v_padded)
                if v_padded_suffix not in variantes:
                    variantes.append(v_padded_suffix)
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
        tipo_doc_codigo = None
        tipo_doc_nombre = None
        current_consecutivo = None
        es_interno = False
        tipo_movimiento = None
        try:
            tipo_documento_id = int(tipo_doc)
            td_row = conn.execute("SELECT id, codigo, nombre, consecutivo, es_interno, tipo_movimiento FROM tipos_documento_negocio WHERE id = %s", (tipo_documento_id,)).fetchone()
            if td_row:
                tipo_doc_codigo = td_row['codigo']
                tipo_doc_nombre = td_row['nombre']
                current_consecutivo = td_row['consecutivo']
                es_interno = bool(td_row['es_interno'])
                tipo_movimiento = td_row['tipo_movimiento']
        except ValueError:
            row_td = conn.execute("""
                SELECT id, codigo, nombre, consecutivo, es_interno, tipo_movimiento FROM tipos_documento_negocio 
                WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))
            """, (negocio_id, tipo_doc, tipo_doc)).fetchone()
            
            # Fallback for placeholder sales types (like 'pedido_venta', 'ventas', 'pedido')
            if not row_td and tipo_doc.lower() in ('pedido_venta', 'ventas', 'pedido'):
                row_td = conn.execute("""
                    SELECT id, codigo, nombre, consecutivo, es_interno, tipo_movimiento FROM tipos_documento_negocio 
                    WHERE negocio_id = %s AND tipo_movimiento = 'venta' AND activo = TRUE
                    ORDER BY predeterminado DESC, id LIMIT 1
                """, (negocio_id,)).fetchone()
                
            if row_td:
                tipo_documento_id = row_td['id']
                tipo_doc_codigo = row_td['codigo']
                tipo_doc_nombre = row_td['nombre']
                current_consecutivo = row_td['consecutivo']
                es_interno = bool(row_td['es_interno'])
                tipo_movimiento = row_td['tipo_movimiento']

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
        
        # Build list of possible string representations of the invoice/consecutive
        doc_codes = list(num_variants)
        if tipo_doc_codigo:
            for v in num_variants:
                doc_codes.append(f"{tipo_doc_codigo}-{v}")
                doc_codes.append(f"{tipo_doc_codigo.upper()}-{v}")
                doc_codes.append(f"{tipo_doc_codigo.lower()}-{v}")
        if tipo_doc_nombre:
            for v in num_variants:
                doc_codes.append(f"{tipo_doc_nombre}-{v}")
                doc_codes.append(f"{tipo_doc_nombre.upper()}-{v}")
                doc_codes.append(f"{tipo_doc_nombre.lower()}-{v}")
        doc_codes = list(set([d.lower() for d in doc_codes]))

        pedido_row = conn.execute("""
            SELECT * FROM pedidos
            WHERE negocio_id = %s 
              AND (
                LOWER(numero_documento) IN %s
                OR (numero_documento IS NOT NULL AND LOWER(numero_documento) IN %s)
              )
            LIMIT 1
        """, (negocio_id, tuple(doc_codes), tuple(doc_codes))).fetchone()


        if pedido_row and not tipo_documento_id:
            tipo_documento_id = pedido_row['tipo_documento_id']

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
        
        # 2. Query movimientos_contables to find the grouped voucher
        tipo_variants = [tipo_doc.lower(), tipo_doc.lower().replace(' ', '_'), tipo_doc.lower().replace('_', ' ')]
        if tipo_doc_codigo:
            tipo_variants.append(tipo_doc_codigo.lower())
            tipo_variants.append(tipo_doc_codigo.lower().replace(' ', '_'))
            tipo_variants.append(tipo_doc_codigo.lower().replace('_', ' '))
        if tipo_doc_nombre:
            tipo_variants.append(tipo_doc_nombre.lower())
            tipo_variants.append(tipo_doc_nombre.lower().replace(' ', '_'))
            tipo_variants.append(tipo_doc_nombre.lower().replace('_', ' '))
            
        tipo_variants = list(set(tipo_variants))
        pedido_id_str = str(pedido_row['id']) if pedido_row else None
        
        comp_row = conn.execute("""
            SELECT comprobante_id AS id, 
                   CASE WHEN tipo_documento IS NOT NULL AND tipo_documento <> '' AND POSITION('-' IN numero_documento) = 0 THEN tipo_documento || '-' || numero_documento ELSE numero_documento END AS numero_comprobante,
                   tipo_documento AS tipo, 
                   fecha, 
                   MAX(descripcion_general) AS descripcion, 
                   SUM(CASE WHEN tipo IN ('debito', 'D') THEN monto ELSE 0 END) AS total_debitos, 
                   SUM(CASE WHEN tipo IN ('credito', 'C') THEN monto ELSE 0 END) AS total_creditos,
                   '' AS notas
            FROM movimientos_contables
            WHERE negocio_id = %s 
              AND (
                tipo_documento_id = %s 
                OR LOWER(tipo_documento) IN %s
              )
              AND (
                numero_documento IN %s 
                OR numero_documento = %s
                OR (origen_tipo = 'pedido' AND origen_id = %s)
              )
            GROUP BY comprobante_id, numero_documento, tipo_documento, fecha
            LIMIT 1
        """, (negocio_id, tipo_documento_id, tuple(tipo_variants), tuple(num_variants), num_doc, pedido_id_str)).fetchone()
            
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
                    'tipo': 'D' if str(e['tipo']).strip().lower() in ('debito', 'd') else 'C',
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
        
        # Determine if it is the latest consecutive document of this type
        es_ultimo_consecutivo = False
        if current_consecutivo is not None:
            def extraer_consecutivo_num(n_str):
                if not n_str:
                    return None
                n_str = str(n_str).strip()
                if '-' in n_str:
                    n_str = n_str.split('-')[-1].strip()
                try:
                    return int(n_str)
                except ValueError:
                    return None
            doc_num_int = extraer_consecutivo_num(num_doc)
            if doc_num_int is not None and current_consecutivo == doc_num_int:
                es_ultimo_consecutivo = True
                
        return jsonify({
            'ok': True,
            'existe': bool(items_inventario or comprobante or pedido),
            'inventario': items_inventario,
            'contabilidad': comprobante,
            'ventas': pedido,
            'saldo_pendiente': saldo_pendiente,
            'monto_original': monto_original,
            'es_ultimo_consecutivo': es_ultimo_consecutivo,
            'es_interno': es_interno,
            'tipo_movimiento': tipo_movimiento
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
        
        # Resolve document number variants
        num_variants = resolver_variantes_numero(num_doc)
        
        # Resolve type code
        row_td = conn.execute("""
            SELECT id, codigo, nombre, consecutivo, es_interno FROM tipos_documento_negocio 
            WHERE negocio_id = %s AND (LOWER(codigo) = LOWER(%s) OR LOWER(nombre) = LOWER(%s))
        """, (negocio_id, tipo_doc, tipo_doc)).fetchone()
        
        if not row_td and tipo_doc.lower() in ('pedido_venta', 'ventas', 'pedido'):
            row_td = conn.execute("""
                SELECT id, codigo, nombre, consecutivo, es_interno FROM tipos_documento_negocio 
                WHERE negocio_id = %s AND tipo_movimiento = 'venta' AND activo = TRUE
                ORDER BY predeterminado DESC, id LIMIT 1
            """, (negocio_id,)).fetchone()
            
        tipo_code = row_td['codigo'] if row_td else None
        
        # Build list of possible string representations of the invoice/consecutive
        doc_codes = list(num_variants)
        if tipo_code:
            for v in num_variants:
                doc_codes.append(f"{tipo_code}-{v}")
                doc_codes.append(f"{tipo_code.upper()}-{v}")
                doc_codes.append(f"{tipo_code.lower()}-{v}")
        doc_codes = list(set([d.lower() for d in doc_codes]))

        # Look up the order in `pedidos` if it exists
        pedido_row = conn.execute("""
            SELECT * FROM pedidos
            WHERE negocio_id = %s 
              AND (
                LOWER(numero_documento) IN %s
                OR (numero_documento IS NOT NULL AND LOWER(numero_documento) IN %s)
              )
            LIMIT 1
        """, (negocio_id, tuple(doc_codes), tuple(doc_codes))).fetchone()

        if not pedido_row:
            try:
                pedido_id_val = int(num_doc)
                pedido_row = conn.execute("SELECT * FROM pedidos WHERE id = %s AND negocio_id = %s LIMIT 1", (pedido_id_val, negocio_id)).fetchone()
            except ValueError:
                pass
        
        # Get inventory movement IDs to be deleted, and their product IDs (for recosteo!)
        if pedido_row:
            sql_inv = """
                SELECT id, producto_id, proveedor_id
                FROM movimientos_inventario
                WHERE negocio_id = %s AND (
                    (referencia_tipo IN ('pedido', 'pedido_tienda', 'pedido_restaurante') AND referencia_id = %s)
                    OR (LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) IN %s)
                    OR (LOWER(documento_numero) IN %s)
                )
            """
            params_inv = [negocio_id, pedido_row['id'], tipo_doc, tuple(doc_codes), tuple(doc_codes)]
        else:
            sql_inv = """
                SELECT id, producto_id, proveedor_id
                FROM movimientos_inventario
                WHERE negocio_id = %s AND (
                    (LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) IN %s)
                    OR (LOWER(documento_numero) IN %s)
                )
            """
            params_inv = [negocio_id, tipo_doc, tuple(doc_codes), tuple(doc_codes)]
        
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
                    OR LOWER(numero_documento) IN %s
                ) AND LOWER(numero_documento) IN %s
            """, (negocio_id, p_id, tipo_doc, pedido_row['tipo_documento_id'] if pedido_row else None, tuple(doc_codes), tuple(doc_codes)))
        else:
            conn.execute("""
                DELETE FROM saldo_por_documentos
                WHERE negocio_id = %s AND (tipo_documento = %s OR LOWER(tipo_documento) = LOWER(%s)) AND LOWER(numero_documento) IN %s
            """, (negocio_id, tipo_doc, tipo_doc, tuple(doc_codes)))

        # Delete purchase cotizaciones generated by this entry
        if p_id:
            conn.execute("""
                DELETE FROM cotizaciones_compras
                WHERE negocio_id = %s AND tercero_id = %s AND LOWER(numero_cotizacion) IN %s AND origen = 'compra'
            """, (negocio_id, p_id, tuple(doc_codes)))
        
        # Delete accounting vouchers & entries
        origen_id_str = f"{tipo_doc}:{num_doc}"
        pedido_id_str = str(pedido_row['id']) if pedido_row else None
        
        # Delete directly from movimientos_contables using flat metadata
        cur_mc = conn.execute("""
            DELETE FROM movimientos_contables
            WHERE negocio_id = %s AND (
                (origen_tipo = 'pedido' AND origen_id = %s)
                OR (origen_tipo IS NOT NULL AND LOWER(origen_id) = LOWER(%s))
                OR (LOWER(numero_documento) IN %s)
            )
        """, (negocio_id, pedido_id_str, origen_id_str, tuple(doc_codes)))
        deleted_contables = cur_mc.rowcount
        deleted_comprobantes = 0
            
        # Action handler: 'anular' (default) vs 'eliminar'
        accion = _txt(data.get('accion') or 'anular').lower()
        pedido_eliminado = False
        pedido_anulado = False
        consecutivo_liberado = False
        
        # Unified consecutive release logic (runs for both orders and flat documents)
        if row_td and accion == 'eliminar':
            # Extract pure numeric consecutive from the document string
            def extraer_consecutivo_num(n_str):
                if not n_str:
                    return None
                n_str = str(n_str).strip()
                if '-' in n_str:
                    n_str = n_str.split('-')[-1].strip()
                try:
                    return int(n_str)
                except ValueError:
                    return None
            
            doc_num_int = extraer_consecutivo_num(num_doc)
            if doc_num_int is not None:
                # Retrieve current sequence value for this document type
                td_curr = conn.execute("SELECT id, consecutivo FROM tipos_documento_negocio WHERE id = %s", (row_td['id'],)).fetchone()
                # Rollback sequence ONLY if it is exactly the one being deleted (no newer documents exist)
                if td_curr and td_curr['consecutivo'] == doc_num_int:
                    new_con = max(0, td_curr['consecutivo'] - 1)
                    conn.execute("UPDATE tipos_documento_negocio SET consecutivo = %s WHERE id = %s", (new_con, td_curr['id']))
                    consecutivo_liberado = True
                    
        if pedido_row:
            if accion == 'eliminar':
                # Delete completely from orders tables
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
        p_row = conn.execute("SELECT id, nombre, telefono FROM terceros WHERE id = %s", (principal_id,)).fetchone()
        if not p_row:
            conn.close()
            return jsonify({'ok': False, 'error': 'El tercero principal no existe'}), 400
            
        # Verify sobrantes exist
        placeholders = ', '.join(['%s'] * len(sobrantes_ids))
        s_rows = conn.execute(f"SELECT id, nombre, telefono, tipo_tercero FROM terceros WHERE id IN ({placeholders})", tuple(sobrantes_ids)).fetchall()
        if len(s_rows) != len(sobrantes_ids):
            conn.close()
            return jsonify({'ok': False, 'error': 'Uno o más terceros sobrantes no existen'}), 400
            
        # Validaciones de seguridad para no eliminar terceros administradores/plenipotenciarios
        for s in s_rows:
            if s['tipo_tercero'] == 'admin':
                conn.close()
                return jsonify({
                    'ok': False, 
                    'error': f"Seguridad: No se permite eliminar al tercero '{s['nombre']}' porque es de tipo 'admin' (usuario plenipotenciario/activo del sistema). Establézcalo como el Tercero Principal si desea unificar sus duplicados."
                }), 400
            
        # Start transaction to merge
        principal_nombre = p_row['nombre']
        
        # Obtener el teléfono definido por el usuario o conservar el del principal
        telefono_definido = data.get('telefono_definido')
        if telefono_definido:
            conn.execute("UPDATE terceros SET telefono = %s WHERE id = %s", (telefono_definido, principal_id))
            principal_telefono = telefono_definido
        else:
            principal_telefono = p_row['telefono']
            # Fallback automático si no se definió y el principal no lo tiene
            if not principal_telefono:
                phone_row = conn.execute(f"SELECT telefono FROM terceros WHERE id IN ({placeholders}) AND telefono IS NOT NULL AND telefono != '' LIMIT 1", tuple(sobrantes_ids)).fetchone()
                if phone_row:
                    conn.execute("UPDATE terceros SET telefono = %s WHERE id = %s", (phone_row['telefono'], principal_id))
                    principal_telefono = phone_row['telefono']
        
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
                id_tercero_cajero = CASE WHEN id_tercero_cajero IN ({placeholders}) THEN %s ELSE id_tercero_cajero END,
                nombre_cliente = CASE WHEN (cliente_id IN ({placeholders}) OR id_tercero IN ({placeholders})) THEN %s ELSE nombre_cliente END
        """, tuple(sobrantes_ids) + (principal_id,) + 
             tuple(sobrantes_ids) + (principal_id,) + 
             tuple(sobrantes_ids) + (principal_id,) + 
             tuple(sobrantes_ids) + tuple(sobrantes_ids) + (principal_nombre,))
        
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
            
        # 8b. Unificar y registrar todos los teléfonos únicos en terceros_telefonos
        # Mapear los registros de terceros_telefonos de los sobrantes hacia el principal
        conn.execute(f"""
            UPDATE terceros_telefonos 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # Registrar números alternativos únicos detectados
        todos_los_telefonos = set()
        if principal_telefono:
            todos_los_telefonos.add(principal_telefono.strip())
        if p_row.get('telefono'):
            todos_los_telefonos.add(p_row['telefono'].strip())
        for s in s_rows:
            if s.get('telefono'):
                todos_los_telefonos.add(s['telefono'].strip())
                
        for tel in todos_los_telefonos:
            if tel:
                existe = conn.execute("SELECT 1 FROM terceros_telefonos WHERE tercero_id = %s AND telefono = %s", (principal_id, tel)).fetchone()
                if not existe:
                    conn.execute("INSERT INTO terceros_telefonos (tercero_id, telefono) VALUES (%s, %s)", (principal_id, tel))
            
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


# ── COTIZACIONES DE COMPRA POR PRESENTACIÓN ───────────────────────────────────

@bp.route('/api/inventario/<int:negocio_id>/cotizaciones')
def api_cotizaciones_listar(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        buscar = (request.args.get('q') or '').strip()
        query = """
            SELECT c.id, c.numero_cotizacion, c.tercero_id, t.nombre AS proveedor_nombre,
                   t.telefono AS proveedor_telefono, c.item_id, p.nombre AS producto_nombre,
                   c.presentacion_id, pr.nombre AS presentacion_nombre, pr.equivalencia,
                   c.unidades_item, c.precio, c.descripcion_presentacion,
                   c.fecha_cotizacion, c.fecha_vencimiento, c.origen,
                   c.validada_proveedor, c.observaciones, c.created_at, c.negocio_id,
                   CASE WHEN c.fecha_vencimiento >= CURRENT_DATE THEN TRUE ELSE FALSE END AS vigente
            FROM cotizaciones_compras c
            JOIN terceros t ON t.id = c.tercero_id
            JOIN productos p ON p.id = c.item_id
            LEFT JOIN presentaciones pr ON pr.id = c.presentacion_id
            WHERE p.id IN (SELECT id FROM productos WHERE negocio_id = %s AND disponible = TRUE)
        """
        params = [negocio_id]
        if buscar:
            query += " AND (p.nombre ILIKE %s OR t.nombre ILIKE %s OR pr.nombre ILIKE %s)"
            like = f"%{buscar}%"
            params.extend([like, like, like])
        query += " ORDER BY p.nombre, t.nombre, c.precio ASC"
        rows = conn.execute(query, params).fetchall()
        return jsonify({'ok': True, 'cotizaciones': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/cotizaciones', methods=['POST'])
def api_cotizaciones_crear(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    tercero_id = _int_o_none(data.get('tercero_id'))
    item_id = _int_o_none(data.get('item_id'))
    presentacion_id = _int_o_none(data.get('presentacion_id'))
    precio = data.get('precio')
    unidades_item = data.get('unidades_item', 1)
    descripcion = (data.get('descripcion_presentacion') or '').strip()
    observaciones = (data.get('observaciones') or '').strip()
    fecha_vencimiento = data.get('fecha_vencimiento')
    
    if not tercero_id or not item_id or precio is None:
        return jsonify({'ok': False, 'error': 'Proveedor, producto y precio son requeridos'}), 400
    
    conn = get_db_connection()
    try:
        # Resolver presentación
        if not presentacion_id and descripcion:
            pres = conn.execute("SELECT id FROM presentaciones WHERE LOWER(nombre) = LOWER(%s) LIMIT 1", (descripcion,)).fetchone()
            if pres:
                presentacion_id = pres['id']
        
        # Calcular unidades_item desde presentación
        if presentacion_id and (not unidades_item or float(unidades_item) <= 1):
            pr = conn.execute("SELECT equivalencia FROM presentaciones WHERE id = %s", (presentacion_id,)).fetchone()
            if pr:
                unidades_item = float(pr['equivalencia'])
                if not descripcion:
                    pr_name = conn.execute("SELECT nombre FROM presentaciones WHERE id = %s", (presentacion_id,)).fetchone()
                    descripcion = pr_name['nombre'] if pr_name else ''
        
        # Verificar duplicado
        existing = conn.execute("""
            SELECT id FROM cotizaciones_compras
            WHERE negocio_id = %s AND tercero_id = %s AND item_id = %s 
              AND (presentacion_id = %s OR (presentacion_id IS NULL AND %s IS NULL))
        """, (negocio_id, tercero_id, item_id, presentacion_id, presentacion_id)).fetchone()
        
        f_vence = fecha_vencimiento or (date.today() + timedelta(days=180))
        
        if existing:
            conn.execute("""
                UPDATE cotizaciones_compras
                SET precio = %s, unidades_item = %s, descripcion_presentacion = %s,
                    observaciones = %s, fecha_vencimiento = %s, updated_at = NOW()
                WHERE id = %s
            """, (float(precio), float(unidades_item), descripcion, observaciones, f_vence, existing['id']))
            cot_id = existing['id']
        else:
            row = conn.execute("""
                INSERT INTO cotizaciones_compras
                    (negocio_id, tercero_id, item_id, presentacion_id, precio,
                     unidades_item, descripcion_presentacion, observaciones,
                     fecha_cotizacion, fecha_vencimiento, origen, validada_proveedor, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, 'manual', TRUE, NOW())
                RETURNING id
            """, (negocio_id, tercero_id, item_id, presentacion_id, float(precio),
                  float(unidades_item), descripcion, observaciones, f_vence)).fetchone()
            cot_id = row['id']
        
        conn.commit()
        return jsonify({'ok': True, 'id': cot_id, 'mensaje': 'Cotización guardada'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/cotizaciones/<int:cot_id>', methods=['PUT'])
def api_cotizaciones_actualizar(negocio_id, cot_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT id FROM cotizaciones_compras WHERE id = %s AND negocio_id = %s", (cot_id, negocio_id)).fetchone()
        if not existing:
            return jsonify({'ok': False, 'error': 'Cotización no encontrada'}), 404
        
        updates = []
        params = []
        if 'precio' in data:
            updates.append("precio = %s")
            params.append(float(data['precio']))
        if 'unidades_item' in data:
            updates.append("unidades_item = %s")
            params.append(float(data['unidades_item']))
        if 'descripcion_presentacion' in data:
            updates.append("descripcion_presentacion = %s")
            params.append(data['descripcion_presentacion'])
        if 'observaciones' in data:
            updates.append("observaciones = %s")
            params.append(data['observaciones'])
        if 'fecha_vencimiento' in data:
            updates.append("fecha_vencimiento = %s")
            params.append(data['fecha_vencimiento'])
        if 'presentacion_id' in data:
            updates.append("presentacion_id = %s")
            params.append(_int_o_none(data['presentacion_id']))
        if 'validada_proveedor' in data:
            updates.append("validada_proveedor = %s")
            params.append(data['validada_proveedor'])
        
        if not updates:
            return jsonify({'ok': False, 'error': 'Nada que actualizar'}), 400
        
        updates.append("updated_at = NOW()")
        params.extend([cot_id, negocio_id])
        conn.execute(f"UPDATE cotizaciones_compras SET {', '.join(updates)} WHERE id = %s AND negocio_id = %s", params)
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Cotización actualizada'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/cotizaciones/<int:cot_id>', methods=['DELETE'])
def api_cotizaciones_eliminar(negocio_id, cot_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM cotizaciones_compras WHERE id = %s AND negocio_id = %s", (cot_id, negocio_id))
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Cotización eliminada'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/cotizaciones/resumen')
def api_cotizaciones_resumen(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM cotizaciones_compras WHERE item_id IN (SELECT id FROM productos WHERE negocio_id = %s AND disponible = TRUE)", (negocio_id,)).fetchone()['n']
        vigentes = conn.execute("SELECT COUNT(*) AS n FROM cotizaciones_compras WHERE item_id IN (SELECT id FROM productos WHERE negocio_id = %s AND disponible = TRUE) AND fecha_vencimiento >= CURRENT_DATE", (negocio_id,)).fetchone()['n']
        vencidas = total - vigentes
        productos = conn.execute("SELECT COUNT(DISTINCT item_id) AS n FROM cotizaciones_compras WHERE item_id IN (SELECT id FROM productos WHERE negocio_id = %s AND disponible = TRUE)", (negocio_id,)).fetchone()['n']
        proveedores = conn.execute("SELECT COUNT(DISTINCT tercero_id) AS n FROM cotizaciones_compras WHERE item_id IN (SELECT id FROM productos WHERE negocio_id = %s AND disponible = TRUE)", (negocio_id,)).fetchone()['n']
        return jsonify({'ok': True, 'total': total, 'vigentes': vigentes, 'vencidas': vencidas, 'productos': productos, 'proveedores': proveedores})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/parametros-compras')
def api_parametros_compras(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    conn = get_db_connection()
    try:
        params = {'dias_stock_max_global': 15, 'dias_entrega_global': 2, 'usar_dias_con_stock': True}
        row = conn.execute("SELECT valor_texto FROM parametros_sistema WHERE nombre = 'inventario_stock_max_dias' AND negocio_id = %s", (negocio_id,)).fetchone()
        if row and row[0]: params['dias_stock_max_global'] = int(row[0])
        row = conn.execute("SELECT valor_texto FROM parametros_sistema WHERE nombre = 'inventario_dias_entrega' AND negocio_id = %s", (negocio_id,)).fetchone()
        if row and row[0]: params['dias_entrega_global'] = int(row[0])
        row = conn.execute("SELECT valor_booleano FROM parametros_sistema WHERE nombre = 'inventario_usar_dias_con_stock' AND negocio_id = %s", (negocio_id,)).fetchone()
        if row and row[0]: params['usar_dias_con_stock'] = str(row[0]).lower() == 'true'
        return jsonify({'ok': True, 'parametros': params})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/produccion/historial')
def api_produccion_historial(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
    except (TypeError, ValueError):
        pagina = 1
    por_pagina = 50
    offset = (pagina - 1) * por_pagina
    conn = get_db_connection()
    try:
        total_row = conn.execute("""
            SELECT COUNT(*) AS total FROM movimientos_inventario
            WHERE negocio_id = %s AND tipo = 'entrada' AND referencia_tipo = 'produccion'
        """, (negocio_id,)).fetchone()
        total = total_row['total'] if total_row else 0
        rows = conn.execute("""
            SELECT m.id, m.producto_id, m.nombre_producto, m.cantidad, m.valor_unitario, m.valor_total,
                   m.documento_numero, m.tipo_documento_id, tdn.nombre AS tipo_documento_nombre, 
                   m.documento_fecha, m.created_at, m.referencia_id AS prod_token, m.notas
            FROM movimientos_inventario m
            LEFT JOIN tipos_documento_negocio tdn ON tdn.id = m.tipo_documento_id
            WHERE m.negocio_id = %s AND m.tipo = 'entrada' AND m.referencia_tipo = 'produccion'
            ORDER BY m.id DESC
            LIMIT %s OFFSET %s
        """, (negocio_id, por_pagina, offset)).fetchall()

        historial = []
        for r in rows:
            if r['documento_fecha']:
                fecha_str = r['documento_fecha'].strftime('%Y-%m-%d')
            elif r['created_at']:
                fecha_str = r['created_at'].strftime('%Y-%m-%d %H:%M')
            else:
                fecha_str = ''
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
        total_paginas = (total + por_pagina - 1) // por_pagina if total else 1
        return jsonify({
            'ok': True,
            'historial': historial,
            'pagina': pagina,
            'por_pagina': por_pagina,
            'total': total,
            'total_paginas': max(1, total_paginas)
        })
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
        
        if terminado['documento_fecha']:
            fecha_doc = terminado['documento_fecha'].strftime('%Y-%m-%d')
        elif terminado['created_at']:
            fecha_doc = terminado['created_at'].strftime('%Y-%m-%d %H:%M')
        else:
            fecha_doc = ''
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
        conn.execute("""
            DELETE FROM movimientos_contables
            WHERE negocio_id = %s AND origen_tipo = 'produccion' AND (origen_id = %s OR origen_id = %s)
        """, (negocio_id, str(prod_token), f"{prod_token}"))
            
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
            doc_num = str(int(res_num))
        except (ValueError, TypeError):
            doc_num = str(res_num)
            
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

@bp.route('/admin/inventario-distribuido/<int:negocio_id>')
def admin_inventario_distribuido(negocio_id):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto:
            return "Negocio no encontrado", 404
        if not _puede_gestionar_negocio(contexto):
            return "No autorizado para este negocio", 403
        return render_template('inventario_distribuido.html',
                               negocio_id=negocio_id,
                               negocio_nombre=contexto.get('negocio_nombre', ''))
    finally:
        conn.close()

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
        doc_num = str(next_num)
        
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
    tercero_id = _int_o_none(data.get('tercero_id'))
    tercero_nombre = data.get('tercero_nombre') or None
    
    if not tipo_documento_id or not documento_numero or not producto_id or cantidad_fisica is None or costo_unitario is None:
        return jsonify({'ok': False, 'error': 'Todos los campos son requeridos'}), 400
        
    conn = get_db_connection()
    try:
        # Normalizar documento_numero contra codigo del tipo doc
        td_raw = conn.execute("SELECT codigo FROM tipos_documento_negocio WHERE id=%s AND negocio_id=%s", (tipo_documento_id, negocio_id)).fetchone() if tipo_documento_id else None
        cod_t = (td_raw['codigo'] if td_raw and td_raw['codigo'] else 'AJUSTE_INV') or ''
        s_doc = str(documento_numero).strip()
        if s_doc.upper().startswith(str(cod_t).strip().upper() + '-'):
            documento_numero = s_doc[len(str(cod_t).strip()) + 1:].strip()
        elif s_doc.upper().startswith('AJUSTE_INV-'):
            documento_numero = s_doc[len('AJUSTE_INV'):].lstrip('-').strip()
    
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

        # 2. Verificar si existe el agrupador de movimientos en esta sesión
        tipo_doc = conn.execute("SELECT id, codigo, consecutivo, numero_inicio FROM tipos_documento_negocio WHERE id=%s AND negocio_id=%s", (tipo_documento_id, negocio_id)).fetchone()
        if not tipo_doc:
            return jsonify({'ok': False, 'error': 'Tipo de documento no válido'}), 400
            
        tipo_code = tipo_doc['codigo'] or 'AJUSTE_INV'

        comp = conn.execute("""
            SELECT DISTINCT comprobante_id AS id FROM movimientos_contables 
            WHERE negocio_id=%s AND numero_documento=%s AND tipo_documento=%s
            LIMIT 1
        """, (negocio_id, documento_numero, tipo_code)).fetchone()
        
        doc_num_final = documento_numero
        comp_id = None
        consecutivo_actualizado = False
        
        if comp:
            comp_id = comp['id']
            desc_asiento = f"Ajuste físico de inventario - {documento_numero}"
        else:
            # Es el primer item: consumimos el consecutivo en la base de datos de manera atómica
            res_num, _ = obtener_siguiente_consecutivo(conn, negocio_id, tipo_documento_id)
            if not res_num:
                res_num = str(max((tipo_doc['consecutivo'] or 0) + 1, (tipo_doc['numero_inicio'] or 1)))
                conn.execute("UPDATE tipos_documento_negocio SET consecutivo = %s WHERE id = %s", (int(res_num), tipo_documento_id))
            
            doc_num_final = str(int(res_num))
            desc_asiento = f"Ajuste físico de inventario - {doc_num_final}"
            comp_id = conn.execute("SELECT nextval('seq_comprobante_id')").fetchone()[0]
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
                     documento_fecha=date.today(),
                     tipo_documento_id=tipo_documento_id,
                     proveedor_id=tercero_id,
                     proveedor_nombre=tercero_nombre)
                     
        # 4. Recostear el producto
        _recostear_producto(conn, negocio_id, producto_id)
        
        # 5. Auto-guardar cotización de compra si hay proveedor y costo
        cotizacion_creada = False
        if tercero_id and costo_unitario and float(costo_unitario) > 0 and diff > 0:
            from datetime import timedelta
            f_cot = date.today()
            f_vence = f_cot + timedelta(days=180)
            # Buscar presentación "Unidad" por defecto
            pres_unidad = conn.execute("SELECT id FROM presentaciones WHERE LOWER(nombre) = 'unidad' LIMIT 1").fetchone()
            pres_id_default = pres_unidad['id'] if pres_unidad else None
            precio_cot = float(costo_unitario)
            
            cot_row = conn.execute("""
                SELECT id FROM cotizaciones_compras
                WHERE tercero_id = %s AND item_id = %s
                  AND (presentacion_id = %s OR (presentacion_id IS NULL AND %s IS NULL))
                LIMIT 1
            """, (tercero_id, producto_id, pres_id_default, pres_id_default)).fetchone()
            
            if cot_row:
                conn.execute("""
                    UPDATE cotizaciones_compras
                    SET precio = %s, fecha_cotizacion = %s, fecha_vencimiento = %s,
                        validada_proveedor = TRUE, updated_at = NOW()
                    WHERE id = %s
                """, (precio_cot, f_cot, f_vence, cot_row['id']))
            else:
                conn.execute("""
                    INSERT INTO cotizaciones_compras
                        (negocio_id, tercero_id, item_id, fecha_cotizacion, fecha_vencimiento,
                         descripcion_presentacion, unidades_item, precio, origen,
                         validada_proveedor, updated_at, presentacion_id)
                    VALUES (%s, %s, %s, %s, %s, 'Unidad', 1, %s, 'ajuste_fisico', TRUE, NOW(), %s)
                """, (negocio_id, tercero_id, producto_id, f_cot, f_vence, precio_cot, pres_id_default))
            cotizacion_creada = True
        
        # 6. Integración contable individualizada por producto
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

                # Validar que las cuentas existan, sean hoja (nivel >= 4) y acepten movimiento
                for campo, val in [('cuenta_inve_id', cuenta_inve), ('cuenta_ajuste_favor_id', cuenta_favor), ('cuenta_ajuste_contra_id', cuenta_contra)]:
                    if val:
                        cta = conn.execute("SELECT codigo, nombre, nivel, acepta_movimiento FROM cuentas_puc WHERE id=%s", (val,)).fetchone()
                        if not cta:
                            conn.rollback(); conn.close()
                            return jsonify({'ok': False, 'error': f'La {campo} (ID {val}) no existe en el PUC.'}), 400
                        if cta['nivel'] < 4:
                            conn.rollback(); conn.close()
                            return jsonify({'ok': False, 'error': f'La {campo} apunta a "{cta["codigo"]} — {cta["nombre"]}" (nivel {cta["nivel"]}). Debe ser una subcuenta hoja (nivel ≥ 4). Corrija la configuración de Grupos de Inventario.'}), 400
                        if not cta['acepta_movimiento']:
                            conn.rollback(); conn.close()
                            return jsonify({'ok': False, 'error': f'La {campo} "{cta["codigo"]} — {cta["nombre"]}" tiene acepta_movimiento=FALSE.'}), 400
                    else:
                        conn.rollback(); conn.close()
                        return jsonify({'ok': False, 'error': f'Falta configurar la {campo} en Grupos de Inventario para la categoría "{prod["categoria"]}".'}), 400
                
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
                        INSERT INTO movimientos_contables (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, producto_id,
                                                           tipo_documento_id, numero_documento, fecha, tipo_documento, origen_tipo, origen_id, descripcion_general, tercero_id)
                        VALUES (%s, %s, %s, %s, %s, 'debito', %s, %s, %s, %s, %s, CURRENT_DATE, %s, 'ajuste_inventario', %s, %s, %s)
                    """, (negocio_id, comp_id, db_cuenta_id, db_cod, concepto, monto_ajuste, session.get('usuario_id'), producto_id,
                          tipo_documento_id, doc_num_final, tipo_code, doc_num_final, desc_asiento, tercero_id))
                    
                    # Insertar Crédito
                    conn.execute("""
                        INSERT INTO movimientos_contables (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, producto_id,
                                                           tipo_documento_id, numero_documento, fecha, tipo_documento, origen_tipo, origen_id, descripcion_general, tercero_id)
                        VALUES (%s, %s, %s, %s, %s, 'credito', %s, %s, %s, %s, %s, CURRENT_DATE, %s, 'ajuste_inventario', %s, %s, %s)
                    """, (negocio_id, comp_id, cr_cuenta_id, cr_cod, concepto, monto_ajuste, session.get('usuario_id'), producto_id,
                          tipo_documento_id, doc_num_final, tipo_code, doc_num_final, desc_asiento, tercero_id))
            else:
                conn.rollback(); conn.close()
                return jsonify({'ok': False, 'error': f'La categoría "{prod["categoria"]}" no está configurada en Grupos de Inventario. Debe configurar cuenta de Inventario, Ajuste a Favor y Ajuste en Contra.'}), 400
        else:
            conn.rollback(); conn.close()
            return jsonify({'ok': False, 'error': 'El producto no tiene categoría asignada. Asigne una categoría antes de ajustar.'}), 400
            
        conn.commit()
        return jsonify({
            'ok': True,
            'mensaje': 'Ajuste registrado y contabilizado con éxito',
            'documento_numero': doc_num_final,
            'consecutivo_actualizado': consecutivo_actualizado,
            'cotizacion_creada': cotizacion_creada,
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
            WITH cont AS (
                SELECT numero_documento, comprobante_id,
                       SUM(CASE WHEN tipo IN ('debito', 'D') THEN monto ELSE 0 END) AS total_debitos
                FROM movimientos_contables
                WHERE negocio_id = %s
                GROUP BY numero_documento, comprobante_id
            )
            SELECT m.documento_numero, MAX(m.created_at) AS fecha, 
                   c.comprobante_id,
                   COALESCE(MAX(c.total_debitos), 0) AS total_debitos, 
                   COUNT(DISTINCT m.producto_id) AS total_items
            FROM movimientos_inventario m
            LEFT JOIN cont c ON c.numero_documento = m.documento_numero
            WHERE m.negocio_id = %s AND m.motivo = 'ajuste'
            GROUP BY m.documento_numero, c.comprobante_id
            ORDER BY fecha DESC
        """, (negocio_id, negocio_id)).fetchall()
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
            WHERE mc.negocio_id = %s AND mc.numero_documento = %s
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


def _pdf_tabla(pdf, col_w, headers, filas, aligns=None, wrap_col=0, alto_linea=5.5):
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_fill_color(230, 230, 230)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6, h, border=1, align='C', fill=True)
    pdf.ln()
    pdf.set_font('Helvetica', '', 7.5)
    for fila in filas:
        txt = fila[wrap_col]
        lineas = pdf.multi_cell(col_w[wrap_col], alto_linea, txt, split_only=True)
        alto_fila = max(len(lineas) * alto_linea, alto_linea)
        if pdf.get_y() + alto_fila > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 7.5)
            pdf.set_fill_color(230, 230, 230)
            for i, h in enumerate(headers):
                pdf.cell(col_w[i], 6, h, border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font('Helvetica', '', 7.5)
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        x_cur = x0
        for i, val in enumerate(fila):
            if i == wrap_col:
                pdf.set_xy(x_cur, y0)
                pdf.multi_cell(col_w[i], alto_linea, val, border=1, align='L')
            else:
                pdf.set_xy(x_cur, y0)
                pdf.cell(col_w[i], alto_fila, val, border=1, align=(aligns[i] if aligns else 'C'))
            x_cur += col_w[i]
        pdf.set_xy(pdf.l_margin, y0 + alto_fila)


def _pdf_documento_ajuste(nombre_negocio, doc_num, fecha_str, items, asiento):
    pdf = FPDF(format='letter', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 15)
    pdf.cell(0, 9, _pdf_sanitize(nombre_negocio), ln=1, align='C')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, 'Inventario Físico', ln=1, align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, f'Documento: {_pdf_sanitize(doc_num)}', ln=1, align='C')
    if fecha_str:
        pdf.cell(0, 5, f'Fecha: {_pdf_sanitize(fecha_str)}', ln=1, align='C')

    sobr_cant = sum(float(it['cantidad'] or 0) for it in items if it['tipo'] == 'entrada')
    sobr_valor = sum(float(it['valor_total'] or 0) for it in items if it['tipo'] == 'entrada')
    falt_cant = sum(abs(float(it['cantidad'] or 0)) for it in items if it['tipo'] != 'entrada')
    falt_valor = sum(float(it['valor_total'] or 0) for it in items if it['tipo'] != 'entrada')

    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, f"Total ítems: {len(items)}    Sobrantes: {_pdf_money(sobr_cant)} und / ${_pdf_money(sobr_valor)}    Faltantes: {_pdf_money(falt_cant)} und / ${_pdf_money(falt_valor)}", ln=1)
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, 'Movimientos de Inventario (Kardex)', ln=1)
    kardex = []
    for it in items:
        nombre = _pdf_sanitize(it['nombre_producto'])[:70]
        if it.get('categoria'):
            nombre += ' - ' + _pdf_sanitize(it['categoria'])
        kardex.append([
            nombre,
            'Sobrante' if it['tipo'] == 'entrada' else 'Faltante',
            _pdf_money(it['cantidad']),
            _pdf_money(it['costo_und']),
            _pdf_money(it['valor_total']),
        ])
    _pdf_tabla(pdf, [62, 16, 16, 22, 24],
               ['Insumo', 'Tipo', 'Cant.', 'Costo Und', 'Valor'],
               kardex, aligns=['L', 'C', 'C', 'R', 'R'])

    pdf.ln(3)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, 'Asiento Contable Detallado', ln=1)
    if asiento:
        filas_asiento = []
        for a in asiento:
            nombre_cuenta = _pdf_sanitize(a['cuenta_nombre'])
            if a.get('concepto'):
                nombre_cuenta += '\nConcepto: ' + _pdf_sanitize(a['concepto'])
            filas_asiento.append([
                _pdf_sanitize(a['cuenta']),
                nombre_cuenta,
                _pdf_sanitize(a['tipo']),
                _pdf_money(a['monto']),
            ])
        _pdf_tabla(pdf, [22, 82, 14, 30],
                   ['Cuenta', 'Nombre / Concepto', 'T', 'Monto'],
                   filas_asiento, aligns=['C', 'L', 'C', 'R'], wrap_col=1)
        total_d = sum(float(a['monto'] or 0) for a in asiento if a['tipo'] in ('D', 'debito'))
        total_c = sum(float(a['monto'] or 0) for a in asiento if a['tipo'] in ('C', 'credito'))
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(0, 6, f'Débitos totales: ${_pdf_money(total_d)}    Créditos totales: ${_pdf_money(total_c)}', ln=1)
    else:
        pdf.set_font('Helvetica', 'I', 8)
        pdf.cell(0, 6, 'Este documento no generó movimientos contables (sin parametrización).', ln=1)

    _pdf_firma_tuctuc(pdf)

    return pdf


@bp.route('/api/inventario/<int:negocio_id>/ajuste-fisico/documento/<documento_numero>/pdf')
def api_ajuste_documento_pdf(negocio_id, documento_numero):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    if FPDF is None:
        return jsonify({'ok': False, 'error': 'PDF no disponible (falta fpdf2)'}), 500
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        nombre_negocio = (contexto.get('negocio_nombre') or 'Negocio') if contexto else 'Negocio'
        fecha_row = conn.execute("""
            SELECT MAX(created_at) AS fecha FROM movimientos_inventario
            WHERE negocio_id = %s AND documento_numero = %s AND motivo = 'ajuste'
        """, (negocio_id, documento_numero)).fetchone()
        fecha_str = fecha_row['fecha'].strftime('%Y-%m-%d %H:%M') if fecha_row and fecha_row['fecha'] else ''
        items = conn.execute("""
            SELECT m.producto_id, m.nombre_producto, m.cantidad, m.tipo, m.costo_und, m.valor_total,
                   m.stock_anterior, m.stock_nuevo, p.categoria
            FROM movimientos_inventario m
            JOIN productos p ON p.id = m.producto_id
            WHERE m.negocio_id = %s AND m.documento_numero = %s AND m.motivo = 'ajuste'
            ORDER BY m.id
        """, (negocio_id, documento_numero)).fetchall()
        asiento = conn.execute("""
            SELECT mc.cuenta, c.nombre AS cuenta_nombre, mc.concepto, mc.tipo, mc.monto, p.nombre AS producto_nombre
            FROM movimientos_contables mc
            JOIN cuentas_puc c ON c.id = mc.cuenta_id
            LEFT JOIN productos p ON p.id = mc.producto_id
            WHERE mc.negocio_id = %s AND mc.numero_documento = %s
            ORDER BY mc.id
        """, (negocio_id, documento_numero)).fetchall()
        pdf = _pdf_documento_ajuste(
            nombre_negocio, documento_numero, fecha_str,
            [dict(i) for i in items], [dict(a) for a in asiento])
        resp = Response(bytes(pdf.output()), mimetype='application/pdf')
        resp.headers['Content-Disposition'] = f"inline; filename=ajuste_fisico_{documento_numero}.pdf"
        return resp
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
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
            where_comp = "negocio_id = %s AND tipo_documento_id = %s AND numero_documento = %s"
            params_comp = [negocio_id, tipo_documento_id, documento_numero]
        else:
            # Fallback legacy
            origen_id_str = f"{tipo_documento}:{documento_numero}"
            pedido_id_str = str(pedido_row['id']) if pedido_row else None
            where_comp = """
                negocio_id = %s AND (
                    (origen_tipo = 'pedido' AND origen_id = %s)
                    OR (origen_tipo IS NOT NULL AND LOWER(origen_id) = LOWER(%s))
                    OR (numero_documento ILIKE %s)
                )
            """
            params_comp = [negocio_id, pedido_id_str, origen_id_str, f'%{documento_numero}%']
        
        if nueva_fecha:
            conn.execute(f"""
                UPDATE movimientos_contables
                SET fecha = %s,
                    created_at = %s::date + (created_at::time)
                WHERE {where_comp}
            """, [nueva_fecha, nueva_fecha] + params_comp)
            
        if nuevo_tercero_id is not None:
            conn.execute(f"""
                UPDATE movimientos_contables
                SET tercero_id = %s
                WHERE {where_comp}
            """, [int(nuevo_tercero_id)] + params_comp)
            
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
        datos = _query_reporte_ventas_costos(conn, negocio_id, desde, hasta)
        return jsonify({'ok': True, 'reporte': datos})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


def _query_reporte_ventas_costos(conn, negocio_id, desde, hasta):
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
          AND (ped.estado IS NULL OR ped.estado = '' OR ped.estado NOT IN ('anulado', 'premontado'))
          AND ped.numero_documento IS NOT NULL AND ped.numero_documento != ''
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
    return datos


@bp.route('/api/inventario/<int:negocio_id>/reporte-ventas-costos/detalle')
def api_reporte_ventas_costos_detalle(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    producto_id = request.args.get('producto_id')
    if not desde or not hasta or not producto_id:
        return jsonify({'ok': False, 'error': 'Fechas y producto_id requeridos'}), 400
    try:
        producto_id = int(producto_id)
    except ValueError:
        return jsonify({'ok': False, 'error': 'producto_id inválido'}), 400
    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT 
                ped.id AS pedido_id,
                COALESCE(ped.fecha, ped.created_at::date) AS fecha,
                ped.numero_documento,
                ped.nombre_cliente,
                ped.estado,
                pi.cantidad,
                pi.precio_unitario,
                pi.costo_unitario,
                (pi.cantidad * pi.precio_unitario) AS total_venta,
                (pi.cantidad * pi.costo_unitario) AS total_costo,
                ped.metodo_pago
            FROM pedido_items pi
            JOIN pedidos ped ON ped.id = pi.pedido_id
            WHERE ped.negocio_id = %s
              AND pi.producto_id = %s
              AND (ped.estado IS NULL OR ped.estado = '' OR ped.estado NOT IN ('anulado', 'premontado'))
              AND ped.numero_documento IS NOT NULL AND ped.numero_documento != ''
              AND COALESCE(ped.fecha, ped.created_at::date) >= %s::date
              AND COALESCE(ped.fecha, ped.created_at::date) <= %s::date
            ORDER BY COALESCE(ped.fecha, ped.created_at::date) DESC, ped.id DESC
        """, (negocio_id, producto_id, desde, hasta)).fetchall()
        documentos = []
        for r in rows:
            d = dict(r)
            if d.get('fecha'):
                d['fecha'] = d['fecha'].strftime('%Y-%m-%d') if hasattr(d['fecha'], 'strftime') else str(d['fecha'])
            for k in ('cantidad', 'precio_unitario', 'costo_unitario', 'total_venta', 'total_costo'):
                d[k] = float(d[k]) if d.get(k) is not None else 0.0
            documentos.append(d)
        conn.close()
        return jsonify({'ok': True, 'documentos': documentos})
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


def _pdf_sanitize(txt):
    out = []
    for ch in str(txt):
        out.append(ch if ord(ch) <= 255 else '?')
    return ''.join(out)


def _pdf_money(valor):
    try:
        return f'{float(valor):,.0f}'
    except Exception:
        return '0'


def _pdf_firma_tuctuc(pdf):
    """Firma de la herramienta al final del reporte — pequeña y discreta."""
    pdf.ln(6)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(170, 170, 170)
    pdf.cell(0, 4, 'Generado con TUC TUC', ln=1, align='C')
    pdf.set_text_color(0, 0, 0)


def _pdf_reporte_ventas_costos(nombre_negocio, desde, hasta, datos):
    pdf = FPDF(format='letter', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 15)
    pdf.cell(0, 9, _pdf_sanitize(nombre_negocio), ln=1, align='C')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 6, 'Informe de Ventas y Costos', ln=1, align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, f'Rango: {desde} al {hasta}', ln=1, align='C')

    total_ventas = sum(d['total_venta'] for d in datos)
    total_costos = sum(d['total_costo'] for d in datos)
    total_margen = total_ventas - total_costos
    pct = (total_margen / total_ventas * 100.0) if total_ventas else 0.0

    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, f"Ventas: ${_pdf_money(total_ventas)}   Costos: ${_pdf_money(total_costos)}   Margen: ${_pdf_money(total_margen)} ({pct:.1f}%)", ln=1)
    pdf.ln(2)

    col_w = [56, 14, 20, 20, 24, 24, 24, 14]
    headers = ['Producto', 'Cant', 'P.Unit', 'C.Unit', 'Total Venta', 'Total Costo', 'Margen', '%']
    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_fill_color(230, 230, 230)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6, h, border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font('Helvetica', '', 7.5)
    alto_linea = 5.5
    for d in datos:
        nombre = _pdf_sanitize(d['nombre_producto'])[:80]
        fila = [
            nombre,
            f"{d['cantidad']:.0f}",
            _pdf_money(d['precio_unitario']),
            _pdf_money(d['costo_unitario']),
            _pdf_money(d['total_venta']),
            _pdf_money(d['total_costo']),
            _pdf_money(d['margen_total']),
            f"{d['margen_porcentual']:.1f}",
        ]
        lineas = pdf.multi_cell(col_w[0], alto_linea, nombre, split_only=True)
        alto_fila = max(len(lineas) * alto_linea, alto_linea)
        if pdf.get_y() + alto_fila > pdf.page_break_trigger:
            pdf.add_page()
        x_fila = pdf.get_x()
        y_fila = pdf.get_y()
        pdf.multi_cell(col_w[0], alto_linea, nombre, border=1, align='L')
        pdf.set_xy(x_fila + col_w[0], y_fila)
        for i in range(1, len(fila)):
            pdf.cell(col_w[i], alto_fila, fila[i], border=1, align='C')
        pdf.set_xy(pdf.l_margin, y_fila + alto_fila)

    pdf.set_font('Helvetica', 'B', 7.5)
    pdf.set_fill_color(235, 245, 235)
    total_cant = sum(d['cantidad'] for d in datos)
    foot = ['TOTALES', f"{total_cant:.0f}", '', '',
            _pdf_money(total_ventas), _pdf_money(total_costos),
            _pdf_money(total_margen), f"{pct:.1f}"]
    for i, val in enumerate(foot):
        align = 'C' if i > 0 else 'L'
        pdf.cell(col_w[i], 6, val, border=1, align=align, fill=True)
    pdf.ln()

    _pdf_firma_tuctuc(pdf)

    return pdf


@bp.route('/api/inventario/<int:negocio_id>/reporte-ventas-costos/pdf')
def api_reporte_ventas_costos_pdf(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    if FPDF is None:
        return jsonify({'ok': False, 'error': 'PDF no disponible (falta fpdf2)'}), 500

    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    if not desde or not hasta:
        return jsonify({'ok': False, 'error': 'Debe especificar las fechas desde y hasta'}), 400

    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        nombre_negocio = (contexto.get('negocio_nombre') or 'Negocio') if contexto else 'Negocio'
        datos = _query_reporte_ventas_costos(conn, negocio_id, desde, hasta)
        conn.close()
        pdf = _pdf_reporte_ventas_costos(nombre_negocio, desde, hasta, datos)
        resp = Response(bytes(pdf.output()), mimetype='application/pdf')
        resp.headers['Content-Disposition'] = 'inline; filename=reporte_ventas_costos.pdf'
        return resp
    except Exception as e:
        try: conn.close()
        except: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


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
            SELECT CASE WHEN mc.tipo_documento IS NOT NULL AND mc.tipo_documento <> '' AND POSITION('-' IN mc.numero_documento) = 0 THEN mc.tipo_documento || '-' || mc.numero_documento ELSE mc.numero_documento END AS numero_comprobante,
                   mc.tipo_documento_id, tdn.nombre AS tipo_documento_nombre,
                   SUM(CASE WHEN mc.tipo IN ('debito', 'D') THEN mc.monto ELSE -mc.monto END) AS total_contab,
                   MAX(mc.fecha) as fecha
            FROM movimientos_contables mc
            JOIN cuentas_puc cp ON cp.id = mc.cuenta_id
            LEFT JOIN tipos_documento_negocio tdn ON tdn.id = mc.tipo_documento_id
            WHERE mc.negocio_id = %s AND cp.codigo LIKE '14%%'
            GROUP BY mc.numero_documento, mc.tipo_documento, mc.tipo_documento_id, tdn.nombre
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


@bp.route('/api/inventario/<int:negocio_id>/reporte-ensambles')
def api_reporte_ensambles(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    prod_padre_id = _int_o_none(request.args.get('producto_padre_id'))
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    
    if not prod_padre_id or not fecha_desde or not fecha_hasta:
        return jsonify({'ok': False, 'error': 'Filtros incompletos (producto padre y fechas requeridos)'}), 400
        
    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto or not _puede_gestionar_negocio(contexto):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403
            
        # Get parent product info
        padre = conn.execute("SELECT id, nombre, categoria FROM productos WHERE id = %s AND negocio_id = %s", (prod_padre_id, negocio_id)).fetchone()
        if not padre:
            return jsonify({'ok': False, 'error': 'Producto padre no encontrado'}), 404
            
        # Query output movements in movimientos_inventario associated with the parent product
        movements = conn.execute("""
            SELECT 
                m.id, 
                m.producto_id, 
                m.nombre_producto, 
                m.documento_numero, 
                COALESCE(m.documento_fecha, m.created_at::date) AS fecha, 
                m.cantidad, 
                m.costo_und AS costo_unitario, 
                COALESCE(m.valor_total, m.cantidad * m.costo_und, 0.0) AS costo_total,
                m.tipo_documento
            FROM movimientos_inventario m
            WHERE m.negocio_id = %s
              AND m.producto_padre_id = %s
              AND m.tipo = 'salida'
              AND COALESCE(m.documento_fecha, m.created_at::date) >= %s
              AND COALESCE(m.documento_fecha, m.created_at::date) <= %s
            ORDER BY m.nombre_producto, fecha, m.documento_numero, m.id
        """, (negocio_id, prod_padre_id, fecha_desde, fecha_hasta)).fetchall()
        
        # Unique documents inside movements to pull their accounting COGS cost
        docs = list(set([ (m['documento_numero'], m['tipo_documento'] or 'FACTURA_DE_VENTA') for m in movements if m['documento_numero'] ]))
        
        # Build accounting COGS map & parent quantities map
        cogs_map = {}
        parent_qty_map = {}
        for doc_num, doc_type in docs:
            consecutive = doc_num
            if '-' in doc_num:
                consecutive = doc_num.split('-')[-1].strip()
                
            # Query sum of COGS entries in movimientos_contables with normalized document type check
            cogs_row = conn.execute("""
                SELECT SUM(monto) AS total_cogs
                FROM movimientos_contables
                WHERE negocio_id = %s
                  AND (numero_documento = %s OR numero_documento = %s)
                  AND REPLACE(UPPER(tipo_documento), '_', ' ') = REPLACE(UPPER(%s), '_', ' ')
                  AND LEFT(cuenta, 2) = '61'
                  AND (
                      UPPER(concepto) = 'COSTO VENTA: ' || UPPER(%s)
                      OR UPPER(concepto) = 'COSTO DE VENTA: ' || UPPER(%s)
                      OR producto_id = %s
                  )
            """, (negocio_id, consecutive, doc_num, doc_type, padre['nombre'], padre['nombre'], prod_padre_id)).fetchone()
            
            total_cogs = float(cogs_row['total_cogs']) if (cogs_row and cogs_row['total_cogs'] is not None) else 0.0
            cogs_map[doc_num] = total_cogs
            
            # Find parent product quantity for this document (Kardex output details or Pedido items)
            ref_row = conn.execute("""
                SELECT DISTINCT referencia_tipo, referencia_id 
                FROM movimientos_inventario 
                WHERE negocio_id = %s AND producto_padre_id = %s AND documento_numero = %s
                LIMIT 1
            """, (negocio_id, prod_padre_id, doc_num)).fetchone()
            
            ref_type = ref_row['referencia_tipo'] if ref_row else None
            ref_id = ref_row['referencia_id'] if ref_row else None
            ref_id_int = _int_o_none(ref_id)
            
            qty = 0.0
            if ref_type == 'produccion':
                qty_row = conn.execute("""
                    SELECT SUM(cantidad) FROM movimientos_inventario
                    WHERE negocio_id = %s AND producto_id = %s AND tipo = 'entrada'
                      AND referencia_tipo = 'produccion' AND (documento_numero = %s OR referencia_id = %s)
                """, (negocio_id, prod_padre_id, doc_num, ref_id)).fetchone()
                qty = float(qty_row[0]) if (qty_row and qty_row[0] is not None) else 0.0
            else:
                qty_row = conn.execute("""
                    SELECT SUM(pi.cantidad) 
                    FROM pedido_items pi
                    JOIN pedidos p ON p.id = pi.pedido_id
                    WHERE p.negocio_id = %s AND pi.producto_id = %s
                      AND (p.numero_documento = %s OR p.numero_documento = %s OR p.id = %s)
                """, (negocio_id, prod_padre_id, consecutive, doc_num, ref_id_int)).fetchone()
                qty = float(qty_row[0]) if (qty_row and qty_row[0] is not None) else 0.0
                
            parent_qty_map[doc_num] = qty
            
        res_movements = []
        for m in movements:
            res_movements.append({
                'id': m['id'],
                'producto_id': m['producto_id'],
                'nombre_producto': m['nombre_producto'],
                'documento_numero': m['documento_numero'],
                'tipo_documento': m['tipo_documento'] or 'FACTURA_DE_VENTA',
                'fecha': m['fecha'].isoformat() if m['fecha'] else '',
                'cantidad': float(m['cantidad']),
                'costo_unitario': float(m['costo_unitario'] or 0.0),
                'costo_total': float(m['costo_total'] or 0.0)
            })
            
        return jsonify({
            'ok': True,
            'producto_padre': {
                'id': padre['id'],
                'nombre': padre['nombre'],
                'categoria': padre['categoria']
            },
            'movements': res_movements,
            'cogs_map': cogs_map,
            'parent_qty_map': parent_qty_map
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/produccion/sugerencias')
def api_produccion_sugerencias(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    try:
        dias_historial = int(request.args.get('dias_historial', 30))
        dias_defecto = int(request.args.get('dias_defecto', 7))
        growth_window = int(request.args.get('growth_window', 7))
        max_growth = float(request.args.get('max_growth', 100.0)) / 100.0
        min_growth = float(request.args.get('min_growth', -50.0)) / 100.0
    except (ValueError, TypeError):
        dias_historial = 30
        dias_defecto = 7
        growth_window = 7
        max_growth = 1.0
        min_growth = -0.5
        
    conn = get_db_connection()
    try:
        # 1. Buscar todos los productos con receta estándar en este negocio
        produced_products = conn.execute("""
            SELECT DISTINCT p.id, p.nombre, COALESCE(s.stock, 0) AS stock_actual
            FROM tarjeta_estandar t
            JOIN productos p ON p.id = t.producto_id
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.negocio_id = %s AND s.bodega = 1
            WHERE p.negocio_id = %s AND p.disponible = TRUE
            ORDER BY p.nombre
        """, (negocio_id, negocio_id)).fetchall()
        
        sugerencias = []
        for prod in produced_products:
            p_id = prod['id']
            p_nombre = prod['nombre']
            stock_actual = float(prod['stock_actual'])
            
            # --- VALIDACIÓN DE INCONSISTENCIAS ---
            has_prod_entries = conn.execute("""
                SELECT 1 FROM movimientos_inventario 
                WHERE negocio_id = %s AND producto_id = %s AND tipo = 'entrada' AND referencia_tipo = 'produccion'
                LIMIT 1
            """, (negocio_id, p_id)).fetchone()
            
            has_exits = conn.execute("""
                SELECT 1 FROM movimientos_inventario 
                WHERE negocio_id = %s AND producto_id = %s AND tipo = 'salida'
                LIMIT 1
            """, (negocio_id, p_id)).fetchone()
            
            if has_exits and not has_prod_entries:
                continue
            
            # Calcular demanda, ciclo (frecuencia) y crecimiento
            ddp, frecuencia, growth_rate = _calcular_demanda_y_ciclo(
                conn, negocio_id, p_id, stock_actual,
                dias_historial, dias_defecto, growth_window, max_growth, min_growth
            )
            
            if ddp < 0.0001:
                # Excluir productos con consumo cero
                continue
            
            # Demanda diaria proyectada
            demanda_proyectada = ddp * (1.0 + growth_rate)
            
            # 1. Calcular días de cobertura
            if stock_actual <= 0.0001:
                cobertura_dias = 0.0
            elif demanda_proyectada < 0.0001:
                cobertura_dias = 9999.0
            else:
                cobertura_dias = stock_actual / demanda_proyectada
                
            # 2. Calcular fecha probable
            import datetime
            if cobertura_dias == 0.0:
                fecha_probable = "Inmediato"
            elif cobertura_dias == 9999.0:
                fecha_probable = "Sin consumo"
            else:
                dias_red = int(round(cobertura_dias))
                fecha_probable = (datetime.date.today() + datetime.timedelta(days=dias_red)).strftime('%d-%b-%Y')
                
            # 3. Calcular cantidad recomendada (para cubrir el ciclo completo)
            cantidad_sugerida = (demanda_proyectada * frecuencia) - stock_actual
            if cantidad_sugerida < 0.0001:
                cantidad_sugerida = demanda_proyectada * frecuencia
                
            if cantidad_sugerida < 0.0001:
                cantidad_sugerida = 0.0
                
            # Validar disponibilidad de materias primas/ingredientes
            componentes = conn.execute("""
                SELECT t.componente_id, t.cantidad, p.nombre, COALESCE(s.stock, 0) AS stock_ingrediente
                FROM tarjeta_estandar t
                JOIN productos p ON p.id = t.componente_id
                LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.negocio_id = %s AND s.bodega = 1
                WHERE t.producto_id = %s
            """, (negocio_id, p_id)).fetchall()
            
            factible = True
            max_produccion_posible = 999999.0
            
            for comp in componentes:
                qty_por_unidad = float(comp['cantidad'])
                stock_ingrediente = float(comp['stock_ingrediente'])
                
                qty_requerida = qty_por_unidad * cantidad_sugerida
                if stock_ingrediente < qty_requerida:
                    factible = False
                    
                if qty_por_unidad > 0:
                    posible = stock_ingrediente / qty_por_unidad
                    if posible < max_produccion_posible:
                        max_produccion_posible = posible
                        
            if max_produccion_posible == 999999.0:
                max_produccion_posible = 0.0
                
            cantidad_factible = cantidad_sugerida if factible else max_produccion_posible
            
            sugerencias.append({
                'producto_id': p_id,
                'producto_nombre': p_nombre,
                'stock_actual': stock_actual,
                'demanda_diaria': round(ddp, 3),
                'frecuencia_dias': int(frecuencia),
                'growth_rate_pct': round(growth_rate * 100, 1),
                'cobertura_dias': round(cobertura_dias, 1),
                'fecha_probable': fecha_probable,
                'cantidad_sugerida': round(cantidad_sugerida, 2),
                'factible': factible,
                'cantidad_factible': round(cantidad_factible, 2)
            })
            
        # Ordenar por cobertura
        sugerencias.sort(key=lambda x: x['cobertura_dias'])
        
        return jsonify({
            'ok': True,
            'sugerencias': sugerencias
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ensambles/sugerencias')
def api_ensambles_sugerencias(negocio_id):
    """Proyecta ventas facturadas y traduce el resultado a necesidades de ensamble."""
    import datetime
    import math

    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    def _param_int(nombre, defecto, minimo, maximo):
        try:
            return max(minimo, min(maximo, int(request.args.get(nombre, defecto))))
        except (ValueError, TypeError):
            return defecto

    dias_historial = _param_int('dias_historial', 60, 7, 365)
    dias_recientes = _param_int('dias_recientes', 14, 3, 90)
    dias_defecto = _param_int('dias_defecto', 7, 1, 90)
    max_growth = _param_int('max_growth', 100, 0, 500)
    min_growth = _param_int('min_growth', -50, -100, 0)
    seguridad = _param_int('seguridad', 0, 0, 100)

    conn = get_db_connection()
    try:
        contexto = _contexto_negocio(conn, negocio_id)
        if not contexto or not _puede_gestionar_negocio(contexto):
            return jsonify({'ok': False, 'error': 'No autorizado'}), 403

        hoy = datetime.date.today()
        fecha_desde = hoy - datetime.timedelta(days=dias_historial - 1)
        fecha_hasta = hoy
        dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

        productos = conn.execute("""
            SELECT DISTINCT p.id, p.nombre
            FROM productos p
            JOIN tarjeta_estandar te ON te.producto_id = p.id
            WHERE p.negocio_id = %s AND p.disponible = TRUE
            ORDER BY p.nombre
        """, (negocio_id,)).fetchall()

        ventas = conn.execute("""
            SELECT pi.producto_id,
                   COALESCE(pi.nombre_producto, p.nombre) AS nombre_producto,
                   COALESCE(ped.fecha::date, ped.created_at::date) AS fecha,
                   SUM(pi.cantidad) AS cantidad
            FROM pedido_items pi
            JOIN pedidos ped ON ped.id = pi.pedido_id
            JOIN productos p ON p.id = pi.producto_id
            JOIN tipos_documento_negocio td ON td.id = ped.tipo_documento_id
            WHERE ped.negocio_id = %s
              AND td.tipo_movimiento = 'venta'
              AND ped.numero_documento IS NOT NULL
              AND TRIM(ped.numero_documento) <> ''
              AND (ped.estado IS NULL OR LOWER(ped.estado) NOT IN ('anulado', 'cancelado'))
              AND COALESCE(ped.fecha::date, ped.created_at::date) BETWEEN %s::date AND %s::date
            GROUP BY pi.producto_id, COALESCE(pi.nombre_producto, p.nombre), COALESCE(ped.fecha::date, ped.created_at::date)
            ORDER BY pi.producto_id, fecha
        """, (negocio_id, fecha_desde, fecha_hasta)).fetchall()

        ventas_por_producto = {}
        for venta in ventas:
            ventas_por_producto.setdefault(venta['producto_id'], []).append({
                'fecha': venta['fecha'],
                'cantidad': float(venta['cantidad'] or 0)
            })

        componentes = conn.execute("""
            SELECT te.producto_id, te.componente_id, te.cantidad,
                   cp.nombre AS componente_nombre,
                   COALESCE(si.stock, 0) AS stock_actual
            FROM tarjeta_estandar te
            JOIN productos cp ON cp.id = te.componente_id
            JOIN productos padre ON padre.id = te.producto_id
            LEFT JOIN saldos_inventario si
              ON si.producto_id = te.componente_id
             AND si.negocio_id = %s AND si.bodega = 1
            WHERE padre.negocio_id = %s
            ORDER BY te.producto_id, cp.nombre
        """, (negocio_id, negocio_id)).fetchall()

        componentes_por_producto = {}
        for componente in componentes:
            componentes_por_producto.setdefault(componente['producto_id'], []).append(componente)

        sugerencias = []
        consolidado = {}
        for producto in productos:
            p_id = producto['id']
            registros = ventas_por_producto.get(p_id, [])
            if not registros:
                continue

            por_fecha = {r['fecha']: r['cantidad'] for r in registros}
            fechas_venta = sorted(por_fecha)
            total_vendido = sum(por_fecha.values())
            dias_venta = len(fechas_venta)
            frecuencia = dias_defecto
            if len(fechas_venta) > 1:
                diferencias = [(fechas_venta[i] - fechas_venta[i - 1]).days for i in range(1, len(fechas_venta))]
                frecuencia = max(1, round(sum(diferencias) / len(diferencias)))

            dias_por_semana = {i: 0.0 for i in range(7)}
            ocurrencias_por_semana = {i: 0 for i in range(7)}
            for i in range(dias_historial):
                dia = fecha_desde + datetime.timedelta(days=i)
                ocurrencias_por_semana[dia.weekday()] += 1
                dias_por_semana[dia.weekday()] += por_fecha.get(dia, 0.0)

            promedios_semana = {
                dia: (dias_por_semana[dia] / ocurrencias_por_semana[dia])
                for dia in range(7)
            }
            contemplados = [dias_semana[dia] for dia in range(7) if dias_por_semana[dia] > 0]
            demanda_dia_venta = total_vendido / dias_venta if dias_venta else 0.0

            reciente_desde = hoy - datetime.timedelta(days=dias_recientes - 1)
            anterior_desde = reciente_desde - datetime.timedelta(days=dias_recientes)
            reciente = sum(c for f, c in por_fecha.items() if f >= reciente_desde)
            anterior = sum(c for f, c in por_fecha.items() if anterior_desde <= f < reciente_desde)
            growth = ((reciente - anterior) / anterior) if anterior > 0 else 0.0
            growth = max(min_growth / 100.0, min(max_growth / 100.0, growth))

            fecha_proxima = hoy + datetime.timedelta(days=1)
            for offset in range(1, 15):
                candidata = hoy + datetime.timedelta(days=offset)
                if promedios_semana[candidata.weekday()] > 0:
                    fecha_proxima = candidata
                    break
            cantidad_base = promedios_semana[fecha_proxima.weekday()] or demanda_dia_venta
            cantidad_recomendada = max(0.0, cantidad_base * (1 + growth) * (1 + seguridad / 100.0))
            cantidad_recomendada = math.ceil(cantidad_recomendada)

            detalle = []
            for componente in componentes_por_producto.get(p_id, []):
                por_unidad = float(componente['cantidad'] or 0)
                requerida = round(por_unidad * cantidad_recomendada, 4)
                stock = float(componente['stock_actual'] or 0)
                diferencia = round(stock - requerida, 4)
                detalle.append({
                    'componente_id': componente['componente_id'],
                    'componente_nombre': componente['componente_nombre'],
                    'cantidad_por_unidad': por_unidad,
                    'cantidad_requerida': requerida,
                    'stock_actual': stock,
                    'diferencia': diferencia
                })
                resumen = consolidado.setdefault(componente['componente_id'], {
                    'componente_id': componente['componente_id'],
                    'componente_nombre': componente['componente_nombre'],
                    'stock_actual': stock,
                    'cantidad_requerida': 0.0
                })
                resumen['cantidad_requerida'] += requerida

            sugerencias.append({
                'producto_id': p_id,
                'producto_nombre': producto['nombre'],
                'ultima_venta': fechas_venta[-1].isoformat(),
                'proxima_venta': fecha_proxima.isoformat(),
                'dia_proxima_venta': dias_semana[fecha_proxima.weekday()],
                'dias_semana_contemplados': contemplados,
                'ventas_total': round(total_vendido, 2),
                'dias_con_venta': dias_venta,
                'frecuencia_dias': frecuencia,
                'demanda_por_dia_venta': round(demanda_dia_venta, 2),
                'growth_rate_pct': round(growth * 100, 1),
                'cantidad_recomendada': cantidad_recomendada,
                'cantidad_final': cantidad_recomendada,
                'componentes': detalle
            })

        for resumen in consolidado.values():
            resumen['cantidad_requerida'] = round(resumen['cantidad_requerida'], 4)
            resumen['diferencia'] = round(resumen['stock_actual'] - resumen['cantidad_requerida'], 4)

        sugerencias.sort(key=lambda item: (item['proxima_venta'], item['producto_nombre']))
        return jsonify({
            'ok': True,
            'configuracion': {
                'fecha_desde': fecha_desde.isoformat(),
                'fecha_hasta': fecha_hasta.isoformat(),
                'dias_historial': dias_historial,
                'dias_recientes': dias_recientes,
                'dias_defecto': dias_defecto,
                'max_growth': max_growth,
                'min_growth': min_growth,
                'seguridad': seguridad,
                'descripcion_periodo': f"Ventas facturadas del {fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')}"
            },
            'sugerencias': sugerencias,
            'materias_primas': sorted(consolidado.values(), key=lambda item: item['componente_nombre'])
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


def _calcular_demanda_y_ciclo(conn, negocio_id, producto_id, current_stock,
                              dias_historial, dias_defecto, growth_window, max_growth, min_growth,
                              usar_dias_con_stock=True):
    import datetime
    
    # 1. Obtener todos los movimientos de los últimos X días
    limite_fecha = datetime.datetime.now() - datetime.timedelta(days=dias_historial)
    movs = conn.execute("""
        SELECT tipo, cantidad, created_at 
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s AND created_at >= %s
        ORDER BY created_at DESC
    """, (negocio_id, producto_id, limite_fecha)).fetchall()
    
    # 2. Reconstruir stock diario hacia atrás
    stock_temp = float(current_stock)
    movs_por_dia = {}
    total_salidas = 0.0
    for m in movs:
        dia_str = m['created_at'].strftime('%Y-%m-%d')
        if dia_str not in movs_por_dia:
            movs_por_dia[dia_str] = []
        movs_por_dia[dia_str].append(m)
        if m['tipo'] == 'salida':
            total_salidas += float(m['cantidad'])
            
    # Calcular stock al final de cada uno de los últimos X días
    hoy = datetime.date.today()
    dias_con_stock = 0
    for i in range(dias_historial):
        dia = hoy - datetime.timedelta(days=i)
        dia_str = dia.strftime('%Y-%m-%d')
        
        if stock_temp > 0.0001:
            dias_con_stock += 1
            
        if dia_str in movs_por_dia:
            for m in movs_por_dia[dia_str]:
                if m['tipo'] == 'entrada':
                    stock_temp -= float(m['cantidad'])
                elif m['tipo'] == 'salida':
                    stock_temp += float(m['cantidad'])
                    
    # Demanda diaria promedio
    dias_div = max(1, dias_con_stock if usar_dias_con_stock else dias_historial)
    ddp = total_salidas / dias_div
    
    # 3. Frecuencia de producción
    prod_dates = conn.execute("""
        SELECT DISTINCT DATE(created_at) AS fecha
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s AND tipo = 'entrada' AND referencia_tipo = 'produccion'
        ORDER BY fecha DESC
        LIMIT 10
    """, (negocio_id, producto_id)).fetchall()
    
    if len(prod_dates) >= 2:
        diffs = []
        for j in range(len(prod_dates) - 1):
            d1 = prod_dates[j]['fecha']
            d2 = prod_dates[j+1]['fecha']
            diffs.append((d1 - d2).days)
        frecuencia = sum(diffs) / len(diffs)
    else:
        frecuencia = float(dias_defecto)
        
    frecuencia = max(1.0, round(frecuencia))
    
    # 4. Calcular tasa de crecimiento real
    limite_w1 = datetime.datetime.now() - datetime.timedelta(days=growth_window)
    limite_w2 = datetime.datetime.now() - datetime.timedelta(days=growth_window * 2)
    
    w1_salidas = conn.execute("""
        SELECT COALESCE(SUM(cantidad), 0) AS total 
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s AND tipo = 'salida' AND created_at >= %s
    """, (negocio_id, producto_id, limite_w1)).fetchone()['total']
    
    w2_salidas = conn.execute("""
        SELECT COALESCE(SUM(cantidad), 0) AS total 
        FROM movimientos_inventario
        WHERE negocio_id = %s AND producto_id = %s AND tipo = 'salida' AND created_at >= %s AND created_at < %s
    """, (negocio_id, producto_id, limite_w2, limite_w1)).fetchone()['total']
    
    w1_val = float(w1_salidas)
    w2_val = float(w2_salidas)
    
    if w2_val > 0.0001:
        growth_rate = (w1_val - w2_val) / w2_val
    else:
        growth_rate = 0.0
        
    growth_rate = max(min_growth, min(max_growth, growth_rate))
    
    return ddp, frecuencia, growth_rate


@bp.route('/api/producto/<int:producto_id>/update-max-stock', methods=['POST'])
def api_update_product_max_stock(producto_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    data = request.get_json() or {}
    val = data.get('dias_max_stock')
    
    if val is not None and val != '':
        try:
            val = int(val)
            if val < 0:
                return jsonify({'ok': False, 'error': 'El valor debe ser un número entero no negativo'}), 400
        except (ValueError, TypeError):
            val = None
    else:
        val = None

    conn = get_db_connection()
    try:
        conn.execute("UPDATE productos SET dias_max_stock = %s WHERE id = %s", (val, producto_id))
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Días máximos de stock actualizados correctamente'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/parametro', methods=['POST'])
def api_guardar_parametro_negocio(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    data = request.get_json() or {}
    nombre = data.get('nombre', '').strip()
    valor = data.get('valor', '')
    
    if not nombre:
        return jsonify({'ok': False, 'error': 'Falta nombre del parametro'}), 400
    
    conn = get_db_connection()
    try:
        existing = conn.execute("""
            SELECT id, tipo FROM parametros_sistema 
            WHERE nombre = %s AND negocio_id = %s
        """, (nombre, negocio_id)).fetchone()
        
        es_booleano = (existing and existing[1] == 'booleano') or str(valor).lower() in ('true', 'false')
        
        if es_booleano:
            valor_bool = str(valor).lower() == 'true'
            if existing:
                conn.execute("""
                    UPDATE parametros_sistema 
                    SET valor_booleano = %s, valor_texto = NULL, fecha_actualizacion = NOW()
                    WHERE nombre = %s AND negocio_id = %s
                """, (str(valor_bool), nombre, negocio_id))
            else:
                conn.execute("""
                    INSERT INTO parametros_sistema (nombre, valor_booleano, tipo, descripcion, negocio_id, fecha_actualizacion)
                    VALUES (%s, %s, 'booleano', NULL, %s, NOW())
                """, (nombre, str(valor_bool), negocio_id))
        else:
            if existing:
                conn.execute("""
                    UPDATE parametros_sistema 
                    SET valor_texto = %s, fecha_actualizacion = NOW()
                    WHERE nombre = %s AND negocio_id = %s
                """, (str(valor), nombre, negocio_id))
            else:
                conn.execute("""
                    INSERT INTO parametros_sistema (nombre, valor_texto, tipo, descripcion, negocio_id, fecha_actualizacion)
                    VALUES (%s, %s, 'numerico', NULL, %s, NOW())
                """, (nombre, str(valor), negocio_id))
        
        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Parametro guardado'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/compras/sugerencias')
def api_compras_sugerencias(negocio_id):
    import datetime
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
        
    try:
        dias_historial = int(request.args.get('dias_historial', 30))
        dias_defecto = int(request.args.get('dias_defecto', 7))
        growth_window = int(request.args.get('growth_window', 7))
        max_growth = float(request.args.get('max_growth', 100.0)) / 100.0
        min_growth = float(request.args.get('min_growth', -50.0)) / 100.0
        dias_stock_max_global = int(request.args.get('dias_stock_max_global', 15))
        dias_entrega_global = int(request.args.get('dias_entrega_global', 2))
        usar_dias_con_stock_param = request.args.get('usar_dias_con_stock')
    except (ValueError, TypeError):
        dias_historial = 30
        dias_defecto = 7
        growth_window = 7
        max_growth = 1.0
        min_growth = -0.5
        dias_stock_max_global = 15
        dias_entrega_global = 2
        usar_dias_con_stock_param = None
        
    conn = get_db_connection()
    try:
        # Leer parametros globales desde BD por negocio
        param_row = conn.execute("""
            SELECT valor_texto FROM parametros_sistema 
            WHERE nombre = 'inventario_stock_max_dias' AND negocio_id = %s
        """, (negocio_id,)).fetchone()
        if param_row and param_row[0]:
            dias_stock_max_global = int(param_row[0])
        
        param_entrega = conn.execute("""
            SELECT valor_texto FROM parametros_sistema 
            WHERE nombre = 'inventario_dias_entrega' AND negocio_id = %s
        """, (negocio_id,)).fetchone()
        if param_entrega and param_entrega[0]:
            dias_entrega_global = int(param_entrega[0])

        param_dias_stock = conn.execute("""
            SELECT valor_booleano FROM parametros_sistema 
            WHERE nombre = 'inventario_usar_dias_con_stock' AND negocio_id = %s
        """, (negocio_id,)).fetchone()
        if usar_dias_con_stock_param is not None:
            usar_dias_con_stock = usar_dias_con_stock_param.lower() == 'true'
        elif param_dias_stock and param_dias_stock[0]:
            usar_dias_con_stock = param_dias_stock[0].lower() == 'true'
        else:
            usar_dias_con_stock = True

        # 1. Obtener todos los productos comprados (sin receta)
        purchased_products = conn.execute("""
            SELECT p.id, p.nombre, COALESCE(p.costo, 0) AS costo, p.dias_max_stock, COALESCE(s.stock, 0) AS stock_actual,
                   COALESCE(p.iva_pct, 0) AS iva_pct
            FROM productos p
            LEFT JOIN saldos_inventario s ON s.producto_id = p.id AND s.negocio_id = %s AND s.bodega = 1
            WHERE p.negocio_id = %s AND p.disponible = TRUE
              AND p.id NOT IN (SELECT DISTINCT producto_id FROM tarjeta_estandar)
            ORDER BY p.nombre
        """, (negocio_id, negocio_id)).fetchall()
        
        proveedores_map = {}
        
        for prod in purchased_products:
            p_id = prod['id']
            p_nombre = prod['nombre']
            p_costo = float(prod['costo'])
            p_dias_max_stock = prod['dias_max_stock']
            stock_actual = float(prod['stock_actual'])
            
            # Calcular demanda, ciclo y tendencia
            ddp, frecuencia, growth_rate = _calcular_demanda_y_ciclo(
                conn, negocio_id, p_id, stock_actual,
                dias_historial, dias_defecto, growth_window, max_growth, min_growth,
                usar_dias_con_stock=usar_dias_con_stock
            )
            
            if ddp < 0.0001:
                # Omitir productos sin consumo
                continue
                
            demanda_proyectada = ddp * (1.0 + growth_rate)
            
            # Obtener cotizaciones activas para este producto (globales)
            quotes = conn.execute("""
                SELECT c.id, c.tercero_id, t.nombre AS proveedor_nombre, t.telefono AS proveedor_telefono,
                       COALESCE(c.unidades_item, 1) AS unidades_item, COALESCE(c.precio, 0) AS precio,
                       COALESCE(c.descripcion_presentacion, 'Unidad') AS descripcion_presentacion,
                       c.presentacion_id
                FROM cotizaciones_compras c
                JOIN terceros t ON t.id = c.tercero_id
                WHERE c.item_id = %s
                  AND (c.fecha_vencimiento >= CURRENT_DATE OR c.fecha_vencimiento IS NULL)
                ORDER BY (c.precio / COALESCE(c.unidades_item, 1)) ASC
            """, (p_id,)).fetchall()
            
            # Obtener el último proveedor histórico como respaldo
            last_purchase = conn.execute("""
                SELECT m.proveedor_id, m.proveedor_nombre, t.telefono AS proveedor_telefono
                FROM movimientos_inventario m
                LEFT JOIN terceros t ON t.id = m.proveedor_id
                WHERE m.negocio_id = %s AND m.producto_id = %s AND m.tipo = 'entrada' AND m.proveedor_id IS NOT NULL
                ORDER BY m.id DESC LIMIT 1
            """, (negocio_id, p_id)).fetchone()
            
            # Determinar días máximos de stock para este producto
            dias_max = p_dias_max_stock if p_dias_max_stock is not None else dias_stock_max_global
            max_comprar = demanda_proyectada * dias_max
            
            # Clasificar cotizaciones entre elegibles y descartadas
            eligible_quotes = []
            discarded_quotes = []
            
            for q in quotes:
                unidades = float(q['unidades_item'])
                if unidades <= max_comprar or max_comprar <= 0.0001:
                    eligible_quotes.append(q)
                else:
                    discarded_quotes.append(q)
                    
            # Seleccionar la cotización y proveedor correspondientes
            selected_quote = None
            oportunidad_ahorro = None
            
            if eligible_quotes:
                selected_quote = eligible_quotes[0]
            elif discarded_quotes:
                mejor_descartada = discarded_quotes[0]
                unidades_desc = float(mejor_descartada['unidades_item'])
                precio_desc = float(mejor_descartada['precio'])
                
                # Calcular cuántos días de stock se requieren para desbloquearla
                dias_necesarios = int(round(unidades_desc / demanda_proyectada)) if demanda_proyectada > 0 else 999
                costo_unitario_desc = precio_desc / unidades_desc
                
                oportunidad_ahorro = {
                    'proveedor_nombre': mejor_descartada['proveedor_nombre'],
                    'descripcion_presentacion': mejor_descartada['descripcion_presentacion'],
                    'unidades_item': unidades_desc,
                    'costo_unitario': round(costo_unitario_desc, 2),
                    'dias_necesarios': dias_necesarios
                }
                
            # Establecer proveedor y costo unitario sugeridos
            prov_id = 0
            prov_nombre = "Sin Proveedor Registrado"
            prov_telefono = ""
            costo_unitario = p_costo
            presentacion_nombre = "Unidad"
            unidades_presentacion = 1.0
            precio_presentacion = p_costo
            
            if selected_quote:
                prov_id = selected_quote['tercero_id']
                prov_nombre = selected_quote['proveedor_nombre']
                prov_telefono = selected_quote['proveedor_telefono'] or ""
                unidades_presentacion = float(selected_quote['unidades_item'])
                precio_presentacion = float(selected_quote['precio'])
                costo_unitario = precio_presentacion / unidades_presentacion
                presentacion_nombre = selected_quote['descripcion_presentacion']
            elif last_purchase:
                prov_id = last_purchase['proveedor_id']
                prov_nombre = last_purchase['proveedor_nombre']
                prov_telefono = last_purchase['proveedor_telefono'] or ""
                
            # Calcular cantidad a comprar
            cantidad_comprar_neta = max_comprar - stock_actual
            if cantidad_comprar_neta < 0.0001:
                continue
            cantidad_comprar = cantidad_comprar_neta
                
            # Convertir cantidad sugerida a paquetes
            import math
            paquetes = math.ceil(cantidad_comprar / unidades_presentacion) if unidades_presentacion > 0 else 0
            cantidad_comprar_unidades = paquetes * unidades_presentacion
            total_costo = paquetes * precio_presentacion
            
            # Cobertura y fecha límite
            if stock_actual <= 0.0001:
                cobertura_dias = 0.0
            elif demanda_proyectada < 0.0001:
                cobertura_dias = 9999.0
            else:
                cobertura_dias = stock_actual / demanda_proyectada
                
            dias_para_reorden = cobertura_dias - dias_entrega_global
            
            if dias_para_reorden <= 0.0001:
                fecha_limite = "Inmediato"
            elif dias_para_reorden == 9999.0:
                fecha_limite = "Sin consumo"
            else:
                dias_red = int(round(dias_para_reorden))
                fecha_limite = (datetime.date.today() + datetime.timedelta(days=dias_red)).strftime('%d-%b-%Y')
                
            if prov_id not in proveedores_map:
                proveedores_map[prov_id] = {
                    'proveedor_id': prov_id,
                    'proveedor_nombre': prov_nombre,
                    'proveedor_telefono': prov_telefono,
                    'total_compras': 0.0,
                    'fecha_limite': 'Sin límite',
                    'fecha_limite_comparable': 99999.0,
                    'productos': []
                }
                
            item_data = {
                'producto_id': p_id,
                'producto_nombre': p_nombre,
                'stock_actual': round(stock_actual, 2),
                'demanda_diaria': round(ddp, 3),
                'demanda_proyectada': round(demanda_proyectada, 3),
                'frecuencia_dias': int(frecuencia),
                'growth_rate_pct': round(growth_rate * 100, 1),
                'dias_max_stock': p_dias_max_stock,
                'dias_max_stock_aplicado': dias_max,
                'cobertura_dias': round(cobertura_dias, 1),
                'dias_entrega_global': dias_entrega_global,
                'fecha_limite': fecha_limite,
                'cantidad_sugerida_unidades': round(cantidad_comprar_unidades, 2),
                'presentacion_nombre': presentacion_nombre,
                'unidades_presentacion': unidades_presentacion,
                'paquetes_sugeridos': paquetes,
                'costo_unitario': round(costo_unitario, 2),
                'precio_presentacion': round(precio_presentacion, 2),
                'total_costo': round(total_costo, 2),
                'oportunidad_ahorro': oportunidad_ahorro,
                'iva_pct': float(prod['iva_pct'] or 0.0),
                'presentacion_id': selected_quote['presentacion_id'] if (selected_quote and selected_quote['presentacion_id']) else None
            }
            
            proveedores_map[prov_id]['productos'].append(item_data)
            proveedores_map[prov_id]['total_compras'] += total_costo
            
            if fecha_limite == 'Inmediato':
                proveedores_map[prov_id]['fecha_limite'] = 'Inmediato'
                proveedores_map[prov_id]['fecha_limite_comparable'] = -1.0
            elif fecha_limite != 'Sin consumo':
                dias_num = dias_para_reorden
                if dias_num < proveedores_map[prov_id]['fecha_limite_comparable']:
                    proveedores_map[prov_id]['fecha_limite_comparable'] = dias_num
                    proveedores_map[prov_id]['fecha_limite'] = fecha_limite
                    
        proveedores_lista = list(proveedores_map.values())
        
        for p in proveedores_lista:
            p['total_compras'] = round(p['total_compras'], 2)
            p['productos'].sort(key=lambda x: x['cobertura_dias'])
            
        proveedores_lista.sort(key=lambda x: x['fecha_limite_comparable'])
        
        return jsonify({
            'ok': True,
            'proveedores': proveedores_lista,
            'parametros': {
                'dias_stock_max_global': dias_stock_max_global,
                'dias_entrega_global': dias_entrega_global,
                'usar_dias_con_stock': usar_dias_con_stock
            }
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# INVENTARIO DISTRIBUIDO — Configuración y endpoints
# ═══════════════════════════════════════════════════════════════════════════════

_PARAM_DEFAULTS_INV_DIST = {
    'inv_distribuido_activo':              {'tipo': 'booleano', 'valor': 'false', 'desc': 'Activa inventario distribuido por ítems'},
    'inv_distribuido_dias_ciclo':          {'tipo': 'numerico', 'valor': '30',   'desc': 'Días de duración del ciclo de conteo'},
    'inv_distribuido_reiniciar':           {'tipo': 'booleano', 'valor': 'false', 'desc': 'Reiniciar ciclo automáticamente al terminar'},
    'inv_distribuido_recordar_min':        {'tipo': 'numerico', 'valor': '15',   'desc': 'Minutos para recordar al usuario que canceló'},
    'inv_distribuido_orden':               {'tipo': 'texto',   'valor': 'valor_rotacion', 'desc': 'Orden de prioridad: valor / rotacion / valor_rotacion'},
    'inv_distribuido_horario_inicio':      {'tipo': 'texto',   'valor': '08:00', 'desc': 'Hora inicio permitida para conteos'},
    'inv_distribuido_horario_fin':         {'tipo': 'texto',   'valor': '17:00', 'desc': 'Hora fin permitida para conteos'},
    'inv_distribuido_dias_semana':         {'tipo': 'texto',   'valor': '1,2,3,4,5', 'desc': 'Días hábiles (1=Lun..7=Dom)'},
    'inv_distribuido_modulos':             {'tipo': 'texto',   'valor': 'produccion,caja,restaurantes', 'desc': 'Módulos donde se invoca el conteo'},
    'inv_distribuido_pausa_seg':          {'tipo': 'numerico', 'valor': '30',   'desc': 'Segundos de pausa antes de mostrar modal'},
}


def _sembrar_parametros_inv_dist(conn, negocio_id):
    """Inserta parámetros default de inventario distribuido si no existen."""
    for nombre, cfg in _PARAM_DEFAULTS_INV_DIST.items():
        exists = conn.execute(
            "SELECT 1 FROM parametros_sistema WHERE nombre = %s AND negocio_id = %s",
            (nombre, negocio_id)
        ).fetchone()
        if not exists:
            if cfg['tipo'] == 'booleano':
                conn.execute("""
                    INSERT INTO parametros_sistema (nombre, valor_numerico, valor_texto, valor_booleano, tipo, descripcion, negocio_id, fecha_actualizacion)
                    VALUES (%s, NULL, NULL, %s, 'booleano', %s, %s, NOW())
                """, (nombre, cfg['valor'].lower(), cfg['desc'], negocio_id))
            else:
                conn.execute("""
                    INSERT INTO parametros_sistema (nombre, valor_numerico, valor_texto, valor_booleano, tipo, descripcion, negocio_id, fecha_actualizacion)
                    VALUES (%s, %s, NULL, NULL, %s, %s, %s, NOW())
                """, (nombre, cfg['valor'], cfg['tipo'], cfg['desc'], negocio_id))


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/config', methods=['GET'])
def inv_dist_config_get(negocio_id):
    """Retorna la configuración de inventario distribuido para un negocio."""
    try:
        conn = get_db_connection()
        _sembrar_parametros_inv_dist(conn, negocio_id)
        conn.commit()
        rows = conn.execute("""
            SELECT nombre, valor_numerico, valor_booleano, tipo, descripcion
            FROM parametros_sistema
            WHERE nombre LIKE 'inv_distribuido%%' AND negocio_id = %s
        """, (negocio_id,)).fetchall()
        config = {}
        for r in rows:
            val = r['valor_booleano'] if r['tipo'] == 'booleano' else r['valor_numerico']
            config[r['nombre']] = {'valor': val, 'tipo': r['tipo'], 'descripcion': r['descripcion']}
        conn.close()
        return jsonify({'ok': True, 'config': config})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/config', methods=['POST'])
def inv_dist_config_set(negocio_id):
    """Guarda configuración de inventario distribuido."""
    try:
        data = request.get_json() or {}
        conn = get_db_connection()
        for nombre, valor in data.items():
            if not nombre.startswith('inv_distribuido'):
                continue
            cfg = _PARAM_DEFAULTS_INV_DIST.get(nombre)
            if not cfg:
                continue
            existing = conn.execute(
                "SELECT 1 FROM parametros_sistema WHERE nombre = %s AND negocio_id = %s",
                (nombre, negocio_id)
            ).fetchone()
            if cfg['tipo'] == 'booleano':
                val_str = str(valor).lower()
                if existing:
                    conn.execute("UPDATE parametros_sistema SET valor_booleano = %s, fecha_actualizacion = NOW() WHERE nombre = %s AND negocio_id = %s",
                                 (val_str, nombre, negocio_id))
                else:
                    conn.execute("INSERT INTO parametros_sistema (nombre, valor_numerico, valor_texto, valor_booleano, tipo, descripcion, negocio_id, fecha_actualizacion) VALUES (%s, NULL, NULL, %s, 'booleano', %s, %s, NOW())",
                                 (nombre, val_str, cfg['desc'], negocio_id))
            else:
                if existing:
                    conn.execute("UPDATE parametros_sistema SET valor_numerico = %s, fecha_actualizacion = NOW() WHERE nombre = %s AND negocio_id = %s",
                                 (str(valor), nombre, negocio_id))
                else:
                    conn.execute("INSERT INTO parametros_sistema (nombre, valor_numerico, valor_texto, valor_booleano, tipo, descripcion, negocio_id, fecha_actualizacion) VALUES (%s, %s, NULL, NULL, %s, %s, %s, NOW())",
                                 (nombre, str(valor), cfg['tipo'], cfg['desc'], negocio_id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'mensaje': 'Configuración guardada'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/siguiente', methods=['GET'])
def inv_dist_siguiente(negocio_id):
    """Retorna el siguiente ítem a contar según prioridad."""
    try:
        conn = get_db_connection()
        usuario_id = request.args.get('usuario_id', type=int)

        # Obtener ciclo activo
        ciclo = conn.execute("""
            SELECT MIN(ciclo_inicio) AS inicio, MAX(ciclo_fin) AS fin
            FROM inventario_distribuido_estado
            WHERE negocio_id = %s AND ciclo_inicio IS NOT NULL
        """, (negocio_id,)).fetchone()

        ciclo_inicio = None
        if ciclo and ciclo['inicio']:
            ciclo_inicio = ciclo['inicio']

        # Obtener configuración
        orden_row = conn.execute(
            "SELECT valor_texto FROM parametros_sistema WHERE nombre = 'inv_distribuido_orden' AND negocio_id = %s",
            (negocio_id,)
        ).fetchone()
        orden = orden_row['valor_texto'] if orden_row else 'valor_rotacion'

        # Construir ORDER BY según prioridad
        order_sql = {
            'valor': 'p.precio * COALESCE(si.stock, 0) DESC',
            'rotacion': '(SELECT COUNT(*) FROM movimientos_inventario m2 WHERE m2.producto_id = p.id AND m2.fecha >= NOW() - INTERVAL \'30 days\') DESC',
            'valor_rotacion': '(p.precio * COALESCE(si.stock, 0)) * (SELECT COUNT(*) FROM movimientos_inventario m2 WHERE m2.producto_id = p.id AND m2.fecha >= NOW() - INTERVAL \'30 days\') DESC',
        }.get(orden, 'p.precio * COALESCE(si.stock, 0) DESC')

        # Buscar siguiente ítem pendiente, excluyendo los que el usuario ya saltó en este ciclo
        params = [negocio_id]
        excl = ''
        if usuario_id:
            excl = "AND (est.estado IS NULL OR est.estado != 'saltado' OR est.usuario_id != %s OR est.ciclo_inicio IS NOT DISTINCT FROM %s)"
            params.extend([usuario_id, ciclo_inicio])

        row = conn.execute(f"""
            SELECT p.id AS producto_id, p.nombre, p.categoria, p.precio, p.codigo_barra,
                   COALESCE(si.stock, 0) AS stock_sistema
            FROM productos p
            LEFT JOIN saldos_inventario si ON si.producto_id = p.id AND si.negocio_id = p.negocio_id AND si.bodega = 1
            LEFT JOIN inventario_distribuido_estado est ON est.producto_id = p.id AND est.negocio_id = p.negocio_id
                {'AND est.ciclo_inicio IS NOT DISTINCT FROM %s' if ciclo_inicio else ''}
            WHERE p.negocio_id = %s AND p.disponible = TRUE
                AND (est.estado IS NULL OR est.estado = 'saltado')
                {excl}
            ORDER BY {order_sql}
            LIMIT 1
        """, params + ([ciclo_inicio] if ciclo_inicio else []) + [negocio_id]).fetchone()

        conn.close()
        if not row:
            return jsonify({'ok': True, 'item': None, 'mensaje': 'No hay ítems pendientes'})
        return jsonify({
            'ok': True,
            'item': {
                'producto_id': row['producto_id'],
                'nombre': row['nombre'],
                'categoria': row['categoria'],
                'precio': float(row['precio'] or 0),
                'codigo_barra': row['codigo_barra'],
            }
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/conteo', methods=['POST'])
def inv_dist_conteo(negocio_id):
    """Registra un conteo físico (el operario ingresa la cantidad)."""
    try:
        data = request.get_json() or {}
        producto_id = data.get('producto_id')
        cantidad_fisica = data.get('cantidad_fisica')
        usuario_id = data.get('usuario_id')
        usuario_nombre = data.get('usuario_nombre', '')

        if not producto_id or cantidad_fisica is None:
            return jsonify({'ok': False, 'error': 'Faltan datos'}), 400

        conn = get_db_connection()

        # Stock actual del sistema (NO se expone al operario)
        sal = conn.execute(
            "SELECT stock FROM saldos_inventario WHERE negocio_id = %s AND producto_id = %s AND bodega = 1",
            (negocio_id, producto_id)
        ).fetchone()
        stock_sistema = float(sal['stock'] or 0) if sal else 0
        diff = float(cantidad_fisica) - stock_sistema

        # Obtener ciclo activo
        ciclo = conn.execute(
            "SELECT MIN(ciclo_inicio) AS inicio FROM inventario_distribuido_estado WHERE negocio_id = %s AND ciclo_inicio IS NOT NULL",
            (negocio_id,)
        ).fetchone()
        ciclo_inicio = ciclo['inicio'] if ciclo and ciclo['inicio'] else None

        # Upsert estado
        exists = conn.execute(
            "SELECT id FROM inventario_distribuido_estado WHERE negocio_id = %s AND producto_id = %s AND ciclo_inicio IS NOT DISTINCT FROM %s",
            (negocio_id, producto_id, ciclo_inicio)
        ).fetchone()

        if exists:
            conn.execute("""
                UPDATE inventario_distribuido_estado
                SET estado = 'contado', fecha_ultimo_conteo = NOW(), conteos_total = conteos_total + 1,
                    quién_contó = %s, usuario_id = %s
                WHERE id = %s
            """, (usuario_nombre, usuario_id, exists['id']))
        else:
            conn.execute("""
                INSERT INTO inventario_distribuido_estado (negocio_id, producto_id, usuario_id, estado, fecha_ultimo_conteo, conteos_total, quién_contó, ciclo_inicio)
                VALUES (%s, %s, %s, 'contado', NOW(), 1, %s, %s)
            """, (negocio_id, producto_id, usuario_id, usuario_nombre, ciclo_inicio))

        # Si hay diferencia, registrar ajuste
        ajuste_monto = 0
        if abs(diff) > 0.001:
            _mov_directo(conn, negocio_id, producto_id, diff, 'ajuste', usuario_nombre)
            ajuste_monto = diff * float(conn.execute(
                "SELECT costo FROM productos WHERE id = %s", (producto_id,)
            ).fetchone()['costo'] or 0)

        conn.commit()
        conn.close()
        return jsonify({
            'ok': True,
            'diferencia': diff,
            'ajuste_monto': round(ajuste_monto, 2),
            'mensaje': f'Conteo registrado. Diferencia: {diff}'
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/saltar', methods=['POST'])
def inv_dist_saltar(negocio_id):
    """El operario salta un ítem (reporta como problemático)."""
    try:
        data = request.get_json() or {}
        producto_id = data.get('producto_id')
        usuario_id = data.get('usuario_id')
        usuario_nombre = data.get('usuario_nombre', '')
        motivo = data.get('motivo', '')

        if not producto_id:
            return jsonify({'ok': False, 'error': 'Faltan datos'}), 400

        conn = get_db_connection()
        ciclo = conn.execute(
            "SELECT MIN(ciclo_inicio) AS inicio FROM inventario_distribuido_estado WHERE negocio_id = %s AND ciclo_inicio IS NOT NULL",
            (negocio_id,)
        ).fetchone()
        ciclo_inicio = ciclo['inicio'] if ciclo and ciclo['inicio'] else None

        exists = conn.execute(
            "SELECT id FROM inventario_distribuido_estado WHERE negocio_id = %s AND producto_id = %s AND ciclo_inicio IS NOT DISTINCT FROM %s",
            (negocio_id, producto_id, ciclo_inicio)
        ).fetchone()

        if exists:
            conn.execute("""
                UPDATE inventario_distribuido_estado
                SET estado = 'saltado', usuario_id = %s, quién_contó = %s, fecha_ultimo_conteo = NOW()
                WHERE id = %s
            """, (usuario_id, usuario_nombre, exists['id']))
        else:
            conn.execute("""
                INSERT INTO inventario_distribuido_estado (negocio_id, producto_id, usuario_id, estado, quién_contó, fecha_ultimo_conteo, ciclo_inicio)
                VALUES (%s, %s, %s, 'saltado', %s, NOW(), %s)
            """, (negocio_id, producto_id, usuario_id, usuario_nombre, ciclo_inicio))

        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'mensaje': 'Ítem saltado'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/cancelar', methods=['POST'])
def inv_dist_cancelar(negocio_id):
    """El operario cancela la sesión de conteo."""
    try:
        data = request.get_json() or {}
        usuario_id = data.get('usuario_id')
        recordar_min = data.get('recordar_min', 15)

        # Solo retorna OK — el frontend deja de mostrar modales por el tiempo configurado
        return jsonify({'ok': True, 'mensaje': f'Sesión cancelada. Recordar en {recordar_min} minutos'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/inventario/<int:negocio_id>/inv-dist/resumen', methods=['GET'])
def inv_dist_resumen(negocio_id):
    """Resumen del ciclo para el parametrizador."""
    try:
        conn = get_db_connection()
        ciclo = conn.execute(
            "SELECT MIN(ciclo_inicio) AS inicio FROM inventario_distribuido_estado WHERE negocio_id = %s AND ciclo_inicio IS NOT NULL",
            (negocio_id,)
        ).fetchone()
        ciclo_inicio = ciclo['inicio'] if ciclo and ciclo['inicio'] else None

        # Total productos del negocio
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM productos WHERE negocio_id = %s AND disponible = TRUE",
            (negocio_id,)
        ).fetchone()['n']

        # Estados
        estados = conn.execute("""
            SELECT estado, COUNT(*) AS n
            FROM inventario_distribuido_estado
            WHERE negocio_id = %s AND ciclo_inicio IS NOT DISTINCT FROM %s
            GROUP BY estado
        """, (negocio_id, ciclo_inicio)).fetchall()
        resumen_estados = {r['estado']: r['n'] for r in estados}

        # Detalle items contados
        items = conn.execute("""
            SELECT est.producto_id, p.nombre, p.categoria, est.estado, est.fecha_ultimo_conteo,
                   est.quién_contó, est.conteos_total,
                   COALESCE(si.stock, 0) AS stock_sistema
            FROM inventario_distribuido_estado est
            JOIN productos p ON p.id = est.producto_id
            LEFT JOIN saldos_inventario si ON si.producto_id = est.producto_id AND si.negocio_id = est.negocio_id AND si.bodega = 1
            WHERE est.negocio_id = %s AND est.ciclo_inicio IS NOT DISTINCT FROM %s
            ORDER BY est.fecha_ultimo_conteo DESC
        """, (negocio_id, ciclo_inicio)).fetchall()

        conn.close()
        return jsonify({
            'ok': True,
            'ciclo_inicio': str(ciclo_inicio) if ciclo_inicio else None,
            'total_productos': total,
            'resumen': {
                'contados': resumen_estados.get('contado', 0),
                'saltados': resumen_estados.get('saltado', 0),
                'pendientes': total - resumen_estados.get('contado', 0) - resumen_estados.get('saltado', 0),
            },
            'items': [{
                'producto_id': it['producto_id'],
                'nombre': it['nombre'],
                'categoria': it['categoria'],
                'estado': it['estado'],
                'fecha': str(it['fecha_ultimo_conteo']) if it['fecha_ultimo_conteo'] else None,
                'quien': it['quién_contó'],
                'stock_sistema': float(it['stock_sistema'] or 0),
                'conteos_total': it['conteos_total'],
            } for it in items]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

