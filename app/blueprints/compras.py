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
        CREATE TABLE IF NOT EXISTS presentaciones (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            equivalencia NUMERIC(14,4) NOT NULL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_presentaciones_unique ON presentaciones(LOWER(nombre), equivalencia)")

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
    
    # Alter to add presentacion_id column
    try:
        conn.execute("ALTER TABLE cotizaciones_compras ADD COLUMN IF NOT EXISTS presentacion_id INTEGER REFERENCES presentaciones(id)")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
            
    # Auto-run inline deduplication and unique constraint creation on first load
    try:
        conn.execute("""
            INSERT INTO presentaciones (nombre, equivalencia)
            VALUES ('Unidad', 1.0)
            ON CONFLICT (LOWER(nombre), equivalencia) DO NOTHING;
        """)
        
        u_row = conn.execute("SELECT id FROM presentaciones WHERE LOWER(nombre) = 'unidad' AND equivalencia = 1.0 LIMIT 1").fetchone()
        ue_row = conn.execute("SELECT id FROM presentaciones WHERE LOWER(nombre) = 'unidad (entrada)' AND equivalencia = 1.0 LIMIT 1").fetchone()
        
        if u_row:
            u_id = u_row['id']
            if ue_row:
                ue_id = ue_row['id']
                conn.execute("UPDATE movimientos_inventario SET presentacion_id = %s WHERE presentacion_id = %s", (u_id, ue_id))
                conn.execute("UPDATE cotizaciones_compras SET presentacion_id = %s WHERE presentacion_id = %s", (u_id, ue_id))
                conn.execute("DELETE FROM presentaciones WHERE id = %s", (ue_id,))
            
            conn.execute("UPDATE movimientos_inventario SET presentacion_id = %s WHERE presentacion_id IS NULL", (u_id,))
            conn.execute("UPDATE cotizaciones_compras SET presentacion_id = %s WHERE presentacion_id IS NULL", (u_id,))
            
        conn.execute("""
            DELETE FROM cotizaciones_compras c
            WHERE c.id NOT IN (
                SELECT MAX(id)
                FROM cotizaciones_compras
                GROUP BY negocio_id, tercero_id, item_id, presentacion_id
            );
        """)
        
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cotizaciones_compras_unique 
            ON cotizaciones_compras (negocio_id, tercero_id, item_id, presentacion_id);
        """)
    except Exception as e:
        import sys
        print("Error running inline quotes migration:", e, file=sys.stderr)
        try:
            conn.rollback()
        except Exception:
            pass

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
    return (
        session.get('rol') == 'Administrador'
        or (usuario_id and contexto.get('admin_id') and _mismo_id(usuario_id, contexto['admin_id']))
    )


def _validar_negocio_json(conn, negocio_id):
    contexto = _contexto_negocio(conn, negocio_id)
    if not contexto:
        return None, (jsonify({'ok': False, 'error': 'Negocio no encontrado'}), 404)
    if not _puede_gestionar_negocio(contexto):
        return None, (jsonify({'ok': False, 'error': 'No autorizado para este negocio'}), 403)
    return contexto, None


# ── Órdenes de Compra y Despachos ─────────────────────────────────────────────

import secrets
import urllib.parse
from datetime import datetime, date
import json

def _asegurar_tablas_oc(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_compra (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL REFERENCES terceros(id),
            proveedor_id INTEGER NOT NULL REFERENCES terceros(id),
            numero_oc VARCHAR(50) NOT NULL,
            token_publico VARCHAR(64) UNIQUE NOT NULL,
            fecha_emision TIMESTAMPTZ DEFAULT NOW(),
            estado VARCHAR(30) DEFAULT 'enviada',
            modalidad_entrega VARCHAR(30) DEFAULT 'sede',
            sede_id INTEGER,
            sede_nombre VARCHAR(100),
            direccion_entrega TEXT,
            forma_pago VARCHAR(50),
            dias_credito INTEGER,
            total_estimado NUMERIC(14,2) DEFAULT 0,
            total_confirmado NUMERIC(14,2),
            fecha_entrega_estimada DATE,
            franja_entrega VARCHAR(100),
            observaciones_comprador TEXT,
            observaciones_proveedor TEXT,
            conversacion_id INTEGER REFERENCES conversaciones(id),
            fecha_confirmacion TIMESTAMPTZ,
            fecha_recibida TIMESTAMPTZ,
            entrada_id INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_compra_items (
            id SERIAL PRIMARY KEY,
            orden_compra_id INTEGER NOT NULL REFERENCES ordenes_compra(id) ON DELETE CASCADE,
            producto_id INTEGER NOT NULL REFERENCES productos(id),
            producto_nombre VARCHAR(255) NOT NULL,
            presentacion_id INTEGER,
            presentacion_nombre VARCHAR(100),
            unidades_presentacion NUMERIC(12,4) DEFAULT 1,
            peso_variable BOOLEAN DEFAULT FALSE,
            tolerancia_peso_pct NUMERIC(5,2) DEFAULT 0,
            cantidad_solicitada NUMERIC(12,4) NOT NULL,
            precio_unitario NUMERIC(14,2) NOT NULL,
            total_solicitado NUMERIC(14,2) NOT NULL,
            cantidad_confirmada NUMERIC(12,4),
            precio_confirmado NUMERIC(14,2),
            total_confirmado NUMERIC(14,2),
            estado_item VARCHAR(30) DEFAULT 'pendiente',
            motivo_cambio TEXT
        )
    """)
    conn.commit()


def _formatear_moneda(val):
    try:
        return f"${float(val or 0):,.0f}"
    except Exception:
        return "$0"


@bp.route('/api/inventario/<int:negocio_id>/ordenes-compra', methods=['POST'])
def api_ordenes_compra_crear(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        _asegurar_tablas_oc(conn)
        contexto, err = _validar_negocio_json(conn, negocio_id)
        if err:
            return err

        data = request.get_json() or {}
        proveedor_id = int(data.get('proveedor_id') or 0)
        if not proveedor_id:
            return jsonify({'ok': False, 'error': 'Proveedor requerido'}), 400

        prov = conn.execute("SELECT id, nombre, telefono, direccion FROM terceros WHERE id = %s", (proveedor_id,)).fetchone()
        if not prov:
            return jsonify({'ok': False, 'error': 'Proveedor no encontrado en terceros'}), 404

        items = data.get('items') or []
        if not items:
            return jsonify({'ok': False, 'error': 'No se enviaron productos para la orden'}), 400

        # Datos de entrega y pago
        modalidad = (data.get('modalidad_entrega') or 'sede').strip().lower()
        sede_id = data.get('sede_id')
        sede_nombre = data.get('sede_nombre') or 'Sede Principal'
        direccion_entrega = (data.get('direccion_entrega') or '').strip()
        direccion_recogida = (data.get('direccion_recogida') or '').strip()
        forma_pago = (data.get('forma_pago') or 'contado').strip()
        dias_credito = int(data.get('dias_credito') or 15) if forma_pago == 'credito' else None
        telefono_prov = (data.get('telefono_proveedor') or prov['telefono'] or '').strip()
        observaciones_comp = (data.get('observaciones') or '').strip() or None

        # 1. Actualizar y persistir ficha del proveedor (Tercero)
        conn.execute("""
            UPDATE terceros SET
                telefono = COALESCE(NULLIF(%s, ''), telefono),
                forma_pago_defecto = %s,
                dias_credito = %s,
                modalidad_entrega_defecto = %s,
                direccion_recogida = COALESCE(NULLIF(%s, ''), direccion_recogida)
            WHERE id = %s
        """, (telefono_prov, forma_pago, dias_credito, modalidad, direccion_recogida, proveedor_id))

        # 2. Actualizar dirección de entrega de la sede si se indicó
        if sede_id and direccion_entrega:
            try:
                conn.execute("UPDATE centros_utilidad SET direccion_entrega = %s WHERE id = %s AND negocio_id = %s",
                             (direccion_entrega, int(sede_id), negocio_id))
            except Exception:
                pass

        # 3. Consecutivo de Orden de Compra para el negocio
        consec_row = conn.execute("""
            SELECT COUNT(*) AS total FROM ordenes_compra WHERE negocio_id = %s
        """, (negocio_id,)).fetchone()
        consec_num = int(consec_row['total'] or 0) + 1
        numero_oc = f"OC-{consec_num:04d}"

        token_pub = secrets.token_urlsafe(24)

        # 4. Asegurar conversación en chat entre negocio y proveedor
        conv = conn.execute("""
            SELECT id, token FROM conversaciones
            WHERE (creador_id = %s AND invitado_id = %s)
               OR (creador_id = %s AND invitado_id = %s)
            ORDER BY id ASC LIMIT 1
        """, (negocio_id, proveedor_id, proveedor_id, negocio_id)).fetchone()

        if not conv:
            conv_token = secrets.token_urlsafe(16)
            conv_row = conn.execute("""
                INSERT INTO conversaciones (creador_id, invitado_id, token, nombre_invitado, activa, origen)
                VALUES (%s, %s, %s, %s, TRUE, 'orden_compra')
                RETURNING id, token
            """, (negocio_id, proveedor_id, conv_token, prov['nombre'])).fetchone()
            conv_id = conv_row['id']
            conv_token = conv_row['token']
        else:
            conv_id = conv['id']
            conv_token = conv['token']

        # 5. Calcular total estimado
        total_estimado = 0.0
        for it in items:
            total_estimado += float(it.get('total_solicitado') or 0.0)

        # 6. Insertar orden_compra
        oc_row = conn.execute("""
            INSERT INTO ordenes_compra (
                negocio_id, proveedor_id, numero_oc, token_publico, estado,
                modalidad_entrega, sede_id, sede_nombre, direccion_entrega,
                forma_pago, dias_credito, total_estimado, observaciones_comprador,
                conversacion_id
            ) VALUES (
                %s, %s, %s, %s, 'enviada',
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s
            ) RETURNING id
        """, (
            negocio_id, proveedor_id, numero_oc, token_pub,
            modalidad, int(sede_id) if sede_id else None, sede_nombre, direccion_entrega,
            forma_pago, dias_credito, total_estimado, observaciones_comp,
            conv_id
        )).fetchone()
        oc_id = oc_row['id']

        # 7. Insertar ordenes_compra_items
        for it in items:
            conn.execute("""
                INSERT INTO ordenes_compra_items (
                    orden_compra_id, producto_id, producto_nombre,
                    presentacion_id, presentacion_nombre, unidades_presentacion,
                    peso_variable, tolerancia_peso_pct,
                    cantidad_solicitada, precio_unitario, total_solicitado,
                    cantidad_confirmada, precio_confirmado, total_confirmado,
                    estado_item
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    'pendiente'
                )
            """, (
                oc_id, int(it['producto_id']), it['producto_nombre'],
                int(it['presentacion_id']) if it.get('presentacion_id') else None,
                it.get('presentacion_nombre') or 'Unidad',
                float(it.get('unidades_presentacion') or 1.0),
                bool(it.get('peso_variable', False)),
                float(it.get('tolerancia_peso_pct') or 0.0),
                float(it.get('cantidad_solicitada') or 1.0),
                float(it.get('precio_unitario') or 0.0),
                float(it.get('total_solicitado') or 0.0),
                float(it.get('cantidad_solicitada') or 1.0), # default inicial sugerido
                float(it.get('precio_unitario') or 0.0),
                float(it.get('total_solicitado') or 0.0)
            ))

        # 8. Insertar mensaje inicial en el chat identificando a ambos
        usuario_nom = session.get('nombre') or session.get('usuario') or 'Equipo de Compras'
        negocio_nom = contexto['negocio_nombre']
        modalidad_desc = f"entrega en {sede_nombre} ({direccion_entrega})" if modalidad == 'sede' else f"para recoger en {direccion_recogida or 'su bodega'}"
        pago_desc = f"Crédito {dias_credito} días" if forma_pago == 'credito' else ('Contraentrega' if forma_pago == 'contraentrega' else 'Contado')

        mensaje_chat = (
            f"Hola {prov['nombre']} 👋, te saluda {usuario_nom} de {negocio_nom}. "
            f"Te compartimos la Orden de Compra #{numero_oc} con {modalidad_desc}. "
            f"Condición de pago: {pago_desc}. "
            f"Cualquier consulta o ajuste sobre los productos, puedes respondernos directamente por aquí."
        )

        conn.execute("""
            INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
            VALUES (%s, %s, %s, 'texto', %s, 'pendiente', CURRENT_TIMESTAMP)
        """, (negocio_id, proveedor_id, mensaje_chat, conv_id))

        conn.commit()

        # 9. Construir link público y mensaje para WhatsApp
        host = request.host_url.rstrip('/')
        url_oc = f"{host}/oc/{token_pub}"

        texto_wa = (
            f"👋 Hola *{prov['nombre']}*, te saluda *{usuario_nom}* de *{negocio_nom}*.\n\n"
            f"Te compartimos la Orden de Compra *#{numero_oc}*:\n"
            f"📦 Modalidad: {modalidad_desc}\n"
            f"💳 Pago: {pago_desc}\n"
            f"📄 Ítems solicitados: {len(items)} producto(s) (Total est.: {_formatear_moneda(total_estimado)})\n\n"
            f"Por favor confirma disponibilidad y fecha estimada aquí:\n"
            f"👉 {url_oc}"
        )
        
        tel_clean = "".join(filter(str.isdigit, telefono_prov))
        if tel_clean and len(tel_clean) == 10 and not tel_clean.startswith('57'):
            tel_clean = '57' + tel_clean

        if tel_clean:
            wa_url = f"https://api.whatsapp.com/send?phone={tel_clean}&text={urllib.parse.quote(texto_wa)}"
        else:
            wa_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wa)}" 

        return jsonify({
            'ok': True,
            'orden_id': oc_id,
            'numero_oc': numero_oc,
            'token_publico': token_pub,
            'url_publica': url_oc,
            'whatsapp_url': wa_url,
            'mensaje_whatsapp': texto_wa,
            'telefono': telefono_prov,
            'conversacion_token': conv_token
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ordenes-compra', methods=['GET'])
def api_ordenes_compra_listar(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        _asegurar_tablas_oc(conn)
        rows = conn.execute("""
            SELECT oc.id, oc.numero_oc, oc.token_publico, oc.estado,
                   oc.modalidad_entrega, oc.sede_nombre, oc.direccion_entrega,
                   oc.forma_pago, oc.dias_credito, oc.total_estimado, oc.total_confirmado,
                   oc.fecha_emision, oc.fecha_entrega_estimada, oc.franja_entrega,
                   oc.observaciones_proveedor, oc.fecha_confirmacion, oc.fecha_recibida,
                   t.id AS proveedor_id, t.nombre AS proveedor_nombre, t.telefono AS proveedor_telefono,
                   c.token AS conversacion_token,
                   (SELECT COUNT(*) FROM ordenes_compra_items oci WHERE oci.orden_compra_id = oc.id) AS items_count
            FROM ordenes_compra oc
            JOIN terceros t ON t.id = oc.proveedor_id
            LEFT JOIN conversaciones c ON c.id = oc.conversacion_id
            WHERE oc.negocio_id = %s
            ORDER BY oc.id DESC
            LIMIT 40
        """, (negocio_id,)).fetchall()

        ordenes = []
        for r in rows:
            d = dict(r)
            d['fecha_emision_str'] = r['fecha_emision'].strftime('%d-%b-%Y %H:%M') if r['fecha_emision'] else ''
            d['fecha_entrega_str'] = r['fecha_entrega_estimada'].strftime('%d-%b-%Y') if r['fecha_entrega_estimada'] else ''
            ordenes.append(d)

        return jsonify({'ok': True, 'ordenes': ordenes})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ordenes-compra/<int:orden_id>', methods=['GET'])
def api_orden_compra_detalle(negocio_id, orden_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        _asegurar_tablas_oc(conn)
        oc = conn.execute("""
            SELECT oc.*, t.nombre AS proveedor_nombre, t.telefono AS proveedor_telefono,
                   c.token AS conversacion_token
            FROM ordenes_compra oc
            JOIN terceros t ON t.id = oc.proveedor_id
            LEFT JOIN conversaciones c ON c.id = oc.conversacion_id
            WHERE oc.id = %s AND oc.negocio_id = %s
        """, (orden_id, negocio_id)).fetchone()
        if not oc:
            return jsonify({'ok': False, 'error': 'Orden no encontrada'}), 404

        items = conn.execute("""
            SELECT * FROM ordenes_compra_items WHERE orden_compra_id = %s ORDER BY id ASC
        """, (orden_id,)).fetchall()

        return jsonify({
            'ok': True,
            'orden': dict(oc),
            'items': [dict(it) for it in items]
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ordenes-compra/<int:orden_id>/aprobar-cambios', methods=['POST'])
def api_orden_compra_aprobar_cambios(negocio_id, orden_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        oc = conn.execute("""
            SELECT oc.*, t.nombre AS proveedor_nombre FROM ordenes_compra oc
            JOIN terceros t ON t.id = oc.proveedor_id
            WHERE oc.id = %s AND oc.negocio_id = %s
        """, (orden_id, negocio_id)).fetchone()
        if not oc:
            return jsonify({'ok': False, 'error': 'Orden no encontrada'}), 404

        conn.execute("UPDATE ordenes_compra SET estado = 'confirmada' WHERE id = %s", (orden_id,))

        # Chat alert
        if oc['conversacion_id']:
            conn.execute("""
                INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
                VALUES (%s, %s, %s, 'texto', %s, 'pendiente', CURRENT_TIMESTAMP)
            """, (negocio_id, oc['proveedor_id'],
                  f"✅ El comprador ha aceptado los cambios propuestos en la Orden #{oc['numero_oc']}. La orden queda formalmente confirmada.",
                  oc['conversacion_id']))

        conn.commit()
        return jsonify({'ok': True, 'mensaje': 'Cambios aprobados exitosamente'})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/inventario/<int:negocio_id>/ordenes-compra/<int:orden_id>/datos-entrada', methods=['GET'])
def api_orden_compra_datos_entrada(negocio_id, orden_id):
    """
    Retorna la estructura lista para inyectar en la pestaña 'Entradas' de inventarios.
    """
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401

    conn = get_db_connection()
    try:
        oc = conn.execute("""
            SELECT oc.*, t.nombre AS proveedor_nombre FROM ordenes_compra oc
            JOIN terceros t ON t.id = oc.proveedor_id
            WHERE oc.id = %s AND oc.negocio_id = %s
        """, (orden_id, negocio_id)).fetchone()
        if not oc:
            return jsonify({'ok': False, 'error': 'Orden no encontrada'}), 404

        items = conn.execute("""
            SELECT * FROM ordenes_compra_items WHERE orden_compra_id = %s ORDER BY id ASC
        """, (orden_id,)).fetchall()

        # Marcar como recibida
        conn.execute("UPDATE ordenes_compra SET estado = 'recibida', fecha_recibida = NOW() WHERE id = %s", (orden_id,))
        conn.commit()

        prods_entrada = []
        for it in items:
            cant = float(it['cantidad_confirmada'] if it['cantidad_confirmada'] is not None else it['cantidad_solicitada'])
            prec = float(it['precio_confirmado'] if it['precio_confirmado'] is not None else it['precio_unitario'])
            prods_entrada.append({
                'producto_id': it['producto_id'],
                'producto_nombre': it['producto_nombre'],
                'cantidad_sugerida_unidades': cant * float(it['unidades_presentacion'] or 1.0),
                'costo_unitario': prec,
                'iva_pct': 0,
                'presentacion_id': it['presentacion_id'],
                'presentacion_nombre': it['presentacion_nombre'],
                'unidades_presentacion': float(it['unidades_presentacion'] or 1.0),
                'cantidad_sugerida_usuario': cant,
                'costo_empaque_usuario': prec * float(it['unidades_presentacion'] or 1.0),
                'total_costo': cant * prec * float(it['unidades_presentacion'] or 1.0)
            })

        return jsonify({
            'ok': True,
            'proveedor': {
                'proveedor_id': oc['proveedor_id'],
                'proveedor_nombre': oc['proveedor_nombre']
            },
            'documento': oc['numero_oc'],
            'fecha': date.today().isoformat(),
            'productos': prods_entrada
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── Rutas Públicas de la Orden de Compra (Para el Proveedor) ───────────────────

@bp.route('/oc/<token>')
def orden_compra_publica_vista(token):
    conn = get_db_connection()
    try:
        _asegurar_tablas_oc(conn)
        oc = conn.execute("""
            SELECT oc.*, neg.nombre AS negocio_nombre, neg.telefono AS negocio_telefono,
                   prov.nombre AS proveedor_nombre, prov.telefono AS proveedor_telefono,
                   c.token AS conversacion_token
            FROM ordenes_compra oc
            JOIN terceros neg ON neg.id = oc.negocio_id
            JOIN terceros prov ON prov.id = oc.proveedor_id
            LEFT JOIN conversaciones c ON c.id = oc.conversacion_id
            WHERE oc.token_publico = %s
        """, (token,)).fetchone()
        if not oc:
            return "Orden de compra no encontrada o enlace vencido", 404

        items = conn.execute("""
            SELECT * FROM ordenes_compra_items WHERE orden_compra_id = %s ORDER BY id ASC
        """, (oc['id'],)).fetchall()

        # Establecer sesión para que el chat nativo de TUC TUC reconozca al proveedor
        session['chat_tercero_id'] = oc['proveedor_id']
        session['chat_token'] = oc['conversacion_token']

        oc_dict = dict(oc)
        total_estimado_num = int(round(float(oc_dict.get('total_estimado') or 0)))
        total_confirmado_num = int(round(float(oc_dict['total_confirmado']))) if oc_dict.get('total_confirmado') is not None else None
        
        oc_dict['total_estimado_fmt'] = f"{total_estimado_num:,.0f}".replace(',', '.')
        oc_dict['total_confirmado_fmt'] = f"{total_confirmado_num:,.0f}".replace(',', '.') if total_confirmado_num is not None else None
        oc_dict['total_display_fmt'] = oc_dict['total_confirmado_fmt'] or oc_dict['total_estimado_fmt']

        clean_items = []
        for it in items:
            d = dict(it)
            prec_sol = int(round(float(d.get('precio_unitario') or 0)))
            prec_conf = int(round(float(d['precio_confirmado']))) if d.get('precio_confirmado') is not None else None
            tot_sol = int(round(float(d.get('total_solicitado') or 0)))
            tot_conf = int(round(float(d['total_confirmado']))) if d.get('total_confirmado') is not None else None

            # Cantidad solicitada y confirmada sin decimales innecesarios
            c_sol_raw = float(d.get('cantidad_solicitada') or 0)
            c_sol = int(c_sol_raw) if c_sol_raw.is_integer() else round(c_sol_raw, 2)
            
            c_conf = None
            if d.get('cantidad_confirmada') is not None:
                c_conf_raw = float(d['cantidad_confirmada'])
                c_conf = int(c_conf_raw) if c_conf_raw.is_integer() else round(c_conf_raw, 2)

            u_pres = None
            if d.get('unidades_presentacion') is not None:
                u_raw = float(d['unidades_presentacion'])
                u_pres = int(u_raw) if u_raw.is_integer() else round(u_raw, 1)

            tol = 10
            if d.get('tolerancia_peso_pct') is not None:
                tol_raw = float(d['tolerancia_peso_pct'])
                tol = int(tol_raw) if tol_raw.is_integer() else round(tol_raw, 1)

            # Rango min y max si peso variable
            r_min = round(c_sol_raw * (1.0 - (tol / 100.0)), 2)
            r_min_clean = int(r_min) if r_min.is_integer() else r_min
            r_max = round(c_sol_raw * (1.0 + (tol / 100.0)), 2)
            r_max_clean = int(r_max) if r_max.is_integer() else r_max

            d['precio_unitario'] = prec_sol
            d['precio_unitario_fmt'] = f"{prec_sol:,.0f}".replace(',', '.')
            d['precio_confirmado'] = prec_conf
            d['precio_confirmado_fmt'] = f"{prec_conf:,.0f}".replace(',', '.') if prec_conf is not None else None
            d['total_solicitado'] = tot_sol
            d['total_solicitado_fmt'] = f"{tot_sol:,.0f}".replace(',', '.')
            d['total_confirmado'] = tot_conf
            d['total_confirmado_fmt'] = f"{tot_conf:,.0f}".replace(',', '.') if tot_conf is not None else None
            d['total_display_fmt'] = d['total_confirmado_fmt'] or d['total_solicitado_fmt']

            d['cantidad_solicitada'] = c_sol
            d['cantidad_confirmada'] = c_conf
            d['unidades_presentacion'] = u_pres
            d['tolerancia_peso_pct'] = tol
            d['rango_min'] = r_min_clean
            d['rango_max'] = r_max_clean

            clean_items.append(d)

        return render_template('orden_compra_publica.html',
                               orden=oc_dict,
                               items=clean_items,
                               token=token,
                               conversacion_token=oc['conversacion_token'] or '')
    finally:
        conn.close()


@bp.route('/api/oc/<token>/confirmar', methods=['POST'])
def api_oc_proveedor_confirmar(token):
    conn = get_db_connection()
    try:
        _asegurar_tablas_oc(conn)
        oc = conn.execute("""
            SELECT oc.*, neg.nombre AS negocio_nombre, prov.nombre AS proveedor_nombre
            FROM ordenes_compra oc
            JOIN terceros neg ON neg.id = oc.negocio_id
            JOIN terceros prov ON prov.id = oc.proveedor_id
            WHERE oc.token_publico = %s
        """, (token,)).fetchone()
        if not oc:
            return jsonify({'ok': False, 'error': 'Orden no encontrada'}), 404

        data = request.get_json() or {}
        items_payload = data.get('items') or []
        fecha_entrega = data.get('fecha_entrega_estimada') or None
        franja = (data.get('franja_entrega') or '').strip() or None
        observaciones_prov = (data.get('observaciones_proveedor') or '').strip() or None

        db_items = conn.execute("SELECT * FROM ordenes_compra_items WHERE orden_compra_id = %s", (oc['id'],)).fetchall()
        db_items_map = {it['id']: dict(it) for it in db_items}

        hubo_cambio_alza_o_baja = False
        cambios_resumen = []
        total_confirmado = 0.0

        for it_in in items_payload:
            it_id = int(it_in.get('id') or 0)
            if it_id not in db_items_map:
                continue

            db_it = db_items_map[it_id]
            cant_sol = float(db_it['cantidad_solicitada'])
            prec_sol = float(db_it['precio_unitario'])
            peso_var = bool(db_it['peso_variable'])
            tol_pct = float(db_it['tolerancia_peso_pct'] or 10.0)

            cant_conf = float(it_in.get('cantidad_confirmada', cant_sol))
            prec_conf = float(it_in.get('precio_confirmado', prec_sol))

            # REGLA A: Prohibido sobrepasar cantidades si NO es peso variable
            if not peso_var and cant_conf > cant_sol:
                return jsonify({
                    'ok': False,
                    'error': f"El producto '{db_it['producto_nombre']}' no permite cantidades superiores a las solicitadas ({cant_sol})."
                }), 400

            # Si es peso variable, validar que no exceda la tolerancia superior
            if peso_var:
                max_permitido = round(cant_sol * (1.0 + (tol_pct / 100.0)), 3)
                if cant_conf > max_permitido:
                    return jsonify({
                        'ok': False,
                        'error': f"El producto '{db_it['producto_nombre']}' excede la tolerancia máxima permitida de +{tol_pct}% (Máx: {max_permitido})."
                    }), 400

            # REGLA B y C: Detectar si el precio subió o la cantidad disminuyó fuera de lo esperado
            subio_precio = prec_conf > prec_sol
            bajo_cantidad = False
            if peso_var:
                min_permitido = round(cant_sol * (1.0 - (tol_pct / 100.0)), 3)
                if cant_conf < min_permitido:
                    bajo_cantidad = True
            else:
                if cant_conf < cant_sol:
                    bajo_cantidad = True

            tot_conf = cant_conf * prec_conf
            total_confirmado += tot_conf

            estado_item = 'aprobado'
            if subio_precio or bajo_cantidad:
                hubo_cambio_alza_o_baja = True
                estado_item = 'con_cambio'
                detalle_cambio = f"• {db_it['producto_nombre']}: "
                if subio_precio:
                    detalle_cambio += f"Precio {prec_sol:,.0f} ➔ {prec_conf:,.0f} (+{((prec_conf/prec_sol)-1)*100:.1f}%) "
                if bajo_cantidad:
                    detalle_cambio += f"Cantidad {cant_sol} ➔ {cant_conf} "
                cambios_resumen.append(detalle_cambio)

            conn.execute("""
                UPDATE ordenes_compra_items SET
                    cantidad_confirmada = %s,
                    precio_confirmado = %s,
                    total_confirmado = %s,
                    estado_item = %s
                WHERE id = %s
            """, (cant_conf, prec_conf, tot_conf, estado_item, it_id))

        nuevo_estado = 'propuesta_cambios' if hubo_cambio_alza_o_baja else 'confirmada'

        conn.execute("""
            UPDATE ordenes_compra SET
                estado = %s,
                total_confirmado = %s,
                fecha_entrega_estimada = %s,
                franja_entrega = %s,
                observaciones_proveedor = %s,
                fecha_confirmacion = NOW()
            WHERE id = %s
        """, (nuevo_estado, total_confirmado, fecha_entrega, franja, observaciones_prov, oc['id']))

        # Enviar mensaje al chat interno
        if oc['conversacion_id']:
            if nuevo_estado == 'confirmada':
                msg_chat = f"✅ He confirmado la Orden #{oc['numero_oc']}. Entrega estimada: {fecha_entrega or 'Pronta'} ({franja or 'Por confirmar'}). Total: {_formatear_moneda(total_confirmado)}."
            else:
                msg_chat = f"⚠️ He revisado la Orden #{oc['numero_oc']} y propongo los siguientes cambios pendientes de su aprobación:\n" + "\n".join(cambios_resumen)
            if observaciones_prov:
                msg_chat += f"\nNota: {observaciones_prov}"

            conn.execute("""
                INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
                VALUES (%s, %s, %s, 'texto', %s, 'pendiente', CURRENT_TIMESTAMP)
            """, (oc['proveedor_id'], oc['negocio_id'], msg_chat, oc['conversacion_id']))

        # Notificar por Telegram al negocio si está configurado
        try:
            from .negocios import _enviar_telegram_negocio
            chat_id = conn.execute("SELECT telegram_chat_id FROM terceros WHERE id = %s", (oc['negocio_id'],)).fetchone()
            if chat_id and chat_id['telegram_chat_id']:
                if nuevo_estado == 'confirmada':
                    t_msg = (
                        f"🟢 <b>Orden de Compra Confirmada #{oc['numero_oc']}</b>\n"
                        f"Proveedor: <b>{oc['proveedor_nombre']}</b>\n"
                        f"📅 Entrega estimada: {fecha_entrega or 'Pronta'} ({franja or ''})\n"
                        f"💰 Total confirmado: <b>{_formatear_moneda(total_confirmado)}</b>"
                    )
                else:
                    t_msg = (
                        f"⚠️ <b>Propuesta de cambios en OC #{oc['numero_oc']}</b>\n"
                        f"Proveedor: <b>{oc['proveedor_nombre']}</b>\n"
                        f"Requiere tu aprobación:\n" + "\n".join(cambios_resumen) + "\n"
                        f"Total propuesto: <b>{_formatear_moneda(total_confirmado)}</b>"
                    )
                _enviar_telegram_negocio(conn, chat_id['telegram_chat_id'], t_msg)
        except Exception:
            pass

        conn.commit()
        return jsonify({
            'ok': True,
            'estado': nuevo_estado,
            'total_confirmado': total_confirmado,
            'mensaje': 'Orden confirmada en firme' if nuevo_estado == 'confirmada' else 'Propuesta enviada al comprador para su aprobación'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()

