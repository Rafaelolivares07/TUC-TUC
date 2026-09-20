import os
import json
import time
import io
import datetime
from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from ..db import get_db_connection
from .auth import admin_required, solo_admin
from ..reportes import CATALOGO

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

bp = Blueprint('reportes', __name__)

REPORTES_INFO = {
    'consulta_cuentas': {
        'nombre': 'Consulta de Cuentas',
        'categoria': 'Contabilidad',
        'icono': 'bi-journal-text',
        'descripcion': 'REG_CTAS agrupado por tercero con débito, crédito y saldo neto.',
        'template': 'reporte_consulta_cuentas.html',
    },
    'consulta_tercero': {
        'nombre': 'Consulta por Tercero',
        'categoria': 'Contabilidad',
        'icono': 'bi-person-lines-fill',
        'descripcion': 'Movimientos detallados de cuentas por tercero.',
        'template': 'reporte_consulta_tercero.html',
    },
    'reg_ctas': {
        'nombre': 'Registro de Cuentas',
        'categoria': 'Contabilidad',
        'icono': 'bi-table',
        'descripcion': 'Listado completo de asientos y registros contables.',
        'template': 'reporte_reg_ctas.html',
    },
    'matriz_terceros_cuentas': {
        'nombre': 'Matriz Terceros vs Cuentas',
        'categoria': 'Contabilidad',
        'icono': 'bi-grid-3x3',
        'descripcion': 'Matriz cruzada de terceros y cuentas contables.',
        'template': 'reporte_matriz_terceros_cuentas.html',
    },
    'ventas_clientes': {
        'nombre': 'Ventas por Cliente',
        'categoria': 'Ventas',
        'icono': 'bi-cart-check',
        'descripcion': 'Consolidado de ventas facturadas por cliente.',
        'template': 'reporte_ventas_clientes.html',
    },
    'inventario': {
        'nombre': 'Inventario y Existencias',
        'categoria': 'Inventario',
        'icono': 'bi-boxes',
        'descripcion': 'Existencias, costos y saldos de productos.',
        'template': 'reporte_inventario.html',
    },
}

def _obtener_agentes_activos(conn, usuario_id, rol):
    rows = conn.execute("""
        SELECT cliente_id, nombre, alias, ultimo_ping
        FROM admin_agent_sesiones
        WHERE ultimo_ping > NOW() - INTERVAL '30 days'
        ORDER BY ultimo_ping DESC, id DESC
    """).fetchall()
    
    permitidos = None
    if rol != 'Administrador':
        perm_rows = conn.execute("""
            SELECT cliente_id FROM admin_agent_permisos WHERE usuario_id = %s
        """, (usuario_id,)).fetchall()
        permitidos = {r['cliente_id'].lower() for r in perm_rows}

    now = datetime.datetime.now(datetime.timezone.utc)
    maquinas = {}
    for r in rows:
        cid_raw = r['cliente_id'] or ''
        cid_clean = cid_raw.strip().lower()
        base_key = cid_clean.replace('_daemon', '')
        if not base_key:
            continue
        if permitidos is not None and base_key not in permitidos and cid_clean not in permitidos:
            continue
            
        up = r['ultimo_ping']
        if up and up.tzinfo is None:
            up = up.replace(tzinfo=datetime.timezone.utc)
            
        diff = (now - up).total_seconds() if up else 9999999
        online = diff < 300
        
        alias = (r['alias'] or '').strip()
        nombre = (r['nombre'] or '').strip()
        if nombre.endswith('(Daemon)'):
            nombre = nombre[:-8].strip()
            
        display_name = alias or nombre or base_key
        
        if base_key not in maquinas:
            maquinas[base_key] = {
                'id': base_key,
                'nombre': display_name,
                'alias': alias,
                'online': online,
                'max_up': up,
                'min_diff': diff,
            }
        else:
            if online:
                maquinas[base_key]['online'] = True
            if alias and not maquinas[base_key]['alias']:
                maquinas[base_key]['alias'] = alias
                maquinas[base_key]['nombre'] = alias
            if up and (maquinas[base_key]['max_up'] is None or up > maquinas[base_key]['max_up']):
                maquinas[base_key]['max_up'] = up
                maquinas[base_key]['min_diff'] = diff

    agentes = []
    for base_key, m in maquinas.items():
        diff = m['min_diff']
        mins = int(diff / 60)
        if mins < 60:
            ultimo = f'hace {mins}m'
        elif mins < 1440:
            ultimo = f'hace {mins // 60}h'
        else:
            ultimo = f'hace {mins // 1440}d'
            
        agentes.append({
            'id': m['id'],
            'nombre': m['nombre'],
            'alias': m['alias'],
            'online': m['online'],
            'ultimo': ultimo,
            '_diff': diff
        })
        
    agentes.sort(key=lambda a: (not a['online'], a['_diff']))
    for a in agentes:
        a.pop('_diff', None)
    return agentes

def _ejecutar_consulta_remota(conn, cliente_id, tipo, parametros, timeout=45):
    row = conn.execute("""
        INSERT INTO admin_agent_consultas (sesion_id, tipo, parametros, estado)
        SELECT id, %s, %s::jsonb, 'pendiente'
        FROM admin_agent_sesiones
        WHERE LOWER(cliente_id) IN (LOWER(%s), LOWER(%s) || '_daemon')
           OR LOWER(cliente_id) = REPLACE(LOWER(%s), '_daemon', '')
        ORDER BY ultimo_ping DESC, id DESC
        LIMIT 1
        RETURNING id
    """, (tipo, json.dumps(parametros), cliente_id, cliente_id, cliente_id)).fetchone()
    
    if not row:
        row = conn.execute("""
            INSERT INTO admin_agent_consultas (sesion_id, tipo, parametros, estado)
            SELECT id, %s, %s::jsonb, 'pendiente'
            FROM admin_agent_sesiones
            WHERE LOWER(cliente_id) IN (LOWER(%s), LOWER(%s) || '_daemon')
               OR LOWER(cliente_id) = REPLACE(LOWER(%s), '_daemon', '')
            ORDER BY id DESC
            LIMIT 1
            RETURNING id
        """, (tipo, json.dumps(parametros), cliente_id, cliente_id, cliente_id)).fetchone()
    
    if not row:
        raise RuntimeError(f"El agente '{cliente_id}' no está registrado.")
        
    conn.commit()
    consulta_id = row['id']
    
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.5)
        c = conn.execute("""
            SELECT estado, respuesta FROM admin_agent_consultas WHERE id=%s
        """, (consulta_id,)).fetchone()
        if c:
            if c['estado'] == 'lista':
                return c['respuesta']
            if c['estado'] == 'error':
                err = c.get('respuesta')
                if isinstance(err, dict):
                    raise RuntimeError(err.get('error', 'Error en el agente'))
                raise RuntimeError(str(err or 'Error en el agente'))
    raise TimeoutError(f"El agente '{cliente_id}' tardó más de {timeout}s en responder.")

def _generar_excel_buffer(reporte_id, rows, filtros, modulo=None, fuente='remoto', cliente_id=''):
    if not HAS_OPENPYXL:
        raise RuntimeError('openpyxl no está instalado')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = reporte_id[:31]

    azul_oscuro = '003F7F'
    gris_claro  = 'F0F4FF'
    hdr_font    = Font(bold=True, color='FFFFFF')
    hdr_fill    = PatternFill('solid', fgColor=azul_oscuro)
    tit_font    = Font(bold=True, size=12, color='FFFFFF')
    tit_fill    = PatternFill('solid', fgColor=azul_oscuro)
    meta_font   = Font(italic=True, color='555555', size=10)
    pie_font    = Font(italic=True, color='888888', size=9)
    num_fmt     = '#,##0.00'

    fila = 1
    nombre_reporte = getattr(modulo, 'NOMBRE', reporte_id) if modulo else reporte_id
    c = ws.cell(fila, 1, nombre_reporte)
    c.font = tit_font
    c.fill = tit_fill
    fila += 1

    fuente_txt = f"Fuente: {fuente.upper()}"
    if cliente_id:
        fuente_txt += f"  —  {cliente_id}"
    c = ws.cell(fila, 1, fuente_txt)
    c.font = meta_font
    fila += 1

    filtros_ui = getattr(modulo, 'FILTROS_UI', []) if modulo else []
    for f_ui in filtros_ui:
        fid = f_ui['id']
        val = filtros.get(fid, '')
        if isinstance(val, list):
            val = ', '.join(str(v) for v in val if v)
        if val:
            c = ws.cell(fila, 1, f"{f_ui['label']}: {val}")
            c.font = meta_font
            fila += 1

    fila += 1

    if not rows:
        ws.cell(fila, 1, 'Sin resultados').font = meta_font
    else:
        excel_cols = getattr(modulo, 'EXCEL_COLS', None) if modulo else None
        if excel_cols:
            keys   = [k  for k, _ in excel_cols]
            labels = [lb for _, lb in excel_cols]
        else:
            keys   = list(rows[0].keys())
            labels = [k.replace('_', ' ').title() for k in keys]

        for ci, label in enumerate(labels, 1):
            c = ws.cell(fila, ci, label)
            c.font = hdr_font
            c.fill = hdr_fill
        fila += 1

        sample = rows[0]
        num_keys = {k for k in keys if isinstance(sample.get(k), (int, float))}

        for ri, r in enumerate(rows):
            fill_par = PatternFill('solid', fgColor=gris_claro) if ri % 2 == 1 else None
            for ci, k in enumerate(keys, 1):
                val = r.get(k, '')
                c = ws.cell(fila, ci, val)
                if k in num_keys:
                    c.number_format = num_fmt
                if fill_par:
                    c.fill = fill_par
            fila += 1

    fila += 1
    ws.cell(fila, 1, f'Generado: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}').font = pie_font

    for col in ws.columns:
        letra = col[0].column_letter
        max_len = max((len(str(cell.value or '')) for cell in col), default=0)
        ws.column_dimensions[letra].width = min(max_len + 2, 60)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

@bp.route('/admin/reportes')
@admin_required
def reportes_menu():
    tipo = request.args.get('tipo') or request.args.get('id') or request.args.get('reporte')
    if tipo:
        return reporte_detalle(tipo)
    conn = get_db_connection()
    try:
        usuario_id = session.get('usuario_id')
        rol = session.get('rol', '')
        agentes = _obtener_agentes_activos(conn, usuario_id, rol)
        
        categorias = {}
        for rid, info in REPORTES_INFO.items():
            cat = info['categoria']
            if cat not in categorias:
                categorias[cat] = []
            categorias[cat].append({
                'id': rid,
                'nombre': info['nombre'],
                'icono': info.get('icono', 'bi-file-earmark-text'),
                'descripcion': info.get('descripcion', ''),
            })
            
        try:
            return render_template('sar_reportes_menu.html',
                                   categorias=categorias,
                                   agentes=agentes,
                                   nombre=session.get('nombre', ''))
        except Exception:
            return reporte_detalle('reg_ctas')
    finally:
        conn.close()

@bp.route('/admin/reportes/<reporte_id>')
@admin_required
def reporte_detalle(reporte_id):
    if reporte_id not in REPORTES_INFO and reporte_id not in CATALOGO:
        flash(f"Reporte '{reporte_id}' no encontrado", "warning")
        return redirect(url_for('reportes.reportes_menu'))
        
    info = REPORTES_INFO.get(reporte_id, {
        'nombre': getattr(CATALOGO.get(reporte_id), 'NOMBRE', reporte_id),
        'template': f'reporte_{reporte_id}.html'
    })
    conn = get_db_connection()
    try:
        usuario_id = session.get('usuario_id')
        rol = session.get('rol', '')
        agentes = _obtener_agentes_activos(conn, usuario_id, rol)
        hoy = datetime.date.today().isoformat()
        
        agente_param = request.args.get('agente', '').strip()
        if not agente_param and agentes:
            online_agents = [a for a in agentes if a['online']]
            agente_param = online_agents[0]['id'] if online_agents else agentes[0]['id']
            
        return render_template(info['template'],
                               reporte_id=reporte_id,
                               reporte_nombre=info['nombre'],
                               agentes=agentes,
                               agente_actual=agente_param,
                               desde=hoy,
                               hasta=hoy,
                               empresas=['MG', 'TP', 'VA', 'DI'],
                               sar_nombre=session.get('nombre', ''))
    finally:
        conn.close()

@bp.route('/admin/api/reporte/<reporte_id>/iniciar', methods=['POST'])
@admin_required
def api_reporte_iniciar(reporte_id):
    if reporte_id not in REPORTES_INFO and reporte_id not in CATALOGO:
        return jsonify({'ok': False, 'error': f"Reporte '{reporte_id}' no existe"}), 404
        
    body = request.get_json(force=True) or {}
    agente = (body.get('agente') or body.get('cliente_id') or '').strip()
    filtros = {k: v for k, v in body.items() if k not in ('agente', 'cliente_id', 'fuente')}
    
    conn = get_db_connection()
    try:
        if not agente:
            agentes = _obtener_agentes_activos(conn, session.get('usuario_id'), session.get('rol', ''))
            if agentes:
                agente = agentes[0]['id']
        if not agente:
            return jsonify({'ok': False, 'error': 'No se especificó un agente'}), 400
            
        row = conn.execute("""
            INSERT INTO admin_agent_consultas (sesion_id, tipo, parametros, estado)
            SELECT id, 'ejecutar_reporte', %s::jsonb, 'pendiente'
            FROM admin_agent_sesiones
            WHERE LOWER(cliente_id) IN (LOWER(%s), LOWER(%s) || '_daemon')
               OR LOWER(cliente_id) = REPLACE(LOWER(%s), '_daemon', '')
            ORDER BY ultimo_ping DESC, id DESC
            LIMIT 1
            RETURNING id
        """, (json.dumps({'reporte_id': reporte_id, 'filtros': filtros}), agente, agente, agente)).fetchone()
        
        if not row:
            row = conn.execute("""
                INSERT INTO admin_agent_consultas (sesion_id, tipo, parametros, estado)
                SELECT id, 'ejecutar_reporte', %s::jsonb, 'pendiente'
                FROM admin_agent_sesiones
                WHERE LOWER(cliente_id) IN (LOWER(%s), LOWER(%s) || '_daemon')
                   OR LOWER(cliente_id) = REPLACE(LOWER(%s), '_daemon', '')
                ORDER BY id DESC
                LIMIT 1
                RETURNING id
            """, (json.dumps({'reporte_id': reporte_id, 'filtros': filtros}), agente, agente, agente)).fetchone()
            
        if not row:
            return jsonify({'ok': False, 'error': f"El agente '{agente}' no está registrado"}), 400
            
        conn.commit()
        return jsonify({'ok': True, 'consulta_id': row['id'], 'agente': agente})
    finally:
        conn.close()

@bp.route('/admin/api/reporte/resultado/<int:consulta_id>', methods=['GET'])
@admin_required
def api_reporte_resultado(consulta_id):
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT id, tipo, parametros, respuesta, estado, created_at, respondida_at
            FROM admin_agent_consultas WHERE id = %s
        """, (consulta_id,)).fetchone()
        
        if not row:
            return jsonify({'ok': False, 'error': 'Consulta no encontrada'}), 404
            
        estado = row['estado']
        if estado == 'pendiente':
            return jsonify({'ok': True, 'estado': 'pendiente'})
            
        if estado == 'error':
            err = row.get('respuesta')
            err_msg = err.get('error') if isinstance(err, dict) else str(err or 'Error en el agente')
            return jsonify({'ok': False, 'estado': 'error', 'error': err_msg})
            
        if estado == 'lista':
            ans = row['respuesta']
            if isinstance(ans, dict):
                filas = ans.get('filas') if 'filas' in ans else ans.get('rows', [])
            elif isinstance(ans, list):
                filas = ans
            else:
                filas = []
            
            elapsed = 0
            if row['respondida_at'] and row['created_at']:
                elapsed = round((row['respondida_at'] - row['created_at']).total_seconds(), 2)
                
            return jsonify({
                'ok': True,
                'estado': 'lista',
                'filas': filas,
                'rows': filas,
                'total': len(filas),
                'elapsed': elapsed
            })
            
        return jsonify({'ok': True, 'estado': estado})
    finally:
        conn.close()

@bp.route('/admin/api/reporte/<reporte_id>', methods=['POST'])
@bp.route('/api/reporte/<reporte_id>', methods=['POST'])
@admin_required
def ejecutar_reporte_api(reporte_id):
    if reporte_id not in REPORTES_INFO and reporte_id not in CATALOGO:
        return jsonify({'ok': False, 'error': f"Reporte '{reporte_id}' no existe"}), 404
        
    body = request.get_json(force=True) or {}
    agente = (body.get('agente') or body.get('cliente_id') or '').strip()
    
    conn = get_db_connection()
    try:
        if not agente:
            agentes = _obtener_agentes_activos(conn, session.get('usuario_id'), session.get('rol', ''))
            if agentes:
                agente = agentes[0]['id']
        if not agente:
            return jsonify({'ok': False, 'error': 'No se especificó un agente remoto'}), 400
            
        filtros = {k: v for k, v in body.items() if k not in ('agente', 'cliente_id', 'fuente')}
        t0 = time.time()
        mod = CATALOGO.get(reporte_id)
        
        try:
            resp = _ejecutar_consulta_remota(conn, agente, 'ejecutar_reporte', {
                'reporte_id': reporte_id,
                'filtros': filtros
            }, timeout=45)
            if isinstance(resp, dict):
                if 'filas' in resp:
                    filas = resp['filas']
                elif 'rows' in resp:
                    filas = resp['rows']
                else:
                    filas = resp
            elif isinstance(resp, list):
                filas = resp
            else:
                filas = []
        except Exception as e_direct:
            if mod and hasattr(mod, 'tablas_requeridas') and hasattr(mod, 'calcular'):
                tablas = mod.tablas_requeridas(filtros)
                datos = _ejecutar_consulta_remota(conn, agente, 'multi_tabla', {
                    'tablas': tablas
                }, timeout=45)
                filas = mod.calcular(datos, filtros)
            else:
                return jsonify({'ok': False, 'error': str(e_direct)}), 500
                
        elapsed = round(time.time() - t0, 2)
        total_cnt = len(filas) if hasattr(filas, '__len__') else 0
        return jsonify({
            'ok': True,
            'rows': filas,
            'filas': filas,
            'total': total_cnt,
            'elapsed': elapsed,
            'agente': agente
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()

@bp.route('/admin/api/reporte/<reporte_id>/excel', methods=['POST'])
@bp.route('/api/reporte/<reporte_id>/excel', methods=['POST'])
@admin_required
def exportar_excel_api(reporte_id):
    try:
        body = request.get_json(force=True) or {}
        agente = (body.get('agente') or body.get('cliente_id') or '').strip()
        filas = body.get('filas') or body.get('rows')
        filtros = {k: v for k, v in body.items() if k not in ('agente', 'cliente_id', 'fuente', 'filas', 'rows')}
        mod = CATALOGO.get(reporte_id)
        
        conn = get_db_connection()
        try:
            if not filas:
                if not agente:
                    agentes = _obtener_agentes_activos(conn, session.get('usuario_id'), session.get('rol', ''))
                    if agentes:
                        agente = agentes[0]['id']
                if not agente:
                    return 'Agente requerido', 400
                try:
                    resp = _ejecutar_consulta_remota(conn, agente, 'ejecutar_reporte', {
                        'reporte_id': reporte_id,
                        'filtros': filtros
                    }, timeout=45)
                    filas = resp.get('filas', []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
                except Exception:
                    if mod and hasattr(mod, 'tablas_requeridas') and hasattr(mod, 'calcular'):
                        tablas = mod.tablas_requeridas(filtros)
                        datos = _ejecutar_consulta_remota(conn, agente, 'multi_tabla', {'tablas': tablas}, timeout=45)
                        filas = mod.calcular(datos, filtros)
                    else:
                        filas = []
        finally:
            conn.close()
            
        if mod and hasattr(mod, 'generar_excel'):
            buf = mod.generar_excel(filas, filtros, 'remoto', agente)
        else:
            buf = _generar_excel_buffer(reporte_id, filas, filtros, mod, fuente='remoto', cliente_id=agente)
            
        filename = f"{reporte_id}_{datetime.date.today().isoformat()}.xlsx"
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/admin/api/cuentas', methods=['GET', 'POST'])
@bp.route('/api/cuentas', methods=['GET', 'POST'])
@admin_required
def api_cuentas():
    body = request.get_json(silent=True) or {}
    agente = (request.args.get('agente') or body.get('agente') or request.args.get('cliente_id') or body.get('cliente_id') or '').strip()
    conn = get_db_connection()
    try:
        if not agente:
            agentes = _obtener_agentes_activos(conn, session.get('usuario_id'), session.get('rol', ''))
            if agentes:
                agente = agentes[0]['id']
        if not agente:
            return jsonify({'ok': False, 'error': 'Agente requerido', 'cuentas': []}), 400
        
        datos = _ejecutar_consulta_remota(conn, agente, 'multi_tabla', {
            'tablas': [{'tabla': 'CUENTAS', 'campos': ['CODIGO', 'NOMBRE'], 'filtros': {}}]
        }, timeout=30)
        
        raw_cuentas = datos.get('CUENTAS', []) if isinstance(datos, dict) else []
        cuentas = []
        for r in raw_cuentas:
            c = str(r.get('CODIGO', '') or '').strip()
            n = str(r.get('NOMBRE', '') or '').strip()
            if c:
                cuentas.append({'codigo': c, 'nombre': n})
        cuentas.sort(key=lambda x: x['codigo'])
        return jsonify({'ok': True, 'cuentas': cuentas, 'total': len(cuentas)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'cuentas': []}), 500
    finally:
        conn.close()


@bp.route('/admin/api/empresas', methods=['GET', 'POST'])
@bp.route('/api/empresas', methods=['GET', 'POST'])
@admin_required
def api_empresas():
    body = request.get_json(silent=True) or {}
    agente = (request.args.get('agente') or body.get('agente') or request.args.get('cliente_id') or body.get('cliente_id') or '').strip()
    conn = get_db_connection()
    try:
        if not agente:
            agentes = _obtener_agentes_activos(conn, session.get('usuario_id'), session.get('rol', ''))
            if agentes:
                agente = agentes[0]['id']
        if not agente:
            return jsonify({'ok': False, 'error': 'Agente requerido', 'empresas': []}), 400
        
        datos = _ejecutar_consulta_remota(conn, agente, 'multi_tabla', {
            'tablas': [{'tabla': 'EMPRESAS', 'campos': ['COD_EMP', 'NOM_EMP', 'NIT'], 'filtros': {}}]
        }, timeout=30)
        
        raw_emp = datos.get('EMPRESAS', []) if isinstance(datos, dict) else []
        empresas = []
        for r in raw_emp:
            cod = str(r.get('COD_EMP', '') or '').strip()
            nom = str(r.get('NOM_EMP', '') or '').strip()
            nit = str(r.get('NIT', '') or '').strip()
            if cod or nom:
                empresas.append({'codigo': cod, 'nombre': nom, 'nit': nit})
        
        empresas.sort(key=lambda x: x['codigo'] if x['codigo'] else x['nombre'])
        return jsonify({'ok': True, 'empresas': empresas, 'total': len(empresas)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'empresas': []}), 500
    finally:
        conn.close()
