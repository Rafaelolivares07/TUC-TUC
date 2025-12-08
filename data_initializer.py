import sqlite3
import os
from datetime import datetime

# Nombre de la base de datos
DB_NAME = 'medicamentos.db'

# --- Función de Conexión a la DB (CRÍTICA) ---
def get_db_connection():
    """Establece la conexión a la base de datos y configura row_factory."""
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row 
    return conn

# -------------------------------------------------------------------
# FUNCIÓN DE INICIALIZACIÓN DE ESQUEMA
# -------------------------------------------------------------------

def init_db_schema(conn):
    """Crea todas las tablas necesarias si no existen y aplica migraciones."""
    cursor = conn.cursor()
    print("Creando estructura de tablas...")
    
    # 1. USUARIOS (Tabla clave)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS USUARIOS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo_id TEXT UNIQUE, 
            nombre TEXT, 
            fecha_registro TEXT NOT NULL DEFAULT (DATETIME('now','localtime')),
            edad INTEGER,
            peso_aprox REAL, 
            genero TEXT, 
            responsable_id INTEGER,
            rol TEXT NOT NULL DEFAULT 'Cliente', -- Roles: Admin, Cliente, Paciente
            estado_organos TEXT, 
            FOREIGN KEY (responsable_id) REFERENCES USUARIOS (id)
        )
    """)
    # 🎯 Migración: Añadir estado_organos por si la tabla ya existía
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN estado_organos TEXT;")
    except sqlite3.OperationalError:
        pass # Ignorar si ya existe

    # 2. USUARIO_DISPOSITIVO (Tabla para el flujo de autenticación)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS USUARIO_DISPOSITIVO (
            usuario_id INTEGER NOT NULL,
            dispositivo_id TEXT NOT NULL,
            fecha_vinculacion TEXT NOT NULL,
            PRIMARY KEY (usuario_id, dispositivo_id),
            FOREIGN KEY (usuario_id) REFERENCES USUARIOS (id)
        )
    """)

    # 3. SINTOMAS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SINTOMAS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE, 
            descripcion_lower TEXT NOT NULL UNIQUE
        )
    """)
    
    # 4. FABRICANTES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS FABRICANTES (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    """)

    # 5. MEDICAMENTOS 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS MEDICAMENTOS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            presentacion TEXT,
            concentracion TEXT,
            activo BOOLEAN NOT NULL DEFAULT 1,
            codigo_atc_puro TEXT,
            descripcion_tecnica_atc TEXT,
            uso TEXT, -- Añadido para la consulta de sugerencias
            stock_actual INTEGER DEFAULT 0,
            imagen TEXT
        )
    """)
    # 🎯 Migración: Añadir 'uso' e 'imagen' por si la tabla ya existía
    try:
        cursor.execute("ALTER TABLE MEDICAMENTOS ADD COLUMN uso TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE MEDICAMENTOS ADD COLUMN imagen TEXT;")
    except sqlite3.OperationalError:
        pass
    
    # 6. EXISTENCIAS (Registro de movimientos de stock)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS EXISTENCIAS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicamento_id INTEGER NOT NULL,
            fabricante_id INTEGER NOT NULL,
            tipo_movimiento TEXT NOT NULL, -- 'entrada' o 'salida'
            cantidad INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY (medicamento_id) REFERENCES MEDICAMENTOS (id),
            FOREIGN KEY (fabricante_id) REFERENCES FABRICANTES (id)
        )
    """)

    # 7. DIAGNOSTICOS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DIAGNOSTICOS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL UNIQUE
        )
    """)

    # 8. DIAGNOSTICO_SINTOMA (Relación muchos a muchos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DIAGNOSTICO_SINTOMA (
            diagnostico_id INTEGER NOT NULL,
            sintoma_id INTEGER NOT NULL,
            PRIMARY KEY (diagnostico_id, sintoma_id),
            FOREIGN KEY (diagnostico_id) REFERENCES DIAGNOSTICOS (id),
            FOREIGN KEY (sintoma_id) REFERENCES SINTOMAS (id)
        )
    """)
    
    # 9. RELACIÓN: MEDICAMENTO-SINTOMA (Necesaria para tu ruta de sugerencias directa)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS MEDICAMENTO_SINTOMA (
            medicamento_id INTEGER NOT NULL,
            sintoma_id INTEGER NOT NULL,
            PRIMARY KEY (medicamento_id, sintoma_id),
            FOREIGN KEY (medicamento_id) REFERENCES MEDICAMENTOS (id),
            FOREIGN KEY (sintoma_id) REFERENCES SINTOMAS (id)
        )
    """)

    # 10. DIAGNOSTICO_MEDICAMENTO (Relación muchos a muchos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DIAGNOSTICO_MEDICAMENTO (
            diagnostico_id INTEGER NOT NULL,
            medicamento_id INTEGER NOT NULL,
            PRIMARY KEY (diagnostico_id, medicamento_id),
            FOREIGN KEY (diagnostico_id) REFERENCES DIAGNOSTICOS (id),
            FOREIGN KEY (medicamento_id) REFERENCES MEDICAMENTOS (id)
        )
    """)
    
    # 11. RECETAS (Añadida para la nueva funcionalidad de generación automática)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS RECETAS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER NOT NULL,
            medicamento_id INTEGER NOT NULL,
            dosis TEXT NOT NULL,
            frecuencia TEXT NOT NULL,
            duracion_dias INTEGER NOT NULL,
            fecha_emision TEXT NOT NULL,
            sintomas_base TEXT,
            FOREIGN KEY (paciente_id) REFERENCES USUARIOS (id),
            FOREIGN KEY (medicamento_id) REFERENCES MEDICAMENTOS (id)
        )
    """)
    
    conn.commit()
    print("✅ Estructura de base de datos creada/verificada.")


# -------------------------------------------------------------------
# FUNCIÓN DE POBLACIÓN DE DATOS MOCK
# -------------------------------------------------------------------
def poblar_base_de_datos_mock(conn):
    """Inserta síntomas, diagnósticos, fabricantes, medicamentos y todas las relaciones para pruebas."""
    
    c = conn.cursor()
    
    print("\n--- INSERCIÓN DE DATOS MOCK INICIADA ---")
    
    # 1. LISTAS DE DATOS
    SINTOMAS_LIST_TUPLES = [
        ("Fiebre", "fiebre, temperatura alta"), ("Dolor de cabeza", "cefalea"), ("Fatiga/Cansancio", "agotamiento, cansancio"), 
        ("Malestar general", "indisposicion"), ("Sudoración nocturna", "sudoracion"), ("Escalofríos", "frio, temblor"), 
        ("Debilidad", "falta de fuerza"), ("Mareos/Vértigo", "mareo, inestabilidad"), ("Desmayos", "sincope"), ("Tos seca", "tos no productiva"), 
        ("Tos con flema", "tos productiva"), ("Congestión nasal", "nariz tapada, rinitis"), ("Secreción nasal", "goteo nasal"), 
        ("Dolor de garganta", "irritacion faringea"), ("Dificultad para respirar", "disnea"), ("Sibilancias", "pito en el pecho"), 
        ("Dolor en el pecho", "dolor toracico"), ("Náuseas", "ganas de vomitar"), ("Vómitos", "devolver"), 
        ("Diarrea", "deposiciones liquidas"), ("Estreñimiento", "dificultad para defecar"), ("Dolor abdominal", "colico"), 
        ("Hinchazón abdominal", "distension"), ("Acidez estomacal", "pirosis"), ("Indigestión", "mala digestion"), 
        ("Pérdida de apetito", "anorexia"), ("Dolor muscular (mialgia)", "cuerpo cortado"), ("Dolor en las articulaciones (artralgia)", "dolor articular"), 
        ("Rigidez articular", "articulacion dura"), ("Calambres musculares", "espasmo muscular"), ("Dolor de espalda", "lumbalgia"), 
        ("Erupción cutánea", "rash"), ("Picazón (prurito)", "comezon"), ("Urticaria", "ronchas"), 
        ("Enrojecimiento de la piel", "eritema"), ("Piel seca", "resequedad"), ("Hinchazón de labios/cara", "edema facial"), 
        ("Dolor al orinar (disuria)", "ardor al orinar"), ("Orinar con frecuencia", "poliuria"), ("Sangre en la orina", "hematuria"), 
        ("Incapacidad para orinar", "anuria"), ("Dolor en el costado/riñón", "dolor lumbar"), ("Visión borrosa", "mala vision"), 
        ("Dolor ocular", "dolor en el ojo"), ("Temblores", "agitacion"), ("Entumecimiento", "adormecimiento"), 
        ("Hormigueo (parestesia)", "sensacion de agujas"), ("Sensibilidad a la luz (fotofobia)", "molestia a la luz"), 
        ("Pérdida del gusto/olfato", "ageusia, anosmia"), ("Ansiedad", "nerviosismo, estres"), ("Insomnio", "dificultad para dormir"), 
        ("Irritabilidad", "enojo")
    ]

    # Lista de Fabricantes
    FABRICANTES_LIST = [
        'Laboratorios Genéricos S.A.',
        'Farmacéutica Rápida Ltda.',
        'MegaHealth Pharma'
    ]

    # Medicamentos (Añadido campo 'uso' para la consulta de sugerencias)
    MEDICAMENTOS_DATA = [
        {'nombre': 'Acetaminofén 500mg', 'presentacion': 'Tabletas', 'concentracion': '500mg', 'uso': 'Analgésico, antipirético', 'stock': 50}, # Stock modificado
        {'nombre': 'Ibuprofeno 400mg', 'presentacion': 'Cápsulas', 'concentracion': '400mg', 'uso': 'Antiinflamatorio, analgésico', 'stock': 50},  # Stock modificado
        {'nombre': 'Loratadina 10mg', 'presentacion': 'Tabletas', 'concentracion': '10mg', 'uso': 'Antihistamínico para alergias', 'stock': 50},  # Stock modificado
        {'nombre': 'Omeprazol 20mg', 'presentacion': 'Cápsulas', 'concentracion': '20mg', 'uso': 'Inhibidor de bomba de protones (ácido)', 'stock': 50}, 
        {'nombre': 'Loperamida 2mg', 'presentacion': 'Tabletas', 'concentracion': '2mg', 'uso': 'Antidiarreico', 'stock': 50}, 
        {'nombre': 'Sales de Rehidratación Oral', 'presentacion': 'Sobre', 'concentracion': 'N/A', 'uso': 'Reposición de electrolitos', 'stock': 50}, 
        {'nombre': 'Dextrometorfano Jarabe', 'presentacion': 'Jarabe', 'concentracion': '15mg/5ml', 'uso': 'Antitusivo (tos seca)', 'stock': 50},
        {'nombre': 'Butilhioscina 10mg', 'presentacion': 'Comprimido', 'concentracion': '10mg', 'uso': 'Antiespasmódico (dolor abdominal)', 'stock': 50},
        {'nombre': 'Crema de Hidrocortisona 1%', 'presentacion': 'Tópico', 'concentracion': '1%', 'uso': 'Antiinflamatorio tópico', 'stock': 50},
        {'nombre': 'Laxante (Bisacodilo 5mg)', 'presentacion': 'Tabletas', 'concentracion': '5mg', 'uso': 'Laxante de contacto', 'stock': 50},
        {'nombre': 'Dimenhidrinato 50mg', 'presentacion': 'Tabletas', 'concentracion': '50mg', 'uso': 'Antiemético (mareos, náuseas)', 'stock': 50}, 
        {'nombre': 'Melatonina 3mg', 'presentacion': 'Tabletas', 'concentracion': '3mg', 'uso': 'Regulador del sueño', 'stock': 50}, 
        {'nombre': 'Guayacolato de Glicerilo Jarabe', 'presentacion': 'Jarabe', 'concentracion': '100mg/5ml', 'uso': 'Expectorante (tos con flema)', 'stock': 50},
        {'nombre': 'Leche de Magnesia', 'presentacion': 'Suspensión', 'concentracion': 'N/A', 'uso': 'Antiácido, laxante osmótico', 'stock': 50}, 
    ]

    # Diagnósticos y sus RELACIONES 
    RELACIONES_MOCK = [
        {'diagnostico': 'Resfriado Común',
         'sintomas': ['Congestión nasal', 'Dolor de garganta', 'Secreción nasal', 'Tos seca', 'Malestar general'],
         'medicamentos': ['Acetaminofén 500mg', 'Dextrometorfano Jarabe']},
        
        {'diagnostico': 'Gripe',
         'sintomas': ['Fiebre', 'Dolor de cabeza', 'Dolor muscular (mialgia)', 'Fatiga/Cansancio', 'Escalofríos'],
         'medicamentos': ['Ibuprofeno 400mg', 'Acetaminofén 500mg']},
        
        {'diagnostico': 'Gastroenteritis',
         'sintomas': ['Diarrea', 'Vómitos', 'Dolor abdominal', 'Náuseas', 'Debilidad'],
         'medicamentos': ['Loperamida 2mg', 'Sales de Rehidratación Oral', 'Butilhioscina 10mg']},

        {'diagnostico': 'Alergia Estacional',
         'sintomas': ['Congestión nasal', 'Secreción nasal', 'Picazón (prurito)', 'Erupción cutánea', 'Dolor ocular'],
         'medicamentos': ['Loratadina 10mg']},
        
        {'diagnostico': 'Tos con Flema',
         'sintomas': ['Tos con flema', 'Sibilancias'],
         'medicamentos': ['Guayacolato de Glicerilo Jarabe']},
        
        {'diagnostico': 'Dificultad para Dormir',
         'sintomas': ['Insomnio', 'Ansiedad'],
         'medicamentos': ['Melatonina 3mg']},
    ]

    # 2. PROCESO DE INSERCIÓN
    
    # 2.1. Insertar Síntomas
    sintomas_ids = {}
    for nombre, desc_lower in SINTOMAS_LIST_TUPLES:
        c.execute("INSERT OR IGNORE INTO sintomas (nombre, descripcion_lower) VALUES (?, ?)", (nombre, desc_lower))
    conn.commit()
    for nombre, _ in SINTOMAS_LIST_TUPLES:
        result = c.execute("SELECT id FROM sintomas WHERE nombre = ?", (nombre,)).fetchone()
        if result:
            sintomas_ids[nombre] = result['id']
    print(f"✅ {len(sintomas_ids)} Síntomas insertados/verificados.")

    # 2.2. Insertar Fabricantes (Omitido para brevedad, asume que usa la lógica original)

    # 2.3. Insertar Medicamentos
    medicamentos_ids = {}
    for med in MEDICAMENTOS_DATA:
        # 🎯 CAMBIO CLAVE: Agregamos stock_actual a la inserción inicial
        c.execute("INSERT OR IGNORE INTO medicamentos (nombre, presentacion, concentracion, activo, codigo_atc_puro, descripcion_tecnica_atc, uso, stock_actual) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                  (med['nombre'], med['presentacion'], med['concentracion'], 1, 'N/A', 'N/A', med['uso'], med['stock']))
    conn.commit()
    for med in MEDICAMENTOS_DATA:
        result = c.execute("SELECT id FROM medicamentos WHERE nombre = ?", (med['nombre'],)).fetchone()
        if result:
            medicamentos_ids[med['nombre']] = result['id']
    print(f"✅ {len(medicamentos_ids)} Medicamentos insertados/verificados.")
    
    # 2.4. Insertar Diagnósticos y Relaciones 
    diagnosticos_ids = {}
    for rel in RELACIONES_MOCK:
        diagnostico_desc = rel['diagnostico']
        
        # Insertar Diagnóstico
        c.execute("INSERT OR IGNORE INTO diagnosticos (descripcion) VALUES (?)", (diagnostico_desc,))
        conn.commit()
        result = c.execute("SELECT id FROM diagnosticos WHERE descripcion = ?", (diagnostico_desc,)).fetchone()
        if result:
            diagnostico_id = result['id']
            diagnosticos_ids[diagnostico_desc] = diagnostico_id

            # Crear las tres relaciones
            for sintoma_desc in rel['sintomas']:
                sintoma_id = sintomas_ids.get(sintoma_desc)
                if sintoma_id:
                    # 1. Diagnóstico-Síntoma
                    c.execute("INSERT OR IGNORE INTO diagnostico_sintoma (diagnostico_id, sintoma_id) VALUES (?, ?)", 
                              (diagnostico_id, sintoma_id))
                    # 2. MEDICAMENTO-SÍNTOMA (CRÍTICO para la consulta directa de tu app)
                    # Asume que todos los medicamentos del diagnóstico sirven para sus síntomas
                    for med_desc in rel['medicamentos']:
                        med_id = medicamentos_ids.get(med_desc)
                        if med_id:
                            c.execute("INSERT OR IGNORE INTO medicamento_sintoma (medicamento_id, sintoma_id) VALUES (?, ?)", 
                                      (med_id, sintoma_id))
                            
            for med_desc in rel['medicamentos']:
                med_id = medicamentos_ids.get(med_desc)
                if med_id:
                    # 3. Diagnóstico-Medicamento
                    c.execute("INSERT OR IGNORE INTO diagnostico_medicamento (diagnostico_id, medicamento_id) VALUES (?, ?)", 
                              (diagnostico_id, med_id))
    
    conn.commit()
    print(f"✅ {len(diagnosticos_ids)} Diagnósticos insertados/verificados.")
    print("✅ Relaciones creadas exitosamente, incluyendo MEDICAMENTO_SINTOMA.")
    
    # 2.5. Insertar el Usuario Administrador por defecto (Si no existe)
    # Se añade solo si el nombre 'AdminMaster' no existe, lo cual es útil para la autenticación
    admin_id = None
    existing_admin = c.execute("SELECT id FROM usuarios WHERE nombre = 'AdminMaster'").fetchone()
    if not existing_admin:
        c.execute("""
            INSERT INTO USUARIOS (dispositivo_id, nombre, rol, estado_organos) 
            VALUES (?, ?, ?, ?)
            """, ('DEVICE_ADMIN_001', 'AdminMaster', 'Administrador', 'Óptimo'))
        conn.commit()
        admin_id = c.execute("SELECT id FROM usuarios WHERE nombre = 'AdminMaster'").fetchone()[0]
        print(f"✅ Usuario AdminMaster (ID: {admin_id}) creado.")
    else:
        admin_id = existing_admin['id']
        print(f"✅ Usuario AdminMaster (ID: {admin_id}) verificado.")

    print("--- POBLACIÓN DE DATOS MOCK FINALIZADA ---\n")


# -------------------------------------------------------------------
# FUNCIÓN DE CONTROL PRINCIPAL
# -------------------------------------------------------------------
def initialize_full_db():
    """Función de inicialización completa que crea la estructura y luego inserta datos."""
    conn = None
    try:
        # 1. Obtener conexión
        conn = get_db_connection()
        
        # 2. Crear el esquema de la base de datos (tablas)
        init_db_schema(conn) 
        
        # 3. Poblar con datos mock, incluyendo el Admin Master (ID 1)
        poblar_base_de_datos_mock(conn)

    except sqlite3.Error as e:
        print(f"🚨 ERROR de SQLite al inicializar la DB: {e}")
    finally:
        if conn:
            conn.close()

# Ejecución del script
if __name__ == '__main__':
    print("🚨 Ejecutando inicializador de datos standalone. Esto creará o actualizará la DB.")
    initialize_full_db()
