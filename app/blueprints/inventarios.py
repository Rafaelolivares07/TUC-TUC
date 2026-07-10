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
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS iva_total NUMERIC(14,2)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS documento_total NUMERIC(14,2)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS iva_pct NUMERIC(5,2) DEFAULT 0",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS iva_valor NUMERIC(14,2) DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS recargo DECIMAL(10,2) DEFAULT 0",
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS catalogo_id INTEGER",
        "ALTER TABLE comprobantes_contables ADD COLUMN IF NOT EXISTS origen_tipo VARCHAR(50)",
        "ALTER TABLE comprobantes_contables ADD COLUMN IF NOT EXISTS origen_id VARCHAR(100)",
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
                 documento_total=None, iva_pct=None, iva_valor=None):
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
             proveedor_nombre, iva_total, documento_total, iva_pct, iva_valor)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        float(iva_valor) if iva_valor is not None else 0.0
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
        _mov_directo(conn, negocio_id, comp['componente_id'], cant_comp, tipo, motivo,
                     registrado_por, valor_unitario, notas, bodega,
                     referencia_id, referencia_tipo, tipo_documento,
                     documento_numero, documento_fecha, proveedor_id,
                     proveedor_nombre, iva_total, documento_total,
                     iva_pct, iva_valor)


def _registrar_entrada_inventario(conn, negocio_id, data, usuario_id):
    from datetime import datetime
    lineas = data.get('lineas', [])
    motivo = data.get('motivo', 'compra')
    notas = _txt(data.get('notes') or data.get('notas'))
    if not lineas:
        return {'ok': False, 'error': 'Debe agregar al menos una linea'}, 400

    tipo_documento = _txt(data.get('tipo_documento')) or 'otro'
    documento_numero = _txt(data.get('documento_numero') or data.get('numero_documento'))
    if not documento_numero:
        documento_numero = f"ENT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    documento_fecha = _fecha_o_none(data.get('documento_fecha') or data.get('fecha_documento'))
    proveedor_id = _int_o_none(data.get('proveedor_id') or data.get('tercero_id'))
    proveedor_nombre = _txt(data.get('proveedor_nombre'))
    subtotal_compra = Decimal('0')
    iva_total = Decimal('0')
    advertencias = []

    if proveedor_id and not proveedor_nombre:
        prov = conn.execute(
            "SELECT nombre FROM terceros WHERE id = %s",
            (proveedor_id,)
        ).fetchone()
        proveedor_nombre = prov['nombre'] if prov else None
        if not prov:
            return {'ok': False, 'error': 'Proveedor no encontrado'}, 400

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
            SELECT te.componente_id, te.cantidad, p.nombre
            FROM tarjeta_estandar te
            JOIN productos p ON p.id = te.componente_id
            WHERE te.producto_id = %s
        """, (producto_id,)).fetchall()
        return jsonify({'ok': True, 'componentes': [dict(r) for r in rows]})
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
            SELECT id, tipo, motivo, cantidad, stock_anterior, stock_nuevo,
                   valor_unitario, costo_und, notas, tipo_documento,
                   documento_numero, documento_fecha, proveedor_id,
                   proveedor_nombre, iva_total, documento_total,
                   TO_CHAR(created_at, 'DD/MM/YY HH24:MI') AS fecha
            FROM movimientos_inventario
            WHERE producto_id = %s
            ORDER BY created_at DESC LIMIT 300
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
            SELECT id, tipo, motivo, cantidad, stock_anterior, stock_nuevo,
                   valor_unitario, costo_und, notas, tipo_documento,
                   documento_numero, documento_fecha, proveedor_id,
                   proveedor_nombre, iva_total, documento_total,
                   TO_CHAR(created_at, 'DD/MM/YY HH24:MI') AS fecha
            FROM movimientos_inventario
            WHERE producto_id = %s AND negocio_id = %s
            ORDER BY created_at DESC LIMIT 300
        """, (producto_id, negocio_id)).fetchall()
        return jsonify({'ok': True, 'movimientos': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/producto/<int:producto_id>', methods=['POST'])
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
                   COALESCE(s.stock, 0) AS stock_actual
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
        for c in componentes:
            a_consumir  = Decimal(str(c['cant_tarjeta'])) * qty
            stock_actual = Decimal(str(c['stock_actual']))
            suficiente  = stock_actual >= a_consumir
            if not suficiente:
                puede_producir = False
            lineas.append({
                'id':           c['id'],
                'nombre':       c['nombre'],
                'a_consumir':   float(a_consumir),
                'stock_actual': float(stock_actual),
                'suficiente':   suficiente,
            })
        return jsonify({
            'ok': True,
            'producto': producto['nombre'],
            'cantidad': cantidad,
            'puede_producir': puede_producir,
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
            saldo = conn.execute(
                "SELECT COALESCE(stock,0) AS stock, COALESCE(costo_und,0) AS costo_und "
                "FROM saldos_inventario "
                "WHERE negocio_id=%s AND producto_id=%s AND bodega=1",
                (negocio_id, c['componente_id'])
            ).fetchone()
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


# ── UI ─────────────────────────────────────────────────────────────────────────


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
