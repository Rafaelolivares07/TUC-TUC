from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ..db import get_db_connection

bp = Blueprint('compras', __name__)

_tablas_listas = False


def _asegurar_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cotizaciones_compras (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL,
            numero_cotizacion VARCHAR(80),
            tercero_id INTEGER REFERENCES terceros(id),
            item_id INTEGER NOT NULL REFERENCES productos(id),
            fecha_cotizacion DATE NOT NULL DEFAULT CURRENT_DATE,
            fecha_vencimiento DATE NOT NULL DEFAULT (CURRENT_DATE + 180),
            descripcion_presentacion VARCHAR(255),
            unidades_item NUMERIC(14,4) NOT NULL DEFAULT 1,
            precio NUMERIC(14,2) NOT NULL DEFAULT 0,
            origen VARCHAR(40) DEFAULT 'manual',
            validada_proveedor BOOLEAN DEFAULT FALSE,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cotcomp_neg_item ON cotizaciones_compras(negocio_id, item_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cotcomp_vigencia ON cotizaciones_compras(fecha_vencimiento)")
    conn.commit()
    _tablas_listas = True


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal('0')


def _float(value):
    return float(_decimal(value))


def _txt(value):
    value = str(value or '').strip()
    return value or None


def _date_or_default(value, default):
    value = _txt(value)
    if not value:
        return default
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return default


def _tercero_por_nombre(conn, nombre):
    nombre = _txt(nombre)
    if not nombre:
        return None
    row = conn.execute(
        "SELECT id FROM terceros WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
        (nombre,)
    ).fetchone()
    if row:
        return row['id']
    row = conn.execute(
        "INSERT INTO terceros (nombre) VALUES (%s) RETURNING id",
        (nombre,)
    ).fetchone()
    return row['id']


def _ceil(value):
    value = _decimal(value)
    if value <= 0:
        return Decimal('0')
    return value.quantize(Decimal('1'), rounding=ROUND_CEILING)


def _estado_rotacion(stock, demanda_diaria, dias_para_agotarse,
                     dias_alerta_agotamiento, dias_cobertura_minima):
    if demanda_diaria <= 0:
        return 'sin_rotacion'
    if stock <= 0:
        return 'agotado_real'
    if dias_para_agotarse <= dias_alerta_agotamiento:
        return 'agotado_funcional'
    if dias_para_agotarse <= dias_cobertura_minima:
        return 'comprar_pronto'
    return 'sano'


def _confianza(row, promedio_7, promedio_30):
    dias_30 = int(row['dias_activos_30'] or 0)
    movs_30 = int(row['movs_30'] or 0)
    consumo_30 = _decimal(row['consumo_30'])
    if consumo_30 <= 0:
        return 'sin_datos'
    if dias_30 >= 6 and movs_30 >= 6:
        return 'alta'
    if dias_30 >= 3 or movs_30 >= 3 or (promedio_7 > 0 and promedio_30 > 0):
        return 'media'
    return 'baja'


def _alertas(row, promedio_7, promedio_30, confianza, cotizacion):
    alertas = []
    if confianza in ('baja', 'sin_datos'):
        alertas.append('Poca historia de consumo')
    if promedio_30 > 0 and promedio_7 > promedio_30 * Decimal('1.8'):
        alertas.append('Rotacion reciente acelerada')
    if promedio_30 > 0 and promedio_7 < promedio_30 * Decimal('0.4'):
        alertas.append('Rotacion reciente menor al promedio')
    if cotizacion is None:
        alertas.append('Sin cotizacion vigente')
    return alertas


def _mejor_cotizacion(conn, negocio_id, producto_id, cantidad_sugerida):
    rows = conn.execute("""
        SELECT c.id, c.numero_cotizacion, c.tercero_id, t.nombre AS proveedor_nombre,
               c.descripcion_presentacion, c.unidades_item, c.precio,
               c.fecha_cotizacion, c.fecha_vencimiento,
               (c.precio / NULLIF(c.unidades_item, 0)) AS precio_unitario
        FROM cotizaciones_compras c
        LEFT JOIN terceros t ON t.id = c.tercero_id
        WHERE c.negocio_id = %s
          AND c.item_id = %s
          AND c.fecha_vencimiento >= CURRENT_DATE
          AND c.unidades_item > 0
          AND c.precio > 0
        ORDER BY (c.precio / NULLIF(c.unidades_item, 0)) ASC, c.fecha_vencimiento DESC, c.id DESC
        LIMIT 1
    """, (negocio_id, producto_id)).fetchall()
    if not rows:
        return None

    row = rows[0]
    unidades = _decimal(row['unidades_item'])
    cantidad = _decimal(cantidad_sugerida)
    cantidad_ajustada = cantidad
    if unidades > 0:
        paquetes = _ceil(cantidad / unidades)
        cantidad_ajustada = paquetes * unidades
    precio_unitario = _decimal(row['precio_unitario'])
    valor_estimado = cantidad_ajustada * precio_unitario
    return {
        'id': row['id'],
        'numero_cotizacion': row['numero_cotizacion'],
        'proveedor_id': row['tercero_id'],
        'proveedor_nombre': row['proveedor_nombre'],
        'descripcion_presentacion': row['descripcion_presentacion'],
        'unidades_item': _float(unidades),
        'precio': _float(row['precio']),
        'precio_unitario': _float(precio_unitario),
        'cantidad_ajustada': _float(cantidad_ajustada),
        'valor_estimado': _float(valor_estimado),
        'fecha_vencimiento': row['fecha_vencimiento'].isoformat() if row['fecha_vencimiento'] else None,
    }


def construir_propuesta_rotacion(conn, negocio_id, dias_alerta_agotamiento=2,
                                 dias_cobertura_minima=7,
                                 dias_cobertura_objetivo=15):
    _asegurar_tablas(conn)
    rows = conn.execute("""
        SELECT p.id, p.nombre, p.categoria,
               COALESCE(s.stock, 0) AS stock_actual,
               COALESCE(SUM(m.cantidad) FILTER (
                   WHERE m.tipo = 'salida' AND m.motivo = 'venta'
                     AND m.created_at >= CURRENT_DATE - INTERVAL '7 days'
               ), 0) AS consumo_7,
               COALESCE(SUM(m.cantidad) FILTER (
                   WHERE m.tipo = 'salida' AND m.motivo = 'venta'
                     AND m.created_at >= CURRENT_DATE - INTERVAL '30 days'
               ), 0) AS consumo_30,
               COALESCE(SUM(m.cantidad) FILTER (
                   WHERE m.tipo = 'salida' AND m.motivo = 'venta'
                     AND m.created_at >= CURRENT_DATE - INTERVAL '90 days'
               ), 0) AS consumo_90,
               COUNT(*) FILTER (
                   WHERE m.tipo = 'salida' AND m.motivo = 'venta'
                     AND m.created_at >= CURRENT_DATE - INTERVAL '30 days'
               ) AS movs_30,
               COUNT(DISTINCT DATE(m.created_at)) FILTER (
                   WHERE m.tipo = 'salida' AND m.motivo = 'venta'
                     AND m.created_at >= CURRENT_DATE - INTERVAL '30 days'
               ) AS dias_activos_30
        FROM productos p
        LEFT JOIN saldos_inventario s
               ON s.negocio_id = p.negocio_id
              AND s.producto_id = p.id
              AND s.bodega = 1
        LEFT JOIN movimientos_inventario m
               ON m.negocio_id = p.negocio_id
              AND m.producto_id = p.id
        WHERE p.negocio_id = %s
        GROUP BY p.id, p.nombre, p.categoria, s.stock
        ORDER BY p.categoria, p.nombre
    """, (negocio_id,)).fetchall()

    items = []
    proveedores = {}
    for row in rows:
        stock = _decimal(row['stock_actual'])
        consumo_7 = _decimal(row['consumo_7'])
        consumo_30 = _decimal(row['consumo_30'])
        consumo_90 = _decimal(row['consumo_90'])
        promedio_7 = consumo_7 / Decimal('7')
        promedio_30 = consumo_30 / Decimal('30')
        promedio_90 = consumo_90 / Decimal('90')
        demanda_diaria = max(promedio_7, promedio_30)

        if demanda_diaria > 0:
            dias_para_agotarse = stock / demanda_diaria if stock > 0 else Decimal('0')
        else:
            dias_para_agotarse = None

        estado = _estado_rotacion(
            stock, demanda_diaria, dias_para_agotarse or Decimal('999999'),
            Decimal(str(dias_alerta_agotamiento)),
            Decimal(str(dias_cobertura_minima)),
        )
        cantidad_sugerida = Decimal('0')
        if estado in ('agotado_real', 'agotado_funcional', 'comprar_pronto'):
            cantidad_sugerida = _ceil(demanda_diaria * Decimal(str(dias_cobertura_objetivo)) - stock)

        cotizacion = None
        if cantidad_sugerida > 0:
            cotizacion = _mejor_cotizacion(conn, negocio_id, row['id'], cantidad_sugerida)

        confianza = _confianza(row, promedio_7, promedio_30)
        alertas = _alertas(row, promedio_7, promedio_30, confianza, cotizacion)
        cantidad_final = _decimal(cotizacion['cantidad_ajustada']) if cotizacion else cantidad_sugerida
        valor_estimado = _decimal(cotizacion['valor_estimado']) if cotizacion else Decimal('0')

        item = {
            'producto_id': row['id'],
            'producto_nombre': row['nombre'],
            'categoria': row['categoria'],
            'stock_actual': _float(stock),
            'consumo_7': _float(consumo_7),
            'consumo_30': _float(consumo_30),
            'consumo_90': _float(consumo_90),
            'promedio_7': _float(promedio_7),
            'promedio_30': _float(promedio_30),
            'promedio_90': _float(promedio_90),
            'demanda_diaria': _float(demanda_diaria),
            'dias_para_agotarse': _float(dias_para_agotarse) if dias_para_agotarse is not None else None,
            'estado_rotacion': estado,
            'cantidad_sugerida': _float(cantidad_sugerida),
            'cantidad_final': _float(cantidad_final),
            'confianza': confianza,
            'cotizacion_sugerida': cotizacion,
            'proveedor_id': cotizacion['proveedor_id'] if cotizacion else None,
            'proveedor_nombre': cotizacion['proveedor_nombre'] if cotizacion else None,
            'precio_unitario_estimado': cotizacion['precio_unitario'] if cotizacion else None,
            'valor_estimado': _float(valor_estimado),
            'alertas': alertas,
        }
        items.append(item)

        proveedor_id = item['proveedor_id']
        if cantidad_sugerida > 0 and proveedor_id:
            key = str(proveedor_id)
            if key not in proveedores:
                proveedores[key] = {
                    'proveedor_id': proveedor_id,
                    'proveedor_nombre': item['proveedor_nombre'],
                    'items': [],
                    'total_estimado': 0,
                }
            proveedores[key]['items'].append(item)
            proveedores[key]['total_estimado'] += item['valor_estimado']

    prioridad = {
        'agotado_real': 0,
        'agotado_funcional': 1,
        'comprar_pronto': 2,
        'sano': 3,
        'sin_rotacion': 4,
    }
    items.sort(key=lambda i: (prioridad.get(i['estado_rotacion'], 9), i['dias_para_agotarse'] or 999999))

    return {
        'ok': True,
        'parametros': {
            'dias_alerta_agotamiento': dias_alerta_agotamiento,
            'dias_cobertura_minima': dias_cobertura_minima,
            'dias_cobertura_objetivo': dias_cobertura_objetivo,
        },
        'items': items,
        'proveedores': list(proveedores.values()),
    }


def _row_cotizacion(row):
    precio_unitario = _decimal(row['precio']) / _decimal(row['unidades_item'] or 1)
    return {
        'id': row['id'],
        'negocio_id': row['negocio_id'],
        'numero_cotizacion': row['numero_cotizacion'],
        'tercero_id': row['tercero_id'],
        'proveedor_nombre': row['proveedor_nombre'],
        'item_id': row['item_id'],
        'item_nombre': row['item_nombre'],
        'fecha_cotizacion': row['fecha_cotizacion'].isoformat() if row['fecha_cotizacion'] else None,
        'fecha_vencimiento': row['fecha_vencimiento'].isoformat() if row['fecha_vencimiento'] else None,
        'descripcion_presentacion': row['descripcion_presentacion'],
        'unidades_item': _float(row['unidades_item']),
        'precio': _float(row['precio']),
        'precio_unitario': _float(precio_unitario),
        'origen': row['origen'],
        'validada_proveedor': bool(row['validada_proveedor']),
        'observaciones': row['observaciones'],
    }


def _listar_cotizaciones(conn, negocio_id, producto_id=None):
    params = [negocio_id]
    filtro_producto = ''
    if producto_id:
        filtro_producto = ' AND c.item_id = %s'
        params.append(producto_id)
    rows = conn.execute(f"""
        SELECT c.*, t.nombre AS proveedor_nombre, p.nombre AS item_nombre
        FROM cotizaciones_compras c
        LEFT JOIN terceros t ON t.id = c.tercero_id
        JOIN productos p ON p.id = c.item_id
        WHERE c.negocio_id = %s {filtro_producto}
        ORDER BY c.fecha_vencimiento DESC, p.nombre, t.nombre, c.id DESC
        LIMIT 300
    """, tuple(params)).fetchall()
    return [_row_cotizacion(r) for r in rows]


@bp.route('/admin/compras/<int:negocio_id>')
def admin_compras(negocio_id):
    if 'usuario_id' not in session:
        return redirect(url_for('auth.admin_login'))
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        negocio = conn.execute(
            "SELECT nombre FROM terceros WHERE id = %s", (negocio_id,)
        ).fetchone()
        if not negocio:
            return "Negocio no encontrado", 404
        tienda = conn.execute(
            "SELECT slug, nombre FROM tiendas WHERE tercero_id = %s AND activo = TRUE LIMIT 1",
            (negocio_id,)
        ).fetchone()
        restaurante = None
        if not tienda:
            restaurante = conn.execute(
                "SELECT slug, nombre FROM restaurantes WHERE tercero_id = %s AND activo = TRUE LIMIT 1",
                (negocio_id,)
            ).fetchone()
        volver_url = '/admin'
        volver_label = 'Admin'
        if tienda:
            volver_url = f"/admin/tienda/{tienda['slug']}"
            volver_label = tienda['nombre'] or 'Tienda'
        elif restaurante:
            volver_url = f"/admin/restaurante/{restaurante['slug']}"
            volver_label = restaurante['nombre'] or 'Restaurante'
        return render_template(
            'compras_admin.html',
            negocio_id=negocio_id,
            negocio_nombre=negocio['nombre'],
            volver_url=volver_url,
            volver_label=volver_label,
        )
    except Exception as e:
        return f"Error: {e}", 500
    finally:
        conn.close()


@bp.route('/api/compras/<int:negocio_id>/rotacion')
def api_compras_rotacion(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    dias_alerta = request.args.get('dias_alerta', default=2, type=int)
    dias_minima = request.args.get('dias_minima', default=7, type=int)
    dias_objetivo = request.args.get('dias_objetivo', default=15, type=int)
    conn = get_db_connection()
    try:
        data = construir_propuesta_rotacion(
            conn, negocio_id,
            dias_alerta_agotamiento=max(1, dias_alerta),
            dias_cobertura_minima=max(1, dias_minima),
            dias_cobertura_objetivo=max(1, dias_objetivo),
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/compras/<int:negocio_id>/cotizaciones')
def api_cotizaciones_listar(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    producto_id = request.args.get('producto_id', type=int)
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        return jsonify({'ok': True, 'cotizaciones': _listar_cotizaciones(conn, negocio_id, producto_id)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/compras/<int:negocio_id>/cotizaciones', methods=['POST'])
def api_cotizaciones_crear(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    item_id = data.get('item_id') or data.get('producto_id')
    if not item_id:
        return jsonify({'ok': False, 'error': 'Producto requerido'}), 400
    unidades_item = _decimal(data.get('unidades_item') or 1)
    precio = _decimal(data.get('precio'))
    if unidades_item <= 0:
        return jsonify({'ok': False, 'error': 'Unidades por presentacion debe ser mayor que cero'}), 400
    if precio <= 0:
        return jsonify({'ok': False, 'error': 'Precio requerido'}), 400

    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        producto = conn.execute(
            "SELECT id FROM productos WHERE id = %s AND negocio_id = %s",
            (int(item_id), negocio_id)
        ).fetchone()
        if not producto:
            return jsonify({'ok': False, 'error': 'Producto no pertenece al negocio'}), 400

        tercero_id = data.get('tercero_id')
        if tercero_id:
            tercero_id = int(tercero_id)
        else:
            tercero_id = _tercero_por_nombre(conn, data.get('proveedor_nombre'))
        if not tercero_id:
            return jsonify({'ok': False, 'error': 'Proveedor requerido'}), 400

        fecha_cot = _date_or_default(data.get('fecha_cotizacion'), date.today())
        fecha_vence = _date_or_default(data.get('fecha_vencimiento'), fecha_cot + timedelta(days=180))
        row = conn.execute("""
            INSERT INTO cotizaciones_compras
                (negocio_id, numero_cotizacion, tercero_id, item_id,
                 fecha_cotizacion, fecha_vencimiento, descripcion_presentacion,
                 unidades_item, precio, origen, validada_proveedor, observaciones,
                 updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            RETURNING id
        """, (
            negocio_id,
            _txt(data.get('numero_cotizacion')),
            tercero_id,
            int(item_id),
            fecha_cot,
            fecha_vence,
            _txt(data.get('descripcion_presentacion')),
            float(unidades_item),
            float(precio),
            _txt(data.get('origen')) or 'manual',
            bool(data.get('validada_proveedor', False)),
            _txt(data.get('observaciones')),
        )).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/compras/cotizaciones/<int:cotizacion_id>', methods=['POST'])
def api_cotizaciones_actualizar(cotizacion_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    data = request.get_json() or {}
    unidades_item = _decimal(data.get('unidades_item') or 1)
    precio = _decimal(data.get('precio'))
    if unidades_item <= 0 or precio <= 0:
        return jsonify({'ok': False, 'error': 'Unidades y precio deben ser mayores que cero'}), 400
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        tercero_id = data.get('tercero_id')
        if tercero_id:
            tercero_id = int(tercero_id)
        else:
            tercero_id = _tercero_por_nombre(conn, data.get('proveedor_nombre'))
        if not tercero_id:
            return jsonify({'ok': False, 'error': 'Proveedor requerido'}), 400
        row = conn.execute(
            "SELECT fecha_cotizacion FROM cotizaciones_compras WHERE id = %s",
            (cotizacion_id,)
        ).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Cotizacion no encontrada'}), 404
        fecha_cot = _date_or_default(data.get('fecha_cotizacion'), row['fecha_cotizacion'] or date.today())
        fecha_vence = _date_or_default(data.get('fecha_vencimiento'), fecha_cot + timedelta(days=180))
        conn.execute("""
            UPDATE cotizaciones_compras
            SET numero_cotizacion=%s, tercero_id=%s, fecha_cotizacion=%s,
                fecha_vencimiento=%s, descripcion_presentacion=%s,
                unidades_item=%s, precio=%s, origen=%s,
                validada_proveedor=%s, observaciones=%s, updated_at=NOW()
            WHERE id=%s
        """, (
            _txt(data.get('numero_cotizacion')),
            tercero_id,
            fecha_cot,
            fecha_vence,
            _txt(data.get('descripcion_presentacion')),
            float(unidades_item),
            float(precio),
            _txt(data.get('origen')) or 'manual',
            bool(data.get('validada_proveedor', False)),
            _txt(data.get('observaciones')),
            cotizacion_id,
        ))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/compras/cotizaciones/<int:cotizacion_id>', methods=['DELETE'])
def api_cotizaciones_eliminar(cotizacion_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        conn.execute("DELETE FROM cotizaciones_compras WHERE id=%s", (cotizacion_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()
