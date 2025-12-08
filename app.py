# ===================================================================
#                               app.py
#               CONTROLADOR CENTRAL Y LÓGICA DEL SERVIDOR
# ===================================================================

# --- MOCK/PLACEHOLDER DE FUNCIONES DE BASE DE DATOS (REEMPLAZAR) ---
# Si estas funciones no existen, el código fallará. Asumimos que manejan SQLite.

# ###################################################################
# ### COMIENZA ZONA 0: CONFIGURACIÓN & IMPORTS ###
# ###################################################################

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, make_response
import sqlite3
import os
import re 
import hashlib 
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps, ImageFile, ImageEnhance
ImageFile.LOAD_TRUNCATED_IMAGES = True 
import pytesseract
import requests
import json 
from requests.exceptions import HTTPError, RequestException 
from datetime import datetime
import time
import tempfile 
import uuid 
from functools import wraps 
# Importación CRÍTICA para inicialización de la BD
from data_initializer import poblar_base_de_datos_mock, init_db_schema

# Inicialización de la aplicación
app = Flask(__name__) 

# ===================================================================
# FUNCIONES DE UTILIDAD (Manejo de Dispositivos/Roles)
# ===================================================================

# Asegúrese de tener: import uuid # CRÍTICO para generar device_id

def generate_unique_device_id():
    """Genera un UUIDv4 único para identificar el dispositivo."""
    return uuid.uuid4().hex

def save_device_id_with_rol_and_name(device_id, rol_master, nombre):
    """
    Guarda o actualiza la identificación de un dispositivo en la tabla USUARIOS según el rol:
    - Admin: Actualiza el Admin pre-existente (por nombre) con el nuevo device_id.
    - Cliente: Inserta un nuevo registro con el device_id (Guardado Inicial).
    """
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        if rol_master == 'Admin':
            # 1. Lógica CRÍTICA para Admin: Asocia el nuevo dispositivo_id al nombre de Admin pre-existente.
            # Esto mantiene el registro único del Admin y solo cambia el dispositivo asociado.
            cursor.execute("""
                UPDATE USUARIOS 
                SET dispositivo_id = ? 
                WHERE nombre = ? AND rol = 'Admin'
            """, (device_id, nombre))

            if cursor.rowcount == 0:
                # Si no se encontró un Admin con ese nombre, el flujo debe fallar.
                raise Exception(f"Admin con nombre '{nombre}' no encontrado o no tiene rol 'Admin'. No se pudo asignar dispositivo.")

        else: # rol_master == 'Cliente' (Lógica de Guardado Inicial)
            # 2. Lógica para Cliente: Inserta un nuevo registro.
            # El resto de los datos (edad, peso) se actualizarán después con update_client_profile().
            cursor.execute("""
                INSERT INTO USUARIOS (dispositivo_id, rol, nombre, fecha_registro) 
                VALUES (?, ?, ?, DATETIME('now','localtime'))
            """, (device_id, rol_master, nombre))
            
        conn.commit()
    
    except sqlite3.IntegrityError as e:
        # Captura errores si el Cliente intenta usar un nombre que ya está en la DB
        print(f"Error de integridad (nombre o device_id duplicado): {e}")
        conn.rollback()
        raise Exception("El nombre de usuario ya está registrado.")
    except Exception as e:
        print(f"Error al guardar la identificación: {e}")
        conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()



# --- Configuración de la Aplicación ---
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif"}
DB = os.path.join(APP_ROOT, "medicamentos.db")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = 'una_clave_muy_secreta_y_larga_para_la_sesion_0123456789' 

# Configuración del ejecutable de Tesseract (Ajusta la ruta si es necesario)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# ###################################################################
# ### COMIENZA ZONA 1: SEGURIDAD & DB CORE ###
# ###################################################################

def get_db():
    """Abre una nueva conexión a la base de datos."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row 
    return conn

def admin_required(f):
    """Decorador para restringir el acceso a usuarios con rol 'Admin'.
    
    CRÍTICO: Si el acceso es denegado, elimina la cookie 'dispositivo_id' 
    y redirige a la ruta de identificación para evitar el bucle.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Asegúrate de que get_user_rol_by_device_id está definida y disponible
        device_id = request.cookies.get('dispositivo_id')
        
        # 1. Caso: No hay cookie. Debe ir a identificación.
        if not device_id:
            print("🚫 ACCESO DENEGADO (Sin cookie): Redirigiendo a identificación.")
            flash('Acceso no autorizado. Por favor, identifique el dispositivo.', 'error')
            # Redirigimos directamente a la identificación
            return redirect(url_for('identificar_dispositivo_route'))

        rol = get_user_rol_by_device_id(device_id)
        
        # 2. Caso: Hay cookie, pero el rol NO es Admin (o el rol es None/'' por base de datos vacía).
        if rol != 'Admin':
            print(f"🚫 ACCESO DENEGADO (Rol: {rol} en BD): Dispositivo no autorizado como Admin. Forzando re-identificación.")
            flash('Acceso restringido. Su dispositivo no tiene permisos de Administrador. Vuelva a identificarse si es necesario.', 'error')
            
            # --- CORRECCIÓN CRÍTICA: Eliminar la cookie antes de redirigir ---
            # Creamos la respuesta de redirección.
            response = redirect(url_for('identificar_dispositivo_route'))
            # Eliminamos la cookie problemática.
            response.set_cookie('dispositivo_id', '', expires=0) 
            return response
            
        # 3. Caso: Rol es Admin. Permitir acceso.
        return f(*args, **kwargs)

    return decorated_function

def get_medicamento_stock(conn, medicamento_id):
    """Calcula el stock actual de un medicamento sumando entradas y restando salidas de la tabla existencias."""
    stock_cur = conn.execute("""
        SELECT 
            SUM(CASE WHEN tipo_movimiento='entrada' THEN cantidad ELSE -cantidad END) AS stock_total
        FROM existencias
        WHERE medicamento_id = ?
    """, (medicamento_id,)).fetchone()
    
    return stock_cur['stock_total'] if stock_cur and stock_cur['stock_total'] is not None else 0


# ###################################################################
# ### COMIENZA ZONA 2: SISTEMA: DISPOSITIVOS & USUARIOS ###
# ###################################################################

def get_user_rol_by_device_id(device_id):
    """Obtiene el rol (Admin/Cliente) desde la tabla 'USUARIOS'."""
    conn = get_db()
    try:
        # Nota: Asume que get_db() usa row_factory = sqlite3.Row
        cursor = conn.execute("SELECT rol FROM USUARIOS WHERE dispositivo_id = ?", (device_id,)) # AQUI ESTA EL CAMBIO DE TABLA
        result = cursor.fetchone()
        
        return result['rol'] if result else None
    except Exception as e:
        print(f"🚨 ERROR: get_user_rol_by_device_id falló: {e}")
        return None
    finally:
        if conn:
            conn.close()

def generar_dispositivo_id():
    """Genera un identificador único global (UUIDv4) para un nuevo dispositivo."""
    return str(uuid.uuid4())

def establecer_dispositivo_cookie(response, dispositivo_id):
    """Establece la cookie 'dispositivo_id' en la respuesta HTTP."""
    response.set_cookie(
        'dispositivo_id', 
        dispositivo_id, 
        max_age=365 * 24 * 60 * 60, 
        httponly=True,              
        samesite='Lax'              
    )
    print(f"🍪 Cookie 'dispositivo_id' {dispositivo_id[:8]}... establecida.")
    return response

def registrar_admin_master(device_id):
    """Registra o actualiza el dispositivo con el rol de 'Admin Master' en la BD."""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO usuario (dispositivo_id, codigo_acceso, rol)
            VALUES (?, ?, ?)
        """, (device_id, '9999', 'Admin')) 
        
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Error de BD al registrar/actualizar Admin Master: {e}")
        return False
        
    finally:
        if conn:
            conn.close()

def identificar_dispositivo(codigo_acceso):
    """Valida un código de acceso de un Cliente y lo asocia a un nuevo dispositivo_id."""
    conn = None
    nuevo_device_id = str(uuid.uuid4())
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Buscar usuario existente (excluyendo Admin Master '9999')
        cursor.execute("""
            SELECT id, rol 
            FROM usuario 
            WHERE codigo_acceso = ? AND codigo_acceso != '9999'
        """, (codigo_acceso,))
        usuario_existente = cursor.fetchone()
        
        if not usuario_existente:
            return (False, None, "Código de acceso no encontrado o inválido.")
            
        usuario_id_bd, rol_bd = usuario_existente
        
        # 2. Asignar el nuevo dispositivo_id al usuario
        cursor.execute("""
            UPDATE usuario 
            SET dispositivo_id = ?
            WHERE id = ?
        """, (nuevo_device_id, usuario_id_bd))
        
        conn.commit()
        
        mensaje = f"Usuario con rol '{rol_bd}'"
        
        return (True, nuevo_device_id, mensaje)
        
    except sqlite3.Error as e:
        print(f"❌ Error de BD al identificar dispositivo con código {codigo_acceso}: {e}")
        return (False, None, "Error interno de la base de datos.")
        
    finally:
        if conn:
            conn.close()



# La ruta donde se sirven los archivos subidos (imágenes de medicamentos)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Ruta CRÍTICA para servir archivos estáticos desde la carpeta de UPLOADS.
    Utilizada en plantillas con url_for('uploaded_file', filename=...)
    """
    # CRÍTICO: Utiliza la configuración global de la carpeta UPLOAD_FOLDER
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Asegúrate de que UPLOAD_FOLDER esté configurada, aunque ya debería estarlo
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ###################################################################
# ### COMIENZA ZONA 3: SISTEMA: ARCHIVOS & HASH ###
# ###################################################################

@app.route('/admin/medicamentos/editar/<int:medicamento_id>', methods=['GET', 'POST'])
@admin_required
def editar_medicamento_admin(medicamento_id):
    """Permite editar los datos de un medicamento existente, incluyendo la imagen."""
    conn = get_db()
    
    # Obtener el medicamento actual
    medicamento = conn.execute("SELECT * FROM medicamentos WHERE id = ?", (medicamento_id,)).fetchone()
    
    if not medicamento:
        conn.close()
        flash("Medicamento no encontrado.", "error")
        # Opción segura si el medicamento no existe: volver a la lista
        return redirect(url_for('gestion_medicamentos'))

    medicamento_dict = dict(medicamento) 

    if request.method == 'POST':
        nombre = request.form['nombre']
        presentacion = request.form['presentacion']
        concentracion = request.form['concentracion']
        stock_actual_str = request.form['stock_actual'] # El stock se gestiona en otra ruta, pero lo mantenemos para compatibilidad de forma
        codigo_atc_puro = request.form.get('codigo_atc_puro', '').upper().strip()
        descripcion_tecnica_atc = request.form.get('descripcion_tecnica_atc', '')
        
        # Mantenemos el nombre de la imagen actual por defecto
        imagen_filename = medicamento_dict.get('imagen') 

        # --- Lógica de Subida de Nueva Imagen (Igual que en nuevo_medicamento) ---
        if 'imagen' in request.files:
            file = request.files['imagen']
            
            if file.filename != '' and allowed_file(file.filename):
                
                # Usamos la misma lógica de hash que en nuevo_medicamento()
                # Asegúrate de que hash_image_content está definida y disponible en tu app.py
                file_hash = hash_image_content(file.stream) 
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename_to_save = f"{file_hash}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_to_save)
                
                # 3. Guardamos el archivo si NO EXISTE
                # Es CRÍTICO que el file.stream se rebobine antes de .save() si se leyó para el hash.
                file.stream.seek(0) # <-- Aseguramos que el puntero está al inicio
                
                if not os.path.exists(filepath):
                    # Asegúrate de que el archivo se guarda solo si el puntero está al inicio
                    file.save(filepath) 
                    
                imagen_filename = filename_to_save # ¡Actualizamos el nombre para el UPDATE!
        
        try:
            # 2. ACTUALIZAR (UPDATE) EL REGISTRO
            # Nota: El stock_actual real se recalcula, aquí solo actualizamos los metadatos
            conn.execute("""
                UPDATE MEDICAMENTOS SET 
                nombre = ?, presentacion = ?, concentracion = ?, imagen = ?,
                codigo_atc_puro = ?, descripcion_tecnica_atc = ?
                WHERE id = ?
            """, (nombre, presentacion, concentracion, imagen_filename, 
                  codigo_atc_puro, descripcion_tecnica_atc, medicamento_id))
            
            conn.commit()
            flash("Medicamento actualizado exitosamente.", "success")
            
            return redirect(url_for('lista_medicamentos'))
            
        except sqlite3.Error as e:
            flash(f"Error al actualizar el medicamento: {e}", "danger")
            conn.rollback()
        finally:
            conn.close()

    # Si es GET, mostramos el la lista de todos los medicamentos
    conn.close()
    return render_template('editar_medicamento.html', medicamento=medicamento_dict)



def allowed_file(filename):
    """Verifica si la extensión del archivo está permitida."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def hash_image_content(file_stream):
    """Calcula el hash SHA256 del contenido de un archivo de imagen."""
    hash_sha = hashlib.sha256()
    file_stream.seek(0)
    for chunk in iter(lambda: file_stream.read(4096), b''):
        hash_sha.update(chunk)
    file_stream.seek(0)
    return hash_sha.hexdigest()


# ###################################################################
# ### COMIENZA ZONA 4: API: CIMA & OCR ###
# ###################################################################

def obtener_clasificacion_cima(nombre_medicamento):
    """Busca un medicamento por su nombre en la API de CIMA y retorna la clasificación ATC."""
    if not nombre_medicamento:
        return None
        
    nombre_normalizado = nombre_medicamento.split('/')[0].strip()

    # [Lógica interna robusta de búsqueda CIMA]
    def buscar_clasificacion_en_resultados(url_consulta, source_type):
        try:
            response = requests.get(url_consulta, timeout=5)
            response.raise_for_status()
            data = response.json()
            resultados = data.get('resultados', [])

            for medicamento in resultados:
                codigo_atc = medicamento.get('codigoATC')
                nombre_atc = medicamento.get('nombreATC')
                
                if codigo_atc and nombre_atc:
                    print(f"✅ Éxito CIMA ({source_type}): Clasificación '{codigo_atc}' encontrada.")
                    return {"nombre": nombre_atc.title(), "codigo": codigo_atc}, len(resultados)

            return None, len(resultados)

        except (HTTPError, RequestException, json.JSONDecodeError) as e:
            return None, 0


    def buscar_por_ficha_tecnica(query_nombre, log_tag):
        try:
            url_list = f"https://cima.aemps.es/cima/rest/medicamentos?nombre={requests.utils.quote(query_nombre)}"
            response_list = requests.get(url_list, timeout=5)
            response_list.raise_for_status()
            data_list = response_list.json()
            
            codigo_registro = data_list.get('resultados', [])[0].get('nregistro')
            
            if codigo_registro:
                url_detalle = f"https://cima.aemps.es/cima/rest/medicamento?nregistro={codigo_registro}"
                response_detalle = requests.get(url_detalle, timeout=5)
                response_detalle.raise_for_status()
                data_detalle = response_detalle.json()

                codigo_atc = data_detalle.get('atcs')[0].get('codigo') if data_detalle.get('atcs') else None
                nombre_atc = data_detalle.get('atcs')[0].get('nombre') if data_detalle.get('atcs') else None
                
                if codigo_atc and nombre_atc:
                    print(f"🔥 Éxito CIMA ({log_tag}): Clasificación encontrada en Ficha Técnica para '{query_nombre}'.")
                    return {"nombre": nombre_atc.title(), "codigo": codigo_atc}
        except Exception as e:
            pass
        return None

    # --- ESTRATEGIA DE BÚSQUEDA ---
    url_nombre = f"https://cima.aemps.es/cima/rest/medicamentos?nombre={requests.utils.quote(nombre_normalizado)}"
    clasificacion, num_resultados = buscar_clasificacion_en_resultados(url_nombre, "Directo")
    if clasificacion:
        return clasificacion

    # Intento 2: Principio Activo
    if num_resultados > 0:
        # [Lógica para buscar por Principio Activo]
        try:
            response = requests.get(url_nombre, timeout=5)
            data = response.json()
            primer_resultado = data.get('resultados', [])[0]
            principio_activo = primer_resultado.get('pactivos')[0].get('nombre') if primer_resultado.get('pactivos') else None
            
            if principio_activo:
                url_pa = f"https://cima.aemps.es/cima/rest/medicamentos?pactivos={requests.utils.quote(principio_activo)}"
                clasificacion_pa, _ = buscar_clasificacion_en_resultados(url_pa, "PA")
                
                if clasificacion_pa:
                    return clasificacion_pa
        except Exception:
            pass

    # Intento 3: Ficha Técnica completa
    clasificacion_ft = buscar_por_ficha_tecnica(nombre_normalizado, "FT Completo")
    if clasificacion_ft:
        return clasificacion_ft

    # Intento 4: Respaldo por Ficha Técnica simplificada
    nombre_simplificado = nombre_normalizado.split(' ')[0]
    if nombre_simplificado.lower() != nombre_normalizado.lower() and len(nombre_simplificado) > 3:
        clasificacion_respaldo = buscar_por_ficha_tecnica(nombre_simplificado, "Respaldo-FT")
        if clasificacion_respaldo:
            return clasificacion_respaldo

    print(f"Advertencia: Fallo total. No se pudo obtener clasificación ('{nombre_medicamento}').")
    return None

@app.route("/ocr_procesar", methods=["POST"])
def ocr_procesar():
    """Endpoint AJAX para procesar la imagen subida con Tesseract OCR."""
    extracted_text = ""
    file = request.files.get("imagen_ocr")
    
    if file and file.filename != "" and allowed_file(file.filename):
        try:
            with tempfile.NamedTemporaryFile(delete=True) as tmp:
                file.save(tmp.name) 

                img = Image.open(tmp.name)
                img = ImageOps.exif_transpose(img)
                
                # Procesamiento de imagen para mejorar el OCR
                MAX_SIZE = (2048, 2048) 
                if img.width > MAX_SIZE[0] or img.height > MAX_SIZE[1]:
                    img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS) 

                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
                img = img.convert('L')
                
                extracted_text = pytesseract.image_to_string(img, lang='spa+eng') 
                
                # --- Lógica de limpieza de texto ---
                lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
                if lines:
                    cleaned_name = ''.join(c for c in lines[0] if c.isalnum() or c.isspace() or c in '.-_').strip()
                    extracted_text = cleaned_name if cleaned_name else lines[0] 
                else:
                    extracted_text = ""

        except Exception as e:
            print(f"Error durante el proceso OCR: {e}")
            extracted_text = ""
    
    return jsonify({"nombre_detectado": extracted_text})


# ###################################################################
# ### COMIENZA ZONA 5: RUTAS DE ACCESO PÚBLICO (INICIO Y CONSULTA) ###
# ###################################################################

# ... código anterior de imports y configuración ...

@app.route('/')
def inicio():
    """Ruta principal: gestiona la identificación del dispositivo y redirige."""
    device_id = request.cookies.get('dispositivo_id')
    
    if not device_id:
        print("🚨 Dispositivo no identificado. Redirigiendo a /identificar_dispositivo")
        return redirect(url_for('identificar_dispositivo_route')) 
        
    rol = get_user_rol_by_device_id(device_id) 
    
    if rol == 'Admin':
        # El dispositivo actual está logueado como Admin.
        print(f"✅ Dispositivo {device_id} identificado como Admin. Redirigiendo a /admin_menu")
        return redirect(url_for('admin_menu'))
    
    elif rol == 'Cliente':
        # Si tiene device_id y es Cliente.
        print(f"✅ Dispositivo {device_id} identificado como rol '{rol}'. Redirigiendo a /consulta_sintomas")
        return redirect(url_for('consulta_sintomas'))
    
    else:
        # CRÍTICO: El ID existe en la cookie pero el rol es nulo o inválido en la DB.
        print(f"❌ ERROR: Dispositivo {device_id} tiene cookie pero rol '{rol}' inválido. Forzando re-identificación.")
        flash("Dispositivo no reconocido. Su ID de sesión es inválido. Por favor, identifíquese de nuevo.", "warning")
        response = make_response(redirect(url_for('identificar_dispositivo_route')))
        response.delete_cookie('dispositivo_id')
        return response

@app.route('/admin')
def admin_shortcut():
    """Ruta de atajo para forzar la identificación como Admin."""
    print("➡️ Redirigiendo atajo /admin a la ruta de identificación con rol_master=Admin.")
    # Redirige a /identificar_dispositivo?rol_master=Admin
    return redirect(url_for('identificar_dispositivo_route', rol_master='Admin'))


@app.route('/consulta', methods=['GET'])
def consulta_sintomas():
    """Muestra la interfaz de consulta de síntomas."""
    conn = get_db()
    sintomas = conn.execute("SELECT id, descripcion FROM sintomas ORDER BY descripcion").fetchall() 
    conn.close()
    return render_template('consulta_sintomas.html', sintomas_disponibles=sintomas)

@app.route('/sugerencias', methods=['POST'])
def mostrar_sugerencias():
    """Motor de diagnóstico: asocia síntomas seleccionados con diagnósticos y medicamentos."""
    sintomas_ids = request.form.getlist('sintomas_ids')
    
    if not sintomas_ids:
        flash("Debes seleccionar al menos un síntoma para la consulta.", 'warning')
        return redirect(url_for('consulta_sintomas'))
        
    conn = get_db()
    
    # 1. Buscar Diagnósticos asociados a los síntomas seleccionados
    placeholders = ','.join('?' * len(sintomas_ids))
    query_diagnosticos = f"""
        SELECT D.id, D.descripcion, D.codigo_atc, D.fuente, 
               COUNT(DS.sintoma_id) AS coincidencias
        FROM diagnosticos D 
        JOIN diagnostico_sintoma DS ON D.id = DS.diagnostico_id
        WHERE DS.sintoma_id IN ({placeholders})
        GROUP BY D.id 
        ORDER BY coincidencias DESC, D.descripcion ASC
    """
    diagnosticos_sugeridos = conn.execute(query_diagnosticos, sintomas_ids).fetchall()
    
    sugerencias_finales = []
    
    for diagnostico in diagnosticos_sugeridos:
        # 2. Para cada diagnóstico, buscar los medicamentos asociados
        medicamentos_asociados = conn.execute(
            """
            SELECT M.nombre, M.presentacion, M.codigo_atc_puro 
            FROM medicamentos M 
            JOIN diagnostico_medicamento DM ON M.id = DM.medicamento_id 
            WHERE DM.diagnostico_id = ?
            """, 
            (diagnostico['id'],)
        ).fetchall()
        
        sugerencias_finales.append({
            'diagnostico_nombre': diagnostico['descripcion'],
            'codigo_atc': diagnostico['codigo_atc'],
            'coincidencias': diagnostico['coincidencias'],
            'medicamentos': [dict(m) for m in medicamentos_asociados]
        })
        
    conn.close()

    return render_template('consulta_sintomas.html', 
        sugerencias=sugerencias_finales, 
        sintomas_seleccionados_ids=sintomas_ids
    )
# ===================================================================
# FUNCIONES DE UTILIDAD (Para evitar errores de 'variable no definida')
# Estas deben estar cerca de la zona de imports o utilidades.
# ===================================================================

# ===================================================================
# RUTA /IDENTIFICAR_DISPOSITIVO (Corregida)
# ===================================================================

def update_client_profile(device_id, data):
    # Lógica de actualización progresiva para el Cliente.
    # Usa 'device_id' para encontrar la fila y actualiza los campos en 'data'.
    print(f"DB ACTION: Actualizando Cliente {device_id} con datos: {data}")
    # --- REEMPLAZA ESTO CON TU FUNCIÓN REAL DE ACTUALIZACIÓN EN SQLite ---
    pass

@app.route('/identificar_dispositivo', methods=['GET', 'POST'])
def identificar_dispositivo_route():
    """
    Maneja la identificación:
    - GET: Muestra la plantilla de Admin o Cliente.
    - POST: Lógica síncrona para Admin, y asíncrona (guardado progresivo) para Cliente.
    """
    
    # ------------------ LÓGICA POST ------------------
    if request.method == 'POST':
        try:
            # 1. Obtener todos los datos posibles (vienen de la forma Admin o Cliente/AJAX)
            nombre = request.form.get('nombre', '').strip()
            rol_master = request.form.get('rol_master') 
            
            # Datos de Cliente para guardado progresivo
            edad = request.form.get('edad')
            peso_aprox = request.form.get('peso_aprox')
            genero = request.form.get('genero')
            
            # Intentar obtener el ID del dispositivo de la cookie
            dispositivo_id = request.cookies.get('dispositivo_id')
            
            # ==========================================================
            # A. LÓGICA SÍNCRONA DE ADMINISTRADOR (Mantiene el flujo original)
            # ==========================================================
            if rol_master == 'Admin':
                
                if not nombre:
                    flash('El nombre del Administrador es obligatorio.', 'error')
                    return redirect(url_for('identificar_dispositivo_route', rol_master='Admin'))
                
                # 1. Obtener/Crear ID de Dispositivo (Aseguramos que esta línea esté aquí)
                device_id = request.cookies.get('device_id') or str(uuid.uuid4())
                
                try:
                    # 🚨 SIMULACIÓN: Registro en DB
                    conn = get_db()
                    # Asegúrate de que tu device_id exista y sea una cadena válida
                    db_manager.register_device_id(conn, device_id, 'Admin', nombre_usuario=nombre)
                except Exception as e:
                    flash('Error al registrar dispositivo en la DB.', 'error')
                    print(f"Error DB en Admin: {e}")
                    return redirect(url_for('identificar_dispositivo_route', rol_master='Admin'))
                
                # --- ZONA CRÍTICA DE REDIRECCIÓN Y COOKIE ---
                flash(f'¡Bienvenido, Administrador {nombre}! Acceso concedido.', 'success')
                
                # PASO A: Crear una respuesta de redirección HTTP 302.
                # Necesitamos make_response para manipular la cabecera.
                resp = make_response(redirect(url_for('admin_menu_route')))
                
                # PASO B: Adjuntar la cookie del dispositivo a ESA respuesta (la redirección).
                resp.set_cookie('device_id', device_id, max_age=365 * 24 * 60 * 60, httponly=True)
                
                # PASO C: Retornar la respuesta.
                return resp

            # ==========================================================
            # B. LÓGICA SINCRONA DE CLIENTE (Redirección HTTP y Cookies)
            # ==========================================================
            elif rol_master == 'Cliente':
                
                # CRÍTICO: Obtener el ID de la cookie o generar uno nuevo si es la primera visita
                # NOTA: Necesitas tener 'uuid' importado (import uuid) al inicio del archivo.
                dispositivo_id = request.cookies.get('dispositivo_id') or str(uuid.uuid4())

                try:
                    conn = get_db()
                    # Busca el usuario por el ID del dispositivo.
                    usuario_existente = db_manager.get_user_by_device_id(conn, dispositivo_id)
                        
                    if usuario_existente:
                        # CASO 2A: Cliente conocido (tiene cookie y registro en DB)
                        # Redirige al saludo persistente.
                        resp = make_response(redirect(url_for('saludo_persistente_route', nombre=usuario_existente['nombre'])))
                        
                        # Establecer/refrescar la cookie del dispositivo
                        resp.set_cookie('dispositivo_id', dispositivo_id, max_age=365 * 24 * 60 * 60, httponly=True)
                        flash(f'Bienvenido de vuelta, {usuario_existente["nombre"]}.', 'success')
                        return resp
                    else:
                        # CASO 2B: Cliente nuevo o desconocido.
                        # Redirigimos a la pantalla de registro para obtener el nombre inicial.
                        
                        # Crear la respuesta de redirección
                        resp = make_response(redirect(url_for('registro_dispositivo_route')))
                        
                        # CRÍTICO: Establecer la cookie por primera vez
                        resp.set_cookie('dispositivo_id', dispositivo_id, max_age=365 * 24 * 60 * 60, httponly=True)
                        flash('Dispositivo no reconocido. Por favor, crea un usuario para continuar.', 'info')
                        return resp
                        
                except Exception as e:
                    flash('Error al procesar la solicitud del cliente.', 'error')
                    print(f"Error DB en Cliente: {e}")
                    # Volver a la home o al formulario de identificación
                    return redirect(url_for('home')) 

            # C. Petición POST con rol_master faltante
            else:
                flash('Petición POST inválida. Rol maestro no especificado.', 'error')
                return redirect(url_for('home'))


        except Exception as e:
            # Manejo de errores que no son de validación de formulario (errores críticos)
            print(f"Error crítico en POST de identificación: {e}")
            
            # Si el error ocurrió durante un POST asíncrono (Cliente), devuelve JSON 500
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Error interno del servidor", "details": str(e)}), 500
            
            # Si el error ocurrió durante un POST síncrono (Admin), usa flash/redirect
            flash(f"Error crítico durante la identificación. Revise la consola: {e}", "danger")
            return redirect(url_for('identificar_dispositivo_route')) 

    # ------------------ LÓGICA GET ------------------
    device_id = request.cookies.get('dispositivo_id')
    
    # 1. Si ya tiene una cookie válida y un rol asociado, lo enviamos al controlador principal (inicio)
    if device_id and get_user_rol_by_device_id(device_id):
        return redirect(url_for('inicio'))

    # 2. Si no está identificado, decide qué plantilla mostrar
    rol_master = request.args.get('rol_master', 'Cliente') 
    
    if rol_master == 'Admin':
        # Renderizamos la plantilla simple para el administrador
        return render_template('admin_identificacion.html', rol_master=rol_master)
    else:
        # Renderizamos la plantilla conversacional/normal para el Cliente
        return render_template('identificar_dispositivo.html', rol_master=rol_master)



@app.route('/identificar_dispositivo', methods=['POST'])
def identificar_dispositivo_post():
    """
    [CRÍTICA] Esta ruta maneja el formulario de selección de rol (Cliente/Admin)
    y gestiona la persistencia del ID del dispositivo mediante cookies.
    """
    rol_master = request.form.get('rol_master')
    
    # Simulación de función de DB para buscar el nombre del usuario por su ID de dispositivo.
    # REEMPLAZAR con tu función real si usas un módulo db_manager
    def mock_get_user_by_device_id(conn, device_id):
        cursor = conn.cursor()
        # Buscamos el nombre en la tabla USUARIOS usando el dispositivo_id
        cursor.execute("SELECT nombre FROM USUARIOS WHERE dispositivo_id = ?", (device_id,))
        result = cursor.fetchone()
        # Retorna el nombre si existe, o None
        return {'nombre': result[0]} if result else None

    if rol_master == 'Admin':
        # LÓGICA ADMINISTRADOR (Redirección simple a admin_dashboard, si existe)
        flash('Modo Administrador seleccionado.', 'info')
        # Cambia 'admin_dashboard' a la ruta de tu panel de admin si tiene otro nombre
        return redirect(url_for('admin_dashboard')) 
            
    # ==========================================================
    # LÓGICA SINCRONA DE CLIENTE (Redirección HTTP y Cookies)
    # ==========================================================
    elif rol_master == 'Cliente':
        
        # Obtener el ID de la cookie o generar uno nuevo si es la primera visita
        # Asegúrate de tener 'import uuid' al inicio de tu app.py
        dispositivo_id = request.cookies.get('dispositivo_id') or str(uuid.uuid4())

        try:
            conn = get_db()
            
            # Usar la función para verificar la existencia del usuario
            usuario_existente = mock_get_user_by_device_id(conn, dispositivo_id)
                
            if usuario_existente:
                # CASO 2A: Cliente conocido (Redirige al saludo persistente)
                resp = make_response(redirect(url_for('saludo_persistente_route', nombre=usuario_existente['nombre'])))
                
                # Establecer/refrescar la cookie del dispositivo
                resp.set_cookie('dispositivo_id', dispositivo_id, max_age=365 * 24 * 60 * 60, httponly=True)
                flash(f'Bienvenido de vuelta, {usuario_existente["nombre"]}.', 'success')
                return resp
            else:
                # CASO 2B: Cliente nuevo (Redirige al registro)
                
                resp = make_response(redirect(url_for('registro_dispositivo_route')))
                
                # CRÍTICO: Establecer la cookie por primera vez (la usaremos en registro_dispositivo_route)
                resp.set_cookie('dispositivo_id', dispositivo_id, max_age=365 * 24 * 60 * 60, httponly=True)
                flash('Dispositivo no reconocido. Por favor, crea un usuario para continuar.', 'info')
                return resp
                
        except Exception as e:
            flash('Error al procesar la solicitud del cliente.', 'error')
            print(f"Error DB en Cliente: {e}")
            return redirect(url_for('home')) 

    # Petición POST con rol_master faltante
    else:
        flash('Petición POST inválida. Rol maestro no especificado.', 'error')
        return redirect(url_for('home'))

# --- RUTAS DE DESTINO DEL FLUJO CLIENTE (NUEVAS) ---

@app.route('/saludo_persistente/<nombre>')
def saludo_persistente_route(nombre):
    """
    [NUEVA RUTA] Muestra la pantalla de saludo para Clientes conocidos.
    """
    return render_template('saludo_persistente.html', nombre=nombre)


@app.route('/registro_dispositivo', methods=['GET', 'POST'])
def registro_dispositivo_route():
    """
    [NUEVA RUTA] Maneja el registro inicial de Clientes nuevos.
    """
    dispositivo_id = request.cookies.get('dispositivo_id') # Debe existir

    if request.method == 'POST':
        nombre_cliente = request.form.get('nombre_cliente')

        if nombre_cliente and dispositivo_id:
            try:
                conn = get_db()
                # 1. Crear el nuevo usuario en la tabla USUARIOS
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO USUARIOS (nombre, rol, dispositivo_id) VALUES (?, ?, ?)",
                    (nombre_cliente, 'Cliente', dispositivo_id)
                )
                conn.commit()

                flash(f'Bienvenido, {nombre_cliente}. Tu perfil ha sido creado.', 'success')
                # Redireccionamos a la ruta de saludo, que luego lleva a la consulta
                return redirect(url_for('saludo_persistente_route', nombre=nombre_cliente))

            except sqlite3.IntegrityError:
                flash('Error: El nombre de usuario ya está en uso. Por favor, elige otro.', 'error')
            except Exception as e:
                flash('Error al guardar el nuevo usuario.', 'error')
                print(f"Error al registrar cliente: {e}")
        else:
            flash('Falta el nombre para registrarte. Inténtalo de nuevo.', 'error')

        return render_template('registro_dispositivo.html')

    # Si es GET, simplemente muestra el formulario
    return render_template('registro_dispositivo.html')






# ###################################################################
# ### COMIENZA ZONA 6: RUTAS DE ADMINISTRACIÓN CORE ###
# ###################################################################


@app.route('/admin_menu')
@admin_required
def admin_menu():
    """Muestra el menú principal de administración."""
    return render_template('admin_menu.html')

@app.route('/logout')
def logout():
    """Cierra la sesión de seguridad eliminando la cookie de dispositivo."""
    response = make_response(redirect(url_for('inicio')))
    response.set_cookie('dispositivo_id', '', expires=0)
    flash("Sesión cerrada. El dispositivo ya no está identificado.", 'info')
    return response


# app.py (AGREGAR ESTO EN LA ZONA 6)

@app.route('/admin/registrar/nuevo-admin', methods=['GET', 'POST'])
@admin_required
def registro_admin_form_protegido(): 
    """
    Ruta para mostrar y procesar el formulario de registro de un nuevo administrador.
    El nombre de la función ('registro_admin_form_protegido') coincide 
    con el 'url_for' solicitado en admin_menu.html
    """
    
    if request.method == 'POST':
        # Aquí iría la lógica para guardar el nuevo administrador en la DB
        # (similar a finalizar_bienvenida_api, pero para un admin ya logueado)
        flash("Nuevo usuario administrador registrado exitosamente. (LÓGICA PENDIENTE)", "success")
        return redirect(url_for('admin_menu')) # Redirige después de guardar
        
    # Asumimos que tienes una plantilla llamada 'registro_admin_form.html'
    return render_template('registro_admin_form.html')


# ###################################################################
# ### COMIENZA ZONA 7: MÓDULO INVENTARIO (CRUD) ###
# ###################################################################

@app.route('/admin/medicamentos', methods=['GET', 'POST'])
@admin_required
def lista_medicamentos():
    """Lista todos los medicamentos y muestra la gestión de stock."""
    conn = get_db()
    # Se recuperan los campos básicos y se utiliza un LEFT JOIN para asegurar que
    # aunque la columna ATC sea NULL, el medicamento se muestre.
    meds = conn.execute("SELECT * FROM medicamentos ORDER BY nombre").fetchall()

    medicamentos_listos = []
    for med in meds:
        med_dict = dict(med) 
        # Aseguramos que el stock se calcule dinámicamente
        med_dict['stock_actual'] = get_medicamento_stock(conn, med['id'])
        medicamentos_listos.append(med_dict)
        
    conn.close()
    return render_template("gestion_medicamentos.html", medicamentos=medicamentos_listos)


@app.route("/admin/medicamentos/nuevo", methods=['GET', 'POST']) 
@admin_required
def nuevo_medicamento():
    """Ruta para agregar un nuevo medicamento, incluyendo subida de imagen y registro de stock inicial."""
    if request.method == 'POST':
        nombre = request.form['nombre']
        concentracion = request.form['concentracion']
        presentacion = request.form['presentacion']
        fabricante_nombre = request.form['fabricante_nombre'].strip()
        
        # Validar y convertir cantidad inicial a entero
        try:
            cantidad_inicial = int(request.form['cantidad_inicial'])
        except ValueError:
            flash("La cantidad inicial debe ser un número entero válido.", "error")
            return redirect(url_for('nuevo_medicamento'))
            
        codigo_atc_puro = request.form.get('codigo_atc_puro', '').upper().strip()
        descripcion_tecnica_atc = request.form.get('descripcion_tecnica_atc', '')
        
        imagen_filename = None
        conn = get_db()

        # 1. PROCESO DE SUBIDA DE IMAGEN
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file.filename != '' and allowed_file(file.filename):
                
                file_hash = hash_image_content(file.stream)
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename_to_save = f"{file_hash}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_to_save)
                
                # Guarda el archivo solo si no existe, utilizando el hash como nombre
                if not os.path.exists(filepath):
                    file.save(filepath)
                imagen_filename = filename_to_save

        try:
            # 2. PROCESO DE FABRICANTE
            fabricante = conn.execute("SELECT id FROM fabricantes WHERE nombre = ?", (fabricante_nombre,)).fetchone()
            if fabricante is None:
                cursor = conn.execute("INSERT INTO fabricantes (nombre) VALUES (?)", (fabricante_nombre,))
                fabricante_id = cursor.lastrowid
            else:
                fabricante_id = fabricante['id']

            # 3. PROCESO DE MEDICAMENTO
            cursor = conn.execute(
                "INSERT INTO medicamentos (nombre, concentracion, presentacion, codigo_atc_puro, descripcion_tecnica_atc, imagen) VALUES (?, ?, ?, ?, ?, ?)",
                (nombre, concentracion, presentacion, codigo_atc_puro, descripcion_tecnica_atc, imagen_filename)
            )
            medicamento_id = cursor.lastrowid

            # 4. PROCESO DE EXISTENCIA (Stock inicial)
            if cantidad_inicial > 0:
                 conn.execute(
                    "INSERT INTO existencias (medicamento_id, fabricante_id, tipo_movimiento, cantidad, fecha) VALUES (?, ?, 'entrada', ?, ?)",
                    (medicamento_id, fabricante_id, cantidad_inicial, datetime.now())
                )
            
            conn.commit()
            flash(f"Medicamento '{nombre}' creado exitosamente.", "success")
            
        except sqlite3.Error as e:
            print(f"Error al guardar medicamento o existencia: {e}")
            conn.rollback()
            flash(f"Error al guardar el medicamento: {e}", "danger")
            return redirect(url_for('nuevo_medicamento'))
        
        finally:
            conn.close()
            
        return redirect(url_for('lista_medicamentos'))
        
    return render_template('nuevo_medicamento.html')



@app.route("/medicamentos/eliminar/<int:medicamento_id>", methods=["POST"])
@admin_required
def eliminar_medicamento(medicamento_id):
    """Ruta POST para eliminar un medicamento y sus dependencias (stock, asociaciones, imagen)."""
    conn = get_db()
    conn.execute("BEGIN TRANSACTION")
    try:
        cur = conn.execute("SELECT imagen FROM medicamentos WHERE id=?", (medicamento_id,)).fetchone()
        imagen_filename = cur['imagen'] if cur and 'imagen' in cur else None

        # Eliminar registros relacionados explícitamente
        conn.execute("DELETE FROM precios WHERE medicamento_id=?", (medicamento_id,))
        conn.execute("DELETE FROM precios_competencia WHERE medicamento_id=?", (medicamento_id,))
        conn.execute("DELETE FROM medicamento_sintoma WHERE medicamento_id=?", (medicamento_id,))
        conn.execute("DELETE FROM movimientos_inventario WHERE medicamento_id=?", (medicamento_id,))
        conn.execute("DELETE FROM existencias WHERE medicamento_id=?", (medicamento_id,))
        conn.execute("DELETE FROM diagnostico_medicamento WHERE medicamento_id=?", (medicamento_id,))

        # Eliminar registro principal al final
        conn.execute("DELETE FROM medicamentos WHERE id=?", (medicamento_id,))

        if imagen_filename:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], imagen_filename)
            # Solo borramos el archivo físico si ningún otro medicamento lo referencia
            if os.path.exists(file_path):
                # Contamos cuántos medicamentos aún usan esta imagen
                count_refs = conn.execute("SELECT COUNT(*) FROM medicamentos WHERE imagen=?", (imagen_filename,)).fetchone()[0]
                if count_refs == 0:
                    os.remove(file_path)
                    print(f"🗑️ Imagen {imagen_filename} eliminada del disco.")
                else:
                    print(f"⚠️ Imagen {imagen_filename} mantenida: referenciada por {count_refs} otros medicamentos.")

        conn.commit()
        # Si es petición AJAX, devolver JSON para que el cliente pueda actualizar la interfaz sin recargar
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.accept_mimetypes.accept_json:
            conn.close()
            return jsonify({'ok': True, 'medicamento_id': medicamento_id})
        flash(f"Medicamento ID {medicamento_id} y sus registros asociados eliminados completamente.", "success")
    except (sqlite3.Error, Exception) as e:
        conn.rollback()
        print(f"Error al eliminar medicamento: {e}")
        # Responder apropiadamente según el tipo de petición
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.accept_mimetypes.accept_json:
            conn.close()
            return jsonify({'ok': False, 'error': str(e)}), 500
        flash("Error al eliminar el medicamento y sus dependencias.", "danger")
    finally:
        conn.close()
    return redirect(url_for("lista_medicamentos"))


# ###################################################################
# ### COMIENZA ZONA 8: MÓDULO CATÁLOGOS MÉDICOS ###
# ###################################################################

# --- Síntomas ---
@app.route("/sintomas")
@admin_required
def lista_sintomas():
    conn = get_db()
    datos = conn.execute("SELECT * FROM sintomas ORDER BY descripcion").fetchall()
    conn.close()
    return render_template("sintomas.html", sintomas=datos)

@app.route("/sintomas/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_sintoma():
    if request.method == "POST":
        descripcion = request.form.get("descripcion", "").strip()
        if descripcion:
            conn = get_db()
            try:
                conn.execute("INSERT OR IGNORE INTO sintomas (descripcion) VALUES (?)", (descripcion,))
                conn.commit()
                flash("Síntoma agregado ✅", "success")
            except sqlite3.Error:
                flash("Error al guardar el síntoma.", "danger")
            finally:
                conn.close()
            return redirect(url_for("lista_sintomas"))
    return render_template("nuevo_sintoma.html")

# --- Diagnósticos ---
@app.route("/diagnosticos")
@admin_required
def lista_diagnosticos():
    conn = get_db()
    datos = conn.execute("SELECT * FROM diagnosticos ORDER BY descripcion").fetchall()
    conn.close()
    return render_template("diagnosticos.html", diagnosticos=datos)

@app.route("/diagnosticos/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_diagnostico():
    if request.method == "POST":
        descripcion = request.form.get("descripcion", "").strip()
        codigo_atc = request.form.get("codigo_atc", "").strip().upper()
        if descripcion:
            conn = get_db()
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO diagnosticos (descripcion, codigo_atc, fuente) VALUES (?, ?, 'Manual')",
                    (descripcion, codigo_atc)
                )
                conn.commit()
                flash("Diagnóstico agregado ✅", "success")
            except sqlite3.Error:
                flash("Error al guardar el diagnóstico.", "danger")
            finally:
                conn.close()
            return redirect(url_for("lista_diagnosticos"))
    return render_template("nuevo_diagnostico.html")

@app.route("/diagnosticos/asociar/<int:medicamento_id>", methods=["GET", "POST"])
@admin_required
def asociar_diagnostico_med(medicamento_id):
    """Permite al Admin asociar Diagnósticos existentes con un Medicamento."""
    conn = get_db()
    
    # Lógica de GET (mostrar formularios)
    if request.method == "GET":
        medicamento = conn.execute("SELECT nombre, presentacion FROM medicamentos WHERE id=?", (medicamento_id,)).fetchone()
        diagnosticos_disp = conn.execute("SELECT id, descripcion, codigo_atc FROM diagnosticos ORDER BY descripcion").fetchall()
        asociaciones_exist = conn.execute(
            """
            SELECT D.descripcion, D.codigo_atc 
            FROM diagnostico_medicamento DM
            JOIN diagnosticos D ON D.id = DM.diagnostico_id
            WHERE DM.medicamento_id = ?
            """,
            (medicamento_id,)
        ).fetchall()
        
        conn.close()
        
        if not medicamento:
            flash("Medicamento no encontrado.", "danger")
            return redirect(url_for('lista_medicamentos'))

        return render_template(
            "asociar_diagnostico.html",
            medicamento=medicamento,
            diagnosticos_disp=diagnosticos_disp,
            asociaciones_exist=asociaciones_exist,
            medicamento_id=medicamento_id
        )

    # Lógica de POST (guardar asociaciones)
    if request.method == "POST":
        diagnosticos_ids = request.form.getlist('diagnosticos_ids')
        
        try:
            conn.execute("DELETE FROM diagnostico_medicamento WHERE medicamento_id=?", (medicamento_id,))
            
            if diagnosticos_ids:
                data_to_insert = [(medicamento_id, int(diag_id)) for diag_id in diagnosticos_ids]
                conn.executemany(
                    "INSERT INTO diagnostico_medicamento (medicamento_id, diagnostico_id) VALUES (?, ?)",
                    data_to_insert
                )
            
            conn.commit()
            flash("Asociaciones de diagnóstico actualizadas correctamente. ✅", "success")
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Error al guardar las asociaciones: {e}", "danger")
        finally:
            conn.close()
            
        return redirect(url_for('lista_medicamentos'))


# ###################################################################
# ### COMIENZA ZONA 9: RUTAS AJAX (METADATOS) ###
# ###################################################################

@app.route("/api/registrar_clasificacion_atc/<int:medicamento_id>", methods=["POST"])
@admin_required
def registrar_clasificacion_atc(medicamento_id):
    """Guarda el código y nombre ATC en el medicamento específico (desde la interfaz AJAX)."""
    data = request.get_json()
    nombre_atc = data.get('nombre_atc', '').strip()
    codigo_atc = data.get('codigo_atc', '').strip()
    
    if not nombre_atc or not codigo_atc:
        return jsonify({"success": False, "message": "Faltan datos de ATC (nombre o código)."}), 400

    conn = get_db()
    try:
        conn.execute(
            "UPDATE medicamentos SET descripcion_tecnica_atc=?, codigo_atc_puro=?, fuente_atc=? WHERE id=?", 
            (nombre_atc, codigo_atc, "ATC/CIMA", medicamento_id) 
        )
        conn.commit()
        
        return jsonify({
            "success": True, 
            "message": f"Clasificación ATC ({codigo_atc}) guardada en el medicamento.", 
            "codigo_atc": codigo_atc
        }), 200
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error al guardar ATC en medicamentos: {e}")
        return jsonify({"success": False, "message": "Error interno de la base de datos."}), 500
            
    finally:
        conn.close()


@app.route("/api/sugerir_diagnosticos/<int:medicamento_id>", methods=["GET"])
@admin_required
def sugerir_diagnosticos(medicamento_id):
    """Busca en CIMA el código ATC para sugerir una indicación al Admin."""
    conn = get_db()
    med = conn.execute(
        "SELECT nombre, descripcion_tecnica_atc, codigo_atc_puro FROM medicamentos WHERE id=?", 
        (medicamento_id,)
    ).fetchone()
    conn.close()

    if not med:
        return jsonify({"success": False, "message": "Medicamento no encontrado."}), 404

    nombre_medicamento = med["nombre"]
    
    # 1. Chequear si la clasificación ya existe
    if med["codigo_atc_puro"] and med["descripcion_tecnica_atc"]:
        sugerencias_indicaciones = [
            f"{med['descripcion_tecnica_atc']} ({med['codigo_atc_puro']})"
        ]
        return jsonify({
            "success": True, 
            "nombre_base": nombre_medicamento,
            "indicaciones_sugeridas": sugerencias_indicaciones,
            "es_atc_guardado": True
        })

    # 2. Si no existe, buscar en CIMA (función de ZONA 4)
    clasificacion_atc = obtener_clasificacion_cima(nombre_medicamento)
    
    if clasificacion_atc:
        indicacion_sugerida = f"{clasificacion_atc['nombre']} ({clasificacion_atc['codigo']})"
        
        return jsonify({
            "success": True, 
            "nombre_base": nombre_medicamento,
            "indicaciones_sugeridas": [indicacion_sugerida],
            "atc_puro": clasificacion_atc 
        })
    
    # 3. Fallo total
    return jsonify({
        "success": False, 
        "message": f"No se pudo encontrar una clasificación ATC (indicación) para: {nombre_medicamento}"
    }), 404
    
@app.route("/api/registrar_diagnosticos", methods=["POST"])
@admin_required
def registrar_diagnosticos_api():
    """Registra nuevos diagnósticos o clasificaciones ATC como diagnósticos si no existen (desde interfaz AJAX)."""
    data = request.get_json()
    nuevos_diagnosticos = data.get('diagnosticos', [])
    
    if not nuevos_diagnosticos:
        return jsonify({"success": False, "message": "No se recibieron diagnósticos para registrar."}), 400

    conn = get_db()
    registrados_count = 0
    
    try:
        diagnosticos_a_insertar = []
        for d in nuevos_diagnosticos:
            descripcion_original = d.strip()
            if not descripcion_original:
                continue

            codigo_atc = None
            fuente = None
            descripcion = descripcion_original
            
            # --- Lógica de Extracción de ATC ---
            match = re.search(r'^(.*)\s\((.+)\)$', descripcion_original)
            
            if match:
                descripcion = match.group(1).strip()  
                codigo_atc = match.group(2).strip()  
                fuente = "ATC/CIMA"
                
                # Chequeo de duplicado por código ATC
                cur = conn.execute("SELECT id FROM diagnosticos WHERE codigo_atc = ?", (codigo_atc,)).fetchone()
                if cur:
                    continue 
            else:
                # Chequeo de duplicado por descripción
                cur = conn.execute("SELECT id FROM diagnosticos WHERE descripcion = ?", (descripcion,)).fetchone()
                if cur:
                    continue
            
            diagnosticos_a_insertar.append((descripcion, codigo_atc, fuente))


        if diagnosticos_a_insertar:
            cur = conn.executemany(
                "INSERT INTO diagnosticos (descripcion, codigo_atc, fuente) VALUES (?, ?, ?)",
                diagnosticos_a_insertar
            )
            registrados_count = cur.rowcount
            conn.commit()
            
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error al insertar múltiples diagnósticos (incluyendo ATC): {e}")
        return jsonify({"success": False, "message": "Error interno de la base de datos."}), 500
            
    finally:
        conn.close()
        
    return jsonify({
        "success": True, 
        "message": f"Se registraron {registrados_count} nuevos diagnósticos/clasificaciones (ignorados duplicados).",
        "count": registrados_count
    })


# ... otras rutas AJAX ...
# app.py (ZONA 9) - Rutas AJAX (Metadatos y Registro)

@app.route("/api/finalizar_bienvenida", methods=["POST"])
def finalizar_bienvenida_api():
    """
    Ruta AJAX llamada por bienvenida.js.
    Asigna un nuevo dispositivo_id, guarda los datos del usuario 
    con el rol enviado y establece la cookie.
    """
    data = request.get_json()
    rol_deseado = data.get('rol', 'Cliente') 
    
    # Validamos que el rol sea uno de los permitidos
    if rol_deseado not in ['Admin', 'Cliente']:
        return jsonify({"status": "error", "message": "Rol no válido."}), 400

    nuevo_device_id = generar_dispositivo_id()
    
    # 🛑 CAMBIO CRÍTICO DE LÓGICA 🛑
    # El nombre DEBE ser UNIQUE. Si no se provee nombre, usamos el dispositivo_id como marcador.
    nombre_input = data.get('nombre', '').strip()
    if not nombre_input and rol_deseado == 'Admin':
        nombre = f"Admin_{nuevo_device_id}" # Nombre temporal único para garantizar inserción
    elif not nombre_input and rol_deseado == 'Cliente':
        nombre = f"Cliente_{nuevo_device_id}" # Nombre temporal único para Clientes
    else:
        nombre = nombre_input # Usar el nombre provisto

    edad = data.get('edad')
    peso_aprox = data.get('peso_aprox')
    genero = data.get('genero')
    
    conn = get_db()
    try:
        cursor = conn.execute("""
            INSERT INTO USUARIOS (dispositivo_id, nombre, rol, edad, peso_aprox, genero)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nuevo_device_id, nombre, rol_deseado, edad, peso_aprox, genero)) 
        
        conn.commit()
        
        print(f"DEBUG: Rol deseado para redirección: {rol_deseado}")
        
        # Redirección basada en el rol que acaba de ser registrado
        if rol_deseado == 'Admin':
            redir_url = url_for('admin_menu')
        else:
            redir_url = url_for('consulta') 
            
        response = jsonify({
            "status": "success", 
            "message": "Registro completado.",
            "redirect_url": redir_url 
        })
        
        # Establecemos la cookie en la respuesta JSON
        return establecer_dispositivo_cookie(response, nuevo_device_id)

    except sqlite3.Error as e:
        # Esto captura la excepción (por ejemplo, UNIQUE constraint fallido)
        print(f"❌ Error al registrar nuevo usuario ({rol_deseado}): {e}")
        conn.rollback()
        # Si la inserción falla, devolvemos un mensaje de error claro al frontend
        return jsonify({"status": "error", "message": f"Error al registrar: {e}"}), 500
    finally:
        conn.close()

# ###################################################################
# ### COMIENZA ZONA 10: EJECUCIÓN DEL SERVIDOR ###
# ###################################################################

def init_db(app):
    """Inicializa la base de datos (crea la estructura de tablas)."""
    # CRÍTICO: Usa la función importada de data_initializer.py
    with app.app_context():
        conn = get_db()
        try:
            # init_db_schema importada de ZONA 0
            init_db_schema(conn)
            check_and_create_dispositivos_table(conn) # <<< AGREGUE ESTA LÍNEA
            print("✅ Estructura de la Base de Datos inicializada (incluida 'dispositivos').")
        finally:
            conn.close()

# ===================================================================
# FUNCIÓN DE INICIALIZACIÓN DE LA BASE DE DATOS (ZONA 10)
# ===================================================================

def check_and_create_dispositivos_table(conn):
    """Asegura que la tabla 'dispositivos' exista para la gestión de roles."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dispositivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL UNIQUE,
            rol TEXT NOT NULL,
            nombre_usuario TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()



            
# Asegúrate de que tu bloque final de ejecución (__name__ == "__main__") llame a init_db(app)



@app.teardown_appcontext
def close_connection(exception):
    """Cierra la conexión a la DB al finalizar la solicitud (Placeholder para el patrón de Flask)."""
    pass

if __name__ == "__main__":
    # 🚨 PASO DE INICIALIZACIÓN CRÍTICO 🚨
    # 1. Aseguramos que todas las tablas existan
    init_db(app) 
    
    # 2. Luego, insertamos los datos Mock (si no se ha hecho antes)
    conn = get_db() 

    try:
        # poblar_base_de_datos_mock importada de ZONA 0
        poblar_base_de_datos_mock(conn)
        print("✅ Comprobación de datos mock ejecutada (Admin Master / Cliente de Prueba).")
    except Exception as e:
        print(f"❌ Error al ejecutar poblar_base_de_datos_mock: {e}")
    finally:
        # Esto asegura que conn.close() se llame incluso si hay una interrupción (Ctrl+C)
        conn.close()

app.run(debug=True, host='0.0.0.0', port=5000)
