from flask import Blueprint, jsonify, request, session
from ..db import get_db_connection
from decimal import Decimal

bp = Blueprint('inventarios', __name__)


def _crear_tablas(conn):
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
    ]
    for sql in sqls:
        conn.execute(sql)

    alters = [
        "CREATE INDEX IF NOT EXISTS idx_productos_negocio ON productos(negocio_id)",
        "CREATE INDEX IF NOT EXISTS idx_tarjeta_producto ON tarjeta_estandar(producto_id)",
        "CREATE INDEX IF NOT EXISTS idx_saldos_negocio_producto ON saldos_inventario(negocio_id, producto_id)",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS costo_und NUMERIC(12,4)",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
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
        # Migrar stock actual a saldos_inventario
        conn.execute("""
            INSERT INTO saldos_inventario (negocio_id, producto_id, bodega, stock)
            SELECT t.tercero_id, pt.id, 1, COALESCE(pt.stock, 0)
            FROM productos_tienda pt
            JOIN tiendas t ON t.id = pt.tienda_id
            WHERE t.tercero_id IS NOT NULL AND COALESCE(pt.stock, 0) > 0
            ON CONFLICT DO NOTHING
        """)
    except Exception:
        pass

    conn.commit()


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


def _aplicar_tarjeta(conn, negocio_id, producto_id, cantidad, tipo, motivo,
                     registrado_por, valor_unitario=None, notas=None, bodega=1,
                     referencia_id=None, referencia_tipo=None):
    """
    Aplica entrada o salida según tarjeta estándar.
    tipo: 'entrada' | 'salida'
    valor_unitario: costo unitario del componente — requerido en entradas para calcular costo ponderado.
    Si el producto no tiene tarjeta, se trata como componente de sí mismo (1:1).
    """
    componentes = conn.execute(
        "SELECT componente_id, cantidad FROM tarjeta_estandar WHERE producto_id = %s",
        (producto_id,)
    ).fetchall()

    if not componentes:
        componentes = [{'componente_id': producto_id, 'cantidad': Decimal('1')}]

    signo = Decimal('1') if tipo == 'entrada' else Decimal('-1')
    cantidad = Decimal(str(cantidad))

    for comp in componentes:
        comp_id = comp['componente_id']
        cant_comp = Decimal(str(comp['cantidad'])) * cantidad

        saldo = conn.execute(
            """SELECT stock, costo_und, valor_existencia
               FROM saldos_inventario
               WHERE negocio_id = %s AND producto_id = %s AND bodega = %s""",
            (negocio_id, comp_id, bodega)
        ).fetchone()

        stock_ant   = Decimal(str(saldo['stock']))           if saldo else Decimal('0')
        costo_ant   = Decimal(str(saldo['costo_und']))       if saldo else Decimal('0')
        val_exi_ant = Decimal(str(saldo['valor_existencia'])) if saldo else Decimal('0')

        stock_nuevo = stock_ant + cant_comp * signo

        if tipo == 'entrada' and valor_unitario is not None:
            vu = Decimal(str(valor_unitario))
            costo_nuevo = (val_exi_ant + cant_comp * vu) / stock_nuevo if stock_nuevo > 0 else vu
            val_exi_nuevo = stock_nuevo * costo_nuevo if stock_nuevo > 0 else Decimal('0')
        else:
            costo_nuevo   = costo_ant if stock_nuevo > 0 else Decimal('0')
            val_exi_nuevo = stock_nuevo * costo_nuevo if stock_nuevo > 0 else Decimal('0')

        nombre_prod = conn.execute(
            "SELECT nombre FROM productos WHERE id = %s", (comp_id,)
        ).fetchone()

        conn.execute("""
            INSERT INTO movimientos_inventario
                (negocio_id, producto_id, nombre_producto, tipo, motivo,
                 cantidad, stock_anterior, stock_nuevo, registrado_por, notas,
                 valor_unitario, valor_total, costo_und, referencia_id, referencia_tipo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            negocio_id, comp_id,
            nombre_prod['nombre'] if nombre_prod else '',
            tipo, motivo,
            float(cant_comp), float(stock_ant), float(stock_nuevo),
            registrado_por, notas,
            float(valor_unitario) if valor_unitario else None,
            float(cant_comp * Decimal(str(valor_unitario))) if valor_unitario else None,
            float(costo_nuevo),
            referencia_id, referencia_tipo
        ))

        if saldo:
            conn.execute("""
                UPDATE saldos_inventario
                SET stock=%s, costo_und=%s, valor_existencia=%s, updated_at=NOW()
                WHERE negocio_id=%s AND producto_id=%s AND bodega=%s
            """, (float(stock_nuevo), float(costo_nuevo), float(val_exi_nuevo),
                  negocio_id, comp_id, bodega))
        else:
            conn.execute("""
                INSERT INTO saldos_inventario (negocio_id, producto_id, bodega, stock, costo_und, valor_existencia)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (negocio_id, comp_id, bodega,
                  float(stock_nuevo), float(costo_nuevo), float(val_exi_nuevo)))


# ── Inicialización ─────────────────────────────────────────────────────────────

@bp.before_app_request
def _init_tablas():
    conn = get_db_connection()
    try:
        _crear_tablas(conn)
    finally:
        conn.close()
    _init_tablas.__func__._done = True  # type: ignore
    # Solo correr una vez
    bp.before_app_request_funcs[None].remove(_init_tablas)  # type: ignore


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
        rows = conn.execute("""
            SELECT p.id, p.nombre, p.categoria, p.precio, p.costo,
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
    lineas = data.get('lineas', [])
    motivo = data.get('motivo', 'compra')
    notas  = data.get('notas') or None
    if not lineas:
        return jsonify({'ok': False, 'error': 'Debe agregar al menos una línea'}), 400
    conn = get_db_connection()
    try:
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
        conn.commit()
        return jsonify({'ok': True, 'advertencias': advertencias})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Stock y kardex ─────────────────────────────────────────────────────────────

@bp.route('/api/inventario/<int:negocio_id>/stock')
def api_inventario_stock(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
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
        rows = conn.execute("""
            SELECT tipo, motivo, cantidad, stock_anterior, stock_nuevo,
                   valor_unitario, costo_und, notas,
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
