import os

file_path = "app/blueprints/compras.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

addon = '''

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
        wa_url = f"https://wa.me/{tel_clean}?text={urllib.parse.quote(texto_wa)}" if tel_clean else ""

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

        return render_template('orden_compra_publica.html',
                               orden=dict(oc),
                               items=[dict(it) for it in items],
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

'''

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content + addon)

print("compras.py patched successfully with OC endpoints.")
