from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from ..db import get_db_connection
from decimal import Decimal
from datetime import date

try:
    from .contabilidad import _ejecutar_asiento_costo_mov as _asiento_costo_mov
    from .contabilidad import _ejecutar_asiento_produccion as _asiento_produccion
    from .contabilidad import _ejecutar_asiento_automatico as _asiento_auto
except ImportError:
    _asiento_costo_mov = None
    _asiento_produccion = None
    _asiento_auto = None

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
                 producto_padre_id=None):
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

    nombre_prod = conn.execute("SELECT nombre FROM productos WHERE id=%s", (producto_id,)).fetchone()

    conn.execute("""
        INSERT INTO movimientos_inventario
            (negocio_id, producto_id, nombre_producto, tipo, motivo,
             cantidad, stock_anterior, stock_nuevo, registrado_por, notas,
             valor_unitario, valor_total, costo_und, referencia_id, referencia_tipo,
             tipo_documento, documento_numero, documento_fecha, proveedor_id,
             proveedor_nombre, iva_total, documento_total, iva_pct, iva_valor,
             producto_padre_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        negocio_id, producto_id,
        nombre_prod['nombre'] if nombre_prod else '',
        tipo, motivo,
        float(cantidad), float(stock_ant), float(stock_nuevo),
        registrado_por, notas,
        float(valor_unitario) if valor_unitario else None,
        float(cantidad * Decimal(str(valor_unitario))) if valor_unitario else None,
        float(costo_nuevo),
        referencia_id, referencia_tipo,
        tipo_documento, documento_numero, documento_fecha, proveedor_id,
        proveedor_nombre,
        float(iva_total) if iva_total is not None else None,
        float(documento_total) if documento_total is not None else None,
        float(iva_pct) if iva_pct is not None else 0.0,
        float(iva_valor) if iva_valor is not None else 0.0,
        producto_padre_id
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

    # Asiento COGS automático en salidas por venta (best-effort, no bloquea)
    if tipo == 'salida' and motivo == 'venta' and _asiento_costo_mov:
        try:
            _asiento_costo_mov(conn, negocio_id, producto_id,
                               float(cantidad), float(costo_ant),
                               registrado_por=registrado_por)
        except Exception as _e:
            print(f'[cont] costo_mov prod={producto_id}: {_e}')


def _aplicar_tarjeta(conn, negocio_id, producto_id, cantidad, tipo, motivo,
                     registrado_por, valor_unitario=None, notas=None, bodega=1,
                     referencia_id=None, referencia_tipo=None,
                     tipo_documento=None, documento_numero=None,
                     documento_fecha=None, proveedor_id=None,
                     proveedor_nombre=None, iva_total=None,
                     documento_total=None, iva_pct=None, iva_valor=None):
    """Aplica entrada o salida según tarjeta estándar. Sin tarjeta → 1:1 sobre sí mismo."""
    componentes = conn.execute(
        "SELECT componente_id, cantidad FROM tarjeta_estandar WHERE producto_id = %s",
        (producto_id,)
    ).fetchall()

    if not componentes:
        componentes = [{'componente_id': producto_id, 'cantidad': Decimal('1')}]

    cantidad = Decimal(str(cantidad))
    for comp in componentes:
        cant_comp = Decimal(str(comp['cantidad'])) * cantidad
        padre_id = producto_id if comp['componente_id'] != producto_id else None
        _mov_directo(conn, negocio_id, comp['componente_id'], cant_comp, tipo, motivo,
                     registrado_por, valor_unitario, notas, bodega,
                     referencia_id, referencia_tipo, tipo_documento,
                     documento_numero, documento_fecha, proveedor_id,
                     proveedor_nombre, iva_total, documento_total,
                     iva_pct, iva_valor, producto_padre_id=padre_id)


def _registrar_entrada_inventario(conn, negocio_id, data, usuario_id):
    from datetime import datetime
    lineas = data.get('lineas', [])
    motivo = data.get('motivo', 'compra')
    notas = _txt(data.get('notes') or data.get('notas'))
    if not lineas:
        return {'ok': False, 'error': 'Debe agregar al menos una linea'}, 400

    tipo_documento = (_txt(data.get('tipo_documento')) or 'otro').upper()
    documento_numero = (_txt(data.get('documento_numero') or data.get('numero_documento')) or '').upper()
    if not documento_numero:
        td = conn.execute("""
            SELECT id, consecutivo, numero_inicio 
            FROM tipos_documento_negocio 
            WHERE negocio_id = %s AND codigo = %s
        """, (negocio_id, tipo_documento)).fetchone()
        if td:
            num = max((td['consecutivo'] or 0) + 1, (td['numero_inicio'] or 1))
            documento_numero = str(num)
            conn.execute("""
                UPDATE tipos_documento_negocio 
                SET consecutivo = %s 
                WHERE id = %s
            """, (num, td['id']))
        else:
            documento_numero = f"ENT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

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

    # Overwrite check: if document already exists, clean up old records first
    if tipo_documento and documento_numero and proveedor_id:
        existing_movs = conn.execute("""
            SELECT id, producto_id, documento_total, created_at 
            FROM movimientos_inventario
            WHERE negocio_id = %s AND tipo = 'entrada'
              AND tipo_documento = %s AND documento_numero = %s AND proveedor_id = %s
        """, (negocio_id, tipo_documento, documento_numero, proveedor_id)).fetchall()
        
        if existing_movs:
            mov_ids = [m['id'] for m in existing_movs]
            prod_ids_to_recost = {m['producto_id'] for m in existing_movs}
            
            # Delete accounting vouchers linked to this document
            origen_id = f"{tipo_documento}:{documento_numero}"
            origen_tipo = 'inventario_entrada'
            
            comp_rows = conn.execute("""
                SELECT id FROM comprobantes_contables
                WHERE negocio_id = %s AND origen_tipo = %s AND origen_id = %s
            """, (negocio_id, origen_tipo, origen_id)).fetchall()
            
            for c in comp_rows:
                conn.execute("DELETE FROM movimientos_contables WHERE comprobante_id = %s", (c['id'],))
                conn.execute("DELETE FROM comprobantes_contables WHERE id = %s", (c['id'],))
                
            if not comp_rows and existing_movs[0]['documento_total'] is not None:
                fallback_comp = conn.execute("""
                    SELECT id FROM comprobantes_contables
                    WHERE negocio_id = %s AND tipo = 'COMPRA'
                      AND ABS(total_debitos - %s) < 0.05
                      AND fecha = %s::date
                """, (negocio_id, float(existing_movs[0]['documento_total']), existing_movs[0]['created_at'].date())).fetchone()
                if fallback_comp:
                    conn.execute("DELETE FROM movimientos_contables WHERE comprobante_id = %s", (fallback_comp['id'],))
                    conn.execute("DELETE FROM comprobantes_contables WHERE id = %s", (fallback_comp['id'],))
            
            # Delete old movements
            placeholders_m = ', '.join(['%s'] * len(mov_ids))
            conn.execute(f"DELETE FROM movimientos_inventario WHERE id IN ({placeholders_m})", tuple(mov_ids))
            
            # Recost old products temporarily
            for p_id in prod_ids_to_recost:
                _recostear_producto(conn, negocio_id, p_id)

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
            'iva_valor': line_iva_val
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
            iva_valor=ln['iva_valor']
        )

        # Feed/update quote (cotizacion) from this entry if it's a purchase and has a price
        if motivo == 'compra' and proveedor_id and ln['valor_unitario'] and float(ln['valor_unitario']) > 0:
            from datetime import timedelta, date
            vu = float(ln['valor_unitario'])
            f_cot = documento_fecha or date.today()
            f_vence = f_cot + timedelta(days=180)
            
            # Check if a quote exists for this product and provider (origin='compra')
            cot_row = conn.execute("""
                SELECT id FROM cotizaciones_compras
                WHERE negocio_id = %s AND tercero_id = %s AND item_id = %s AND origen = 'compra'
                LIMIT 1
            """, (negocio_id, proveedor_id, ln['producto_id'])).fetchone()
            
            if cot_row:
                conn.execute("""
                    UPDATE cotizaciones_compras
                    SET numero_cotizacion = %s, fecha_cotizacion = %s, fecha_vencimiento = %s,
                        precio = %s, unidades_item = 1, validada_proveedor = TRUE, updated_at = NOW()
                    WHERE id = %s
                """, (documento_numero, f_cot, f_vence, vu, cot_row['id']))
            else:
                conn.execute("""
                    INSERT INTO cotizaciones_compras
                        (negocio_id, numero_cotizacion, tercero_id, item_id, fecha_cotizacion,
                         fecha_vencimiento, descripcion_presentacion, unidades_item, precio,
                         origen, validada_proveedor, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, 'compra', TRUE, NOW())
                """, (negocio_id, documento_numero, proveedor_id, ln['producto_id'], f_cot, f_vence, 'Unidad (entrada)', vu))

    if _asiento_auto:
        try:
            if documento_total > 0:
                _asiento_auto(conn, negocio_id, 'COMPRA',
                              {'subtotal_compra': float(subtotal_compra),
                               'iva_compra': float(iva_total),
                               'total_compra': float(documento_total)},
                              registrado_por=usuario_id,
                              origen_tipo='inventario_entrada',
                              origen_id=f"{tipo_documento}:{documento_numero}")
        except Exception as _e:
            print(f'[cont] compra negocio={negocio_id}: {_e}')

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
        comp_cnt = conn.execute(
            "SELECT COUNT(*) FROM tarjeta_estandar WHERE componente_id = %s",
            (producto_id,)
        ).fetchone()[0]
        if comp_cnt > 0:
            return jsonify({
                'ok': False,
                'error': 'No se puede eliminar el producto porque es componente de la tarjeta estándar de otros productos.'
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
                   m.valor_unitario, m.costo_und, m.notas, m.tipo_documento,
                   m.documento_numero, m.documento_fecha, m.proveedor_id,
                   COALESCE(t.nombre, m.proveedor_nombre) AS proveedor_nombre, m.iva_total, m.documento_total,
                   TO_CHAR(m.created_at, 'DD/MM/YY HH24:MI') AS fecha
            FROM movimientos_inventario m
            LEFT JOIN terceros t ON t.id = m.proveedor_id
            WHERE m.producto_id = %s
            ORDER BY m.created_at DESC LIMIT 300
        """, (producto_id,)).fetchall()
        return jsonify({'ok': True, 'movimientos': [dict(r) for r in rows]})
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
                   m.valor_unitario, m.costo_und, m.notas, m.tipo_documento,
                   m.documento_numero, m.documento_fecha, m.proveedor_id,
                   COALESCE(t.nombre, m.proveedor_nombre) AS proveedor_nombre, m.iva_total, m.documento_total,
                   TO_CHAR(m.created_at, 'DD/MM/YY HH24:MI') AS fecha
            FROM movimientos_inventario m
            LEFT JOIN terceros t ON t.id = m.proveedor_id
            WHERE m.producto_id = %s AND m.negocio_id = %s
            ORDER BY m.created_at DESC LIMIT 300
        """, (producto_id, negocio_id)).fetchall()
        return jsonify({'ok': True, 'movimientos': [dict(r) for r in rows]})
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
    producto_id = data.get('producto_id', type=int) if hasattr(data.get('producto_id'), '__class__') else int(data.get('producto_id', 0))
    cantidad    = Decimal(str(data.get('cantidad', 1)))
    notas       = data.get('notas') or None
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
        prod_token = f"PROD-{int(time.time())}"

        # Salida de cada componente
        for c in componentes:
            cant_comp = Decimal(str(c['cantidad'])) * cantidad
            _mov_directo(conn, negocio_id, c['componente_id'], cant_comp,
                         'salida', 'produccion', session['usuario_id'],
                         notas=notas, referencia_tipo='produccion', referencia_id=prod_token)

        # Entrada del terminado con costo calculado desde componentes
        _mov_directo(conn, negocio_id, producto_id, cantidad,
                     'entrada', 'produccion', session['usuario_id'],
                     valor_unitario=costo_unitario,
                     notas=notas, referencia_tipo='produccion', referencia_id=prod_token)

        # Asiento contable de producción (best-effort, no bloquea)
        if _asiento_produccion:
            try:
                _asiento_produccion(
                    conn, negocio_id, producto_id, float(costo_total), comps_cont,
                    registrado_por=session['usuario_id'],
                    descripcion=f'Producción {producto["nombre"]} x{float(cantidad)}',
                    origen_tipo='produccion',
                    origen_id=prod_token
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
        ORDER BY created_at ASC, id ASC
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
            SELECT DISTINCT tipo_documento, documento_numero, documento_fecha, SUM(valor_total) AS total
            FROM movimientos_inventario
            WHERE negocio_id = %s AND proveedor_id = %s
            GROUP BY tipo_documento, documento_numero, documento_fecha
            ORDER BY documento_fecha DESC, documento_numero DESC
        """, (negocio_id, tercero_id)).fetchall()
        
        documentos = []
        for r in rows_inv:
            documentos.append({
                'tipo_documento': r['tipo_documento'] or 'otro',
                'documento_numero': r['documento_numero'],
                'fecha': r['documento_fecha'].isoformat() if r['documento_fecha'] else None,
                'origen': 'inventario',
                'total': float(r['total'] or 0)
            })
            
        # Query unique documents in pedidos (sales/orders)
        rows_ped = conn.execute("""
            SELECT id, fecha, total, estado
            FROM pedidos
            WHERE id_tercero = %s
            ORDER BY fecha DESC, id DESC
        """, (tercero_id,)).fetchall()
        
        for r in rows_ped:
            documentos.append({
                'tipo_documento': 'pedido_venta',
                'documento_numero': str(r['id']),
                'fecha': r['fecha'].date().isoformat() if r['fecha'] else None,
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
        # 1. Query movimientos_inventario
        sql_inv = """
            SELECT id, producto_id, nombre_producto, tipo, motivo, cantidad, valor_unitario, valor_total, iva_pct, created_at, proveedor_id, proveedor_nombre
            FROM movimientos_inventario
            WHERE negocio_id = %s AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s)
        """
        params_inv = [negocio_id, tipo_doc, num_doc]
        if proveedor_id:
            sql_inv += " AND proveedor_id = %s"
            params_inv.append(int(proveedor_id))
        
        rows_inv = conn.execute(sql_inv, tuple(params_inv)).fetchall()
        items_inventario = [
            {
                'id': r['id'],
                'producto_id': r['producto_id'],
                'nombre_producto': r['nombre_producto'],
                'tipo': r['tipo'],
                'motivo': r['motivo'],
                'cantidad': float(r['cantidad']),
                'valor_unitario': float(r['valor_unitario'] or 0),
                'valor_total': float(r['valor_total'] or 0),
                'iva_pct': float(r['iva_pct'] or 0),
                'created_at': r['created_at'].isoformat() if r['created_at'] else None,
                'proveedor_id': r['proveedor_id'],
                'proveedor_nombre': r['proveedor_nombre']
            } for r in rows_inv
        ]
        
        # 2. Query comprobantes_contables and movimientos_contables
        origen_id = f"{tipo_doc}:{num_doc}"
        comp_row = conn.execute("""
            SELECT id, numero_comprobante, tipo, fecha, descripcion, total_debitos, total_creditos, notas
            FROM comprobantes_contables
            WHERE negocio_id = %s AND (
                (origen_tipo IS NOT NULL AND LOWER(origen_id) = LOWER(%s))
                OR (numero_comprobante ILIKE %s)
            )
            LIMIT 1
        """, (negocio_id, origen_id, f'%{num_doc}%')).fetchone()
        
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
                'asientos': [
                    {
                        'id': e['id'],
                        'cuenta_id': e['cuenta_id'],
                        'cuenta': e['cuenta'],
                        'concepto': e['concepto'],
                        'tipo': e['tipo'],
                        'monto': float(e['monto'] or 0)
                    } for e in entries
                ]
            }
        
        # 3. Query sales (pedidos & pedido_items)
        pedido = None
        pedido_id = None
        try:
            pedido_id = int(num_doc)
        except ValueError:
            pass
        
        if pedido_id:
            ped_row = conn.execute("""
                SELECT p.id, p.fecha, p.total, p.metodo_pago, p.estado, p.notas, p.id_tercero
                FROM pedidos p
                WHERE p.id = %s
                LIMIT 1
            """, (pedido_id,)).fetchone()
            
            if ped_row:
                p_items = conn.execute("""
                    SELECT pi.id, pi.producto_id, pi.nombre_producto, pi.cantidad, pi.precio_unitario
                    FROM pedido_items pi
                    WHERE pi.pedido_id = %s
                """, (pedido_id,)).fetchall()
                
                cliente_nombre = None
                if ped_row['id_tercero']:
                    cli_row = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (ped_row['id_tercero'],)).fetchone()
                    if cli_row:
                        cliente_nombre = cli_row['nombre']
                        
                pedido = {
                    'id': ped_row['id'],
                    'fecha': ped_row['fecha'].isoformat() if ped_row['fecha'] else None,
                    'total': float(ped_row['total'] or 0),
                    'metodo_pago': ped_row['metodo_pago'],
                    'estado': ped_row['estado'],
                    'notas': ped_row['notas'],
                    'cliente_nombre': cliente_nombre,
                    'tercero_id': ped_row['id_tercero'],
                    'items': [
                        {
                            'id': pi['id'],
                            'producto_id': pi['producto_id'],
                            'nombre_producto': pi['nombre_producto'],
                            'cantidad': float(pi['cantidad']),
                            'precio_unitario': float(pi['precio_unitario'] or 0),
                            'subtotal': float(pi['cantidad'] * pi['precio_unitario'])
                        } for pi in p_items
                    ]
                }
        
        return jsonify({
            'ok': True,
            'existe': bool(items_inventario or comprobante or pedido),
            'inventario': items_inventario,
            'contabilidad': comprobante,
            'ventas': pedido
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
        
        # Get inventory movement IDs to be deleted, and their product IDs (for recosteo!)
        sql_inv = """
            SELECT id, producto_id 
            FROM movimientos_inventario
            WHERE negocio_id = %s AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s)
        """
        params_inv = [negocio_id, tipo_doc, num_doc]
        if proveedor_id:
            sql_inv += " AND proveedor_id = %s"
            params_inv.append(int(proveedor_id))
        
        movs = conn.execute(sql_inv, tuple(params_inv)).fetchall()
        mov_ids = [m['id'] for m in movs]
        prod_ids = list({m['producto_id'] for m in movs})
        
        # Delete inventory movements
        if mov_ids:
            placeholders = ','.join(['%s'] * len(mov_ids))
            conn.execute(f"DELETE FROM movimientos_inventario WHERE id IN ({placeholders})", tuple(mov_ids))
            deleted_inventario = len(mov_ids)
        
        # Delete accounting vouchers & entries
        origen_id = f"{tipo_doc}:{num_doc}"
        comp_rows = conn.execute("""
            SELECT id FROM comprobantes_contables
            WHERE negocio_id = %s AND (
                (origen_tipo IS NOT NULL AND LOWER(origen_id) = LOWER(%s))
                OR (numero_comprobante ILIKE %s)
            )
        """, (negocio_id, origen_id, f'%{num_doc}%')).fetchall()
        comp_ids = [c['id'] for c in comp_rows]
        
        if comp_ids:
            placeholders = ','.join(['%s'] * len(comp_ids))
            cur_mc = conn.execute(f"DELETE FROM movimientos_contables WHERE comprobante_id IN ({placeholders})", tuple(comp_ids))
            deleted_contables = cur_mc.rowcount
            cur_cc = conn.execute(f"DELETE FROM comprobantes_contables WHERE id IN ({placeholders})", tuple(comp_ids))
            deleted_comprobantes = cur_cc.rowcount
            
        # Void sales order
        pedido_id = None
        try:
            pedido_id = int(num_doc)
        except ValueError:
            pass
        
        if pedido_id:
            ped_row = conn.execute("SELECT id FROM pedidos WHERE id = %s LIMIT 1", (pedido_id,)).fetchone()
            if ped_row:
                conn.execute("UPDATE pedidos SET estado = 'anulado' WHERE id = %s", (pedido_id,))
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
            'pedido_anulado': pedido_anulado
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
        # 1. Update movimientos_inventario
        conn.execute(f"""
            UPDATE movimientos_inventario 
            SET proveedor_id = %s 
            WHERE proveedor_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # 2. Update cotizaciones
        conn.execute(f"""
            UPDATE cotizaciones_compras 
            SET tercero_id = %s 
            WHERE tercero_id IN ({placeholders})
        """, (principal_id,) + tuple(sobrantes_ids))
        
        # 3. Delete duplicates from terceros
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
        # Check if there is any movement with this key
        if proveedor_id:
            query = """
                SELECT id, producto_id, nombre_producto, cantidad, valor_unitario, iva_pct, notas
                FROM movimientos_inventario
                WHERE negocio_id = %s AND tipo = 'entrada' 
                  AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s) AND proveedor_id = %s
                ORDER BY id
            """
            params = (negocio_id, tipo_doc, num_doc, proveedor_id)
        else:
            query = """
                SELECT id, producto_id, nombre_producto, cantidad, valor_unitario, iva_pct, notas
                FROM movimientos_inventario
                WHERE negocio_id = %s AND tipo = 'entrada' 
                  AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s) AND proveedor_nombre = %s
                ORDER BY id
            """
            params = (negocio_id, tipo_doc, num_doc, proveedor_nombre)
            
        rows = conn.execute(query, params).fetchall()
        if not rows:
            return jsonify({'ok': True, 'existe': False})
            
        # Get notes from first movement
        first_row = conn.execute("""
            SELECT notas FROM movimientos_inventario
            WHERE negocio_id = %s AND tipo = 'entrada' 
              AND LOWER(tipo_documento) = LOWER(%s) AND LOWER(documento_numero) = LOWER(%s) AND (proveedor_id = %s OR proveedor_nombre = %s)
            LIMIT 1
        """, (negocio_id, tipo_doc, num_doc, proveedor_id, proveedor_nombre)).fetchone()
        notes = first_row['notas'] if first_row else ''
            
        return jsonify({
            'ok': True,
            'existe': True,
            'notas': notes,
            'items': [{
                'producto_id': r['producto_id'],
                'nombre_producto': r['nombre_producto'],
                'cantidad': float(r['cantidad']),
                'valor_unitario': float(r['valor_unitario'] or 0),
                'iva_pct': float(r['iva_pct'] or 0),
                'notas': r['notas']
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
