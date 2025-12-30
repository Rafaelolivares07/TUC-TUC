# Código para insertar en 1_medicamentos.py después de la línea 14258
# Endpoints API para gestión de parámetros de horarios y festivos

# --- ENDPOINTS DE PARÁMETROS ---

@app.route('/api/parametros/horarios', methods=['GET'])
@admin_required
def get_horarios():
    """Obtiene los horarios de entrega configurados"""
    try:
        conn = get_db_connection()

        horarios_data = {}

        # Obtener horarios lun-sab
        lun_sab = conn.execute("""
            SELECT hora_apertura_h, hora_apertura_m, hora_apertura_ampm,
                   hora_cierre_h, hora_cierre_m, hora_cierre_ampm
            FROM parametros_horarios
            WHERE tipo = 'lun_sab'
        """).fetchone()

        if lun_sab:
            horarios_data['lun_sab'] = {
                'apertura_h': lun_sab['hora_apertura_h'],
                'apertura_m': lun_sab['hora_apertura_m'],
                'apertura_ampm': lun_sab['hora_apertura_ampm'],
                'cierre_h': lun_sab['hora_cierre_h'],
                'cierre_m': lun_sab['hora_cierre_m'],
                'cierre_ampm': lun_sab['hora_cierre_ampm']
            }

        # Obtener horarios dom-festivos
        dom_festivos = conn.execute("""
            SELECT hora_apertura_h, hora_apertura_m, hora_apertura_ampm,
                   hora_cierre_h, hora_cierre_m, hora_cierre_ampm
            FROM parametros_horarios
            WHERE tipo = 'dom_festivos'
        """).fetchone()

        if dom_festivos:
            horarios_data['dom_festivos'] = {
                'apertura_h': dom_festivos['hora_apertura_h'],
                'apertura_m': dom_festivos['hora_apertura_m'],
                'apertura_ampm': dom_festivos['hora_apertura_ampm'],
                'cierre_h': dom_festivos['hora_cierre_h'],
                'cierre_m': dom_festivos['hora_cierre_m'],
                'cierre_ampm': dom_festivos['hora_cierre_ampm']
            }

        conn.close()

        return jsonify({
            'ok': True,
            'horarios': horarios_data
        })
    except Exception as e:
        print(f"Error obteniendo horarios: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/parametros/horarios', methods=['POST'])
@admin_required
def guardar_horarios():
    """Guarda o actualiza los horarios de entrega"""
    try:
        data = request.get_json()
        conn = get_db_connection()

        # Guardar lun-sab
        if 'lun_sab' in data:
            ls = data['lun_sab']
            conn.execute("""
                INSERT INTO parametros_horarios
                (tipo, hora_apertura_h, hora_apertura_m, hora_apertura_ampm,
                 hora_cierre_h, hora_cierre_m, hora_cierre_ampm, fecha_actualizacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (tipo)
                DO UPDATE SET
                    hora_apertura_h = EXCLUDED.hora_apertura_h,
                    hora_apertura_m = EXCLUDED.hora_apertura_m,
                    hora_apertura_ampm = EXCLUDED.hora_apertura_ampm,
                    hora_cierre_h = EXCLUDED.hora_cierre_h,
                    hora_cierre_m = EXCLUDED.hora_cierre_m,
                    hora_cierre_ampm = EXCLUDED.hora_cierre_ampm,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            """, ('lun_sab', ls['apertura_h'], ls['apertura_m'], ls['apertura_ampm'],
                  ls['cierre_h'], ls['cierre_m'], ls['cierre_ampm']))

        # Guardar dom-festivos
        if 'dom_festivos' in data:
            df = data['dom_festivos']
            conn.execute("""
                INSERT INTO parametros_horarios
                (tipo, hora_apertura_h, hora_apertura_m, hora_apertura_ampm,
                 hora_cierre_h, hora_cierre_m, hora_cierre_ampm, fecha_actualizacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (tipo)
                DO UPDATE SET
                    hora_apertura_h = EXCLUDED.hora_apertura_h,
                    hora_apertura_m = EXCLUDED.hora_apertura_m,
                    hora_apertura_ampm = EXCLUDED.hora_apertura_ampm,
                    hora_cierre_h = EXCLUDED.hora_cierre_h,
                    hora_cierre_m = EXCLUDED.hora_cierre_m,
                    hora_cierre_ampm = EXCLUDED.hora_cierre_ampm,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            """, ('dom_festivos', df['apertura_h'], df['apertura_m'], df['apertura_ampm'],
                  df['cierre_h'], df['cierre_m'], df['cierre_ampm']))

        conn.commit()
        conn.close()

        return jsonify({
            'ok': True,
            'message': 'Horarios guardados correctamente'
        })
    except Exception as e:
        print(f"Error guardando horarios: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/parametros/festivos', methods=['GET'])
@admin_required
def get_festivos():
    """Obtiene la lista de festivos"""
    try:
        conn = get_db_connection()

        festivos = conn.execute("""
            SELECT id, fecha, nombre
            FROM festivos
            WHERE activo = TRUE
            ORDER BY fecha ASC
        """).fetchall()

        conn.close()

        festivos_list = [{
            'id': f['id'],
            'fecha': str(f['fecha']),
            'nombre': f['nombre']
        } for f in festivos]

        return jsonify({
            'ok': True,
            'festivos': festivos_list
        })
    except Exception as e:
        print(f"Error obteniendo festivos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/parametros/festivos', methods=['POST'])
@admin_required
def agregar_festivo():
    """Agrega un nuevo festivo"""
    try:
        data = request.get_json()
        fecha = data.get('fecha')
        nombre = data.get('nombre', '').strip()

        if not fecha or not nombre:
            return jsonify({'ok': False, 'error': 'Fecha y nombre son requeridos'}), 400

        conn = get_db_connection()

        # Verificar si ya existe
        existe = conn.execute("""
            SELECT id FROM festivos WHERE fecha = %s
        """, (fecha,)).fetchone()

        if existe:
            conn.close()
            return jsonify({'ok': False, 'error': 'Ya existe un festivo en esa fecha'}), 400

        # Insertar
        conn.execute("""
            INSERT INTO festivos (fecha, nombre)
            VALUES (%s, %s)
        """, (fecha, nombre))

        conn.commit()
        conn.close()

        return jsonify({
            'ok': True,
            'message': 'Festivo agregado correctamente'
        })
    except Exception as e:
        print(f"Error agregando festivo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/parametros/festivos/<int:festivo_id>', methods=['DELETE'])
@admin_required
def eliminar_festivo(festivo_id):
    """Elimina un festivo"""
    try:
        conn = get_db_connection()

        conn.execute("""
            DELETE FROM festivos WHERE id = %s
        """, (festivo_id,))

        conn.commit()
        conn.close()

        return jsonify({
            'ok': True,
            'message': 'Festivo eliminado correctamente'
        })
    except Exception as e:
        print(f"Error eliminando festivo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/validar-horario', methods=['GET'])
def validar_horario():
    """Valida si la hora actual está dentro del horario de entregas"""
    from datetime import datetime, time

    try:
        conn = get_db_connection()

        # Obtener fecha y hora actual
        ahora = datetime.now()
        dia_semana = ahora.weekday()  # 0=Lunes, 6=Domingo
        fecha_actual = ahora.date()

        # Verificar si es festivo
        es_festivo = conn.execute("""
            SELECT id FROM festivos
            WHERE fecha = %s AND activo = TRUE
        """, (fecha_actual,)).fetchone()

        # Determinar qué tipo de horario usar
        if dia_semana == 6 or es_festivo:  # Domingo o festivo
            tipo_horario = 'dom_festivos'
        else:  # Lunes a Sábado
            tipo_horario = 'lun_sab'

        # Obtener horario correspondiente
        horario = conn.execute("""
            SELECT hora_apertura_h, hora_apertura_m, hora_apertura_ampm,
                   hora_cierre_h, hora_cierre_m, hora_cierre_ampm
            FROM parametros_horarios
            WHERE tipo = %s
        """, (tipo_horario,)).fetchone()

        conn.close()

        if not horario:
            # Sin horarios configurados, asumir abierto
            return jsonify({
                'ok': True,
                'dentro_horario': True,
                'mensaje': None
            })

        # Convertir horarios a formato 24h
        def a_24h(h, m, ampm):
            if ampm == 'PM' and h != 12:
                h += 12
            elif ampm == 'AM' and h == 12:
                h = 0
            return time(h, m)

        hora_apertura = a_24h(
            horario['hora_apertura_h'],
            horario['hora_apertura_m'],
            horario['hora_apertura_ampm']
        )

        hora_cierre = a_24h(
            horario['hora_cierre_h'],
            horario['hora_cierre_m'],
            horario['hora_cierre_ampm']
        )

        hora_actual = ahora.time()

        # Validar si está dentro del horario
        # Caso especial: si cierre es medianoche (00:00), es el final del día
        if hora_cierre == time(0, 0):
            dentro_horario = hora_actual >= hora_apertura
        else:
            dentro_horario = hora_apertura <= hora_actual <= hora_cierre

        # Preparar mensaje si está fuera de horario
        mensaje = None
        if not dentro_horario:
            # Formatear hora de apertura
            h_ap = horario['hora_apertura_h']
            m_ap = horario['hora_apertura_m']
            ampm_ap = horario['hora_apertura_ampm']

            hora_texto = f"{h_ap}:{m_ap:02d} {ampm_ap}"

            # Determinar cuándo será la próxima apertura
            if hora_actual < hora_apertura:
                # Hoy mismo más tarde
                if dia_semana == 6:  # Domingo
                    dia_texto = "hoy"
                else:
                    dia_texto = "hoy"
            else:
                # Mañana
                if dia_semana == 5:  # Sábado, siguiente es domingo
                    # Obtener horario de domingo
                    conn = get_db_connection()
                    horario_dom = conn.execute("""
                        SELECT hora_apertura_h, hora_apertura_m, hora_apertura_ampm
                        FROM parametros_horarios
                        WHERE tipo = 'dom_festivos'
                    """).fetchone()
                    conn.close()

                    if horario_dom:
                        h_ap = horario_dom['hora_apertura_h']
                        m_ap = horario_dom['hora_apertura_m']
                        ampm_ap = horario_dom['hora_apertura_ampm']
                        hora_texto = f"{h_ap}:{m_ap:02d} {ampm_ap}"

                    dia_texto = "mañana (Domingo)"
                elif dia_semana == 6:  # Domingo, siguiente es lunes
                    # Obtener horario de lunes
                    conn = get_db_connection()
                    horario_lun = conn.execute("""
                        SELECT hora_apertura_h, hora_apertura_m, hora_apertura_ampm
                        FROM parametros_horarios
                        WHERE tipo = 'lun_sab'
                    """).fetchone()
                    conn.close()

                    if horario_lun:
                        h_ap = horario_lun['hora_apertura_h']
                        m_ap = horario_lun['hora_apertura_m']
                        ampm_ap = horario_lun['hora_apertura_ampm']
                        hora_texto = f"{h_ap}:{m_ap:02d} {ampm_ap}"

                    dia_texto = "mañana (Lunes)"
                else:
                    dia_texto = "mañana"

            mensaje = f"Entregas programadas a partir de las {hora_texto} del {dia_texto}"

        return jsonify({
            'ok': True,
            'dentro_horario': dentro_horario,
            'mensaje': mensaje,
            'tipo_horario': tipo_horario
        })

    except Exception as e:
        print(f"Error validando horario: {e}")
        import traceback
        traceback.print_exc()
        # En caso de error, asumir que está abierto (no bloquear compras)
        return jsonify({
            'ok': True,
            'dentro_horario': True,
            'mensaje': None,
            'error': str(e)
        })


# --- FIN ENDPOINTS DE PARÁMETROS ---
