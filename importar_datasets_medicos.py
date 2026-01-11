#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para importar datasets médicos a PostgreSQL

Importa:
1. CIE-10 en español (enfermedades)
2. Disease-Symptom dataset (síntomas y relaciones)

Autor: Claude Code
Fecha: 2026-01-03
"""

import csv
import os
import psycopg2
from psycopg2 import sql
from urllib.request import urlretrieve
import json

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Obtener DATABASE_URL de variable de entorno (usar la de Render)
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ ERROR: Variable DATABASE_URL no encontrada")
    print("💡 Ejecuta: export DATABASE_URL='tu_url_de_render'")
    exit(1)

# URLs de los datasets
URL_CIE10 = "https://raw.githubusercontent.com/verasativa/CIE-10/master/cie-10.csv"
URL_DISEASE_SYMPTOM = "https://raw.githubusercontent.com/anujdutt9/Disease-Prediction-from-Symptoms/master/dataset/training_data.csv"

# Archivos locales
ARCHIVO_CIE10 = "cie10_dataset.csv"
ARCHIVO_DISEASE_SYMPTOM = "disease_symptom_dataset.csv"

# Diccionario de traducción manual (síntomas más comunes)
# TODO: Expandir o usar Google Translate API para traducciones automáticas
TRADUCCIONES_SINTOMAS = {
    'itching': 'picazón',
    'skin_rash': 'erupción cutánea',
    'nodal_skin_eruptions': 'erupciones nodulares',
    'continuous_sneezing': 'estornudos continuos',
    'shivering': 'escalofríos',
    'chills': 'escalofríos',
    'joint_pain': 'dolor articular',
    'stomach_pain': 'dolor de estómago',
    'acidity': 'acidez',
    'ulcers_on_tongue': 'úlceras en la lengua',
    'muscle_wasting': 'desgaste muscular',
    'vomiting': 'vómito',
    'burning_micturition': 'micción ardiente',
    'spotting_urination': 'manchado al orinar',
    'fatigue': 'fatiga',
    'weight_gain': 'aumento de peso',
    'anxiety': 'ansiedad',
    'cold_hands_and_feets': 'manos y pies fríos',
    'mood_swings': 'cambios de humor',
    'weight_loss': 'pérdida de peso',
    'restlessness': 'inquietud',
    'lethargy': 'letargo',
    'patches_in_throat': 'manchas en la garganta',
    'irregular_sugar_level': 'nivel irregular de azúcar',
    'cough': 'tos',
    'high_fever': 'fiebre alta',
    'sunken_eyes': 'ojos hundidos',
    'breathlessness': 'falta de aire',
    'sweating': 'sudoración',
    'dehydration': 'deshidratación',
    'indigestion': 'indigestión',
    'headache': 'dolor de cabeza',
    'yellowish_skin': 'piel amarillenta',
    'dark_urine': 'orina oscura',
    'nausea': 'náuseas',
    'loss_of_appetite': 'pérdida de apetito',
    'pain_behind_the_eyes': 'dolor detrás de los ojos',
    'back_pain': 'dolor de espalda',
    'constipation': 'estreñimiento',
    'abdominal_pain': 'dolor abdominal',
    'diarrhoea': 'diarrea',
    'mild_fever': 'fiebre leve',
    'yellow_urine': 'orina amarilla',
    'yellowing_of_eyes': 'amarillez de ojos',
    'acute_liver_failure': 'insuficiencia hepática aguda',
    'fluid_overload': 'sobrecarga de líquidos',
    'swelling_of_stomach': 'hinchazón del estómago',
    'swelled_lymph_nodes': 'ganglios linfáticos inflamados',
    'malaise': 'malestar general',
    'blurred_and_distorted_vision': 'visión borrosa y distorsionada',
    'phlegm': 'flema',
    'throat_irritation': 'irritación de garganta',
    'redness_of_eyes': 'enrojecimiento de ojos',
    'sinus_pressure': 'presión sinusal',
    'runny_nose': 'secreción nasal',
    'congestion': 'congestión',
    'chest_pain': 'dolor de pecho',
    'weakness_in_limbs': 'debilidad en extremidades',
    'fast_heart_rate': 'frecuencia cardíaca rápida',
    'pain_during_bowel_movements': 'dolor al defecar',
    'pain_in_anal_region': 'dolor anal',
    'bloody_stool': 'heces con sangre',
    'irritation_in_anus': 'irritación anal',
    'neck_pain': 'dolor de cuello',
    'dizziness': 'mareo',
    'cramps': 'calambres',
    'bruising': 'moretones',
    'obesity': 'obesidad',
    'swollen_legs': 'piernas hinchadas',
    'swollen_blood_vessels': 'vasos sanguíneos hinchados',
    'puffy_face_and_eyes': 'cara y ojos hinchados',
    'enlarged_thyroid': 'tiroides agrandada',
    'brittle_nails': 'uñas quebradizas',
    'swollen_extremeties': 'extremidades hinchadas',
    'excessive_hunger': 'hambre excesiva',
    'drying_and_tingling_lips': 'labios secos y hormigueantes',
    'slurred_speech': 'habla arrastrada',
    'knee_pain': 'dolor de rodilla',
    'hip_joint_pain': 'dolor de cadera',
    'muscle_weakness': 'debilidad muscular',
    'stiff_neck': 'rigidez de cuello',
    'swelling_joints': 'articulaciones hinchadas',
    'movement_stiffness': 'rigidez de movimiento',
    'spinning_movements': 'movimientos giratorios',
    'loss_of_balance': 'pérdida de equilibrio',
    'unsteadiness': 'inestabilidad',
    'weakness_of_one_body_side': 'debilidad de un lado del cuerpo',
    'loss_of_smell': 'pérdida de olfato',
    'bladder_discomfort': 'molestia en la vejiga',
    'foul_smell_of_urine': 'mal olor de orina',
    'continuous_feel_of_urine': 'sensación continua de orinar',
    'passage_of_gases': 'gases',
    'internal_itching': 'picazón interna',
    'depression': 'depresión',
    'irritability': 'irritabilidad',
    'muscle_pain': 'dolor muscular',
    'altered_sensorium': 'alteración del sensorio',
    'red_spots_over_body': 'manchas rojas en el cuerpo',
    'belly_pain': 'dolor de vientre',
    'abnormal_menstruation': 'menstruación anormal',
    'dischromic_patches': 'manchas discrómicas',
    'watering_from_eyes': 'lagrimeo',
    'increased_appetite': 'aumento de apetito',
    'polyuria': 'poliuria',
    'family_history': 'historial familiar',
    'mucoid_sputum': 'esputo mucoide',
    'rusty_sputum': 'esputo oxidado',
    'lack_of_concentration': 'falta de concentración',
    'visual_disturbances': 'alteraciones visuales',
    'receiving_blood_transfusion': 'recibir transfusión de sangre',
    'receiving_unsterile_injections': 'recibir inyecciones no estériles',
    'coma': 'coma',
    'stomach_bleeding': 'sangrado estomacal',
    'distention_of_abdomen': 'distensión abdominal',
    'history_of_alcohol_consumption': 'historial de consumo de alcohol',
    'blood_in_sputum': 'sangre en esputo',
    'prominent_veins_on_calf': 'venas prominentes en pantorrilla',
    'palpitations': 'palpitaciones',
    'painful_walking': 'caminar doloroso',
    'pus_filled_pimples': 'granos con pus',
    'blackheads': 'puntos negros',
    'scurring': 'cicatrización',
    'skin_peeling': 'descamación de piel',
    'silver_like_dusting': 'polvo plateado',
    'small_dents_in_nails': 'pequeñas abolladuras en uñas',
    'inflammatory_nails': 'uñas inflamadas',
    'blister': 'ampolla',
    'red_sore_around_nose': 'llaga roja alrededor de nariz',
    'yellow_crust_ooze': 'supuración de costra amarilla'
}

TRADUCCIONES_ENFERMEDADES = {
    'Fungal infection': 'Infección fúngica',
    'Allergy': 'Alergia',
    'GERD': 'Enfermedad por reflujo gastroesofágico',
    'Chronic cholestasis': 'Colestasis crónica',
    'Drug Reaction': 'Reacción a medicamentos',
    'Peptic ulcer diseae': 'Úlcera péptica',
    'AIDS': 'SIDA',
    'Diabetes': 'Diabetes',
    'Gastroenteritis': 'Gastroenteritis',
    'Bronchial Asthma': 'Asma bronquial',
    'Hypertension': 'Hipertensión',
    'Migraine': 'Migraña',
    'Cervical spondylosis': 'Espondilosis cervical',
    'Paralysis (brain hemorrhage)': 'Parálisis (hemorragia cerebral)',
    'Jaundice': 'Ictericia',
    'Malaria': 'Malaria',
    'Chicken pox': 'Varicela',
    'Dengue': 'Dengue',
    'Typhoid': 'Tifoidea',
    'hepatitis A': 'Hepatitis A',
    'Hepatitis B': 'Hepatitis B',
    'Hepatitis C': 'Hepatitis C',
    'Hepatitis D': 'Hepatitis D',
    'Hepatitis E': 'Hepatitis E',
    'Alcoholic hepatitis': 'Hepatitis alcohólica',
    'Tuberculosis': 'Tuberculosis',
    'Common Cold': 'Resfriado común',
    'Pneumonia': 'Neumonía',
    'Dimorphic hemmorhoids(piles)': 'Hemorroides',
    'Heart attack': 'Infarto',
    'Varicose veins': 'Várices',
    'Hypothyroidism': 'Hipotiroidismo',
    'Hyperthyroidism': 'Hipertiroidismo',
    'Hypoglycemia': 'Hipoglucemia',
    'Osteoarthristis': 'Osteoartritis',
    'Arthritis': 'Artritis',
    '(vertigo) Paroymsal  Positional Vertigo': 'Vértigo posicional paroxístico',
    'Acne': 'Acné',
    'Urinary tract infection': 'Infección urinaria',
    'Psoriasis': 'Psoriasis',
    'Impetigo': 'Impétigo'
}

# =============================================================================
# FUNCIONES DE DESCARGA
# =============================================================================

def descargar_datasets():
    """Descarga los datasets si no existen localmente"""
    print("📥 Descargando datasets...")

    if not os.path.exists(ARCHIVO_CIE10):
        print(f"  → Descargando CIE-10: {URL_CIE10}")
        urlretrieve(URL_CIE10, ARCHIVO_CIE10)
        print("  ✅ CIE-10 descargado")
    else:
        print(f"  ℹ️  {ARCHIVO_CIE10} ya existe")

    if not os.path.exists(ARCHIVO_DISEASE_SYMPTOM):
        print(f"  → Descargando Disease-Symptom: {URL_DISEASE_SYMPTOM}")
        urlretrieve(URL_DISEASE_SYMPTOM, ARCHIVO_DISEASE_SYMPTOM)
        print("  ✅ Disease-Symptom descargado")
    else:
        print(f"  ℹ️  {ARCHIVO_DISEASE_SYMPTOM} ya existe")

# =============================================================================
# FUNCIONES DE CREACIÓN DE TABLAS
# =============================================================================

def crear_tablas(conn):
    """Crea las tablas necesarias en PostgreSQL"""
    print("\n🔨 Creando tablas en PostgreSQL...")

    cursor = conn.cursor()

    # Tabla: enfermedades_catalogo (CIE-10)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enfermedades_catalogo (
            id SERIAL PRIMARY KEY,
            codigo VARCHAR(20) UNIQUE NOT NULL,
            codigo_padre_0 VARCHAR(20),
            codigo_padre_1 VARCHAR(20),
            codigo_padre_2 VARCHAR(20),
            codigo_padre_3 VARCHAR(20),
            codigo_padre_4 VARCHAR(20),
            descripcion TEXT NOT NULL,
            descripcion_lower TEXT,
            nivel INTEGER,
            fuente VARCHAR(100),
            fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_enfermedades_descripcion_lower
        ON enfermedades_catalogo(descripcion_lower)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_enfermedades_codigo
        ON enfermedades_catalogo(codigo)
    """)

    # Tabla: sintomas_catalogo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sintomas_catalogo (
            id SERIAL PRIMARY KEY,
            nombre_original VARCHAR(100) UNIQUE NOT NULL,
            nombre_espanol VARCHAR(100),
            nombre_lower TEXT,
            categoria VARCHAR(50),
            fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sintomas_nombre_lower
        ON sintomas_catalogo(nombre_lower)
    """)

    # Tabla: enfermedades_dataset
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enfermedades_dataset (
            id SERIAL PRIMARY KEY,
            nombre_original VARCHAR(100) UNIQUE NOT NULL,
            nombre_espanol VARCHAR(100),
            nombre_lower TEXT,
            fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla: enfermedad_sintoma_dataset
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enfermedad_sintoma_dataset (
            id SERIAL PRIMARY KEY,
            enfermedad_id INTEGER NOT NULL REFERENCES enfermedades_dataset(id),
            sintoma_id INTEGER NOT NULL REFERENCES sintomas_catalogo(id),
            frecuencia VARCHAR(20) DEFAULT 'comun',
            fuente VARCHAR(100) DEFAULT 'kaggle-disease-symptom-dataset',
            fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(enfermedad_id, sintoma_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_enfermedad_sintoma_enfermedad
        ON enfermedad_sintoma_dataset(enfermedad_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_enfermedad_sintoma_sintoma
        ON enfermedad_sintoma_dataset(sintoma_id)
    """)

    # Tabla: sinonimos_medicos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sinonimos_medicos (
            id SERIAL PRIMARY KEY,
            termino_original VARCHAR(200) NOT NULL,
            termino_normalizado VARCHAR(200) NOT NULL,
            tipo VARCHAR(20),
            idioma VARCHAR(10) DEFAULT 'es',
            fuente VARCHAR(100),
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sinonimos_original
        ON sinonimos_medicos(termino_original)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sinonimos_normalizado
        ON sinonimos_medicos(termino_normalizado)
    """)

    conn.commit()
    print("  ✅ Tablas creadas exitosamente")

# =============================================================================
# FUNCIONES DE IMPORTACIÓN
# =============================================================================

def importar_cie10(conn):
    """Importa el dataset CIE-10 a la tabla enfermedades_catalogo"""
    print("\n📊 Importando CIE-10...")

    cursor = conn.cursor()
    registros_importados = 0

    with open(ARCHIVO_CIE10, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                cursor.execute("""
                    INSERT INTO enfermedades_catalogo
                    (codigo, codigo_padre_0, codigo_padre_1, codigo_padre_2,
                     codigo_padre_3, codigo_padre_4, descripcion, descripcion_lower,
                     nivel, fuente)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (codigo) DO NOTHING
                """, (
                    row['code'],
                    row['code_0'] if row['code_0'] else None,
                    row['code_1'] if row['code_1'] else None,
                    row['code_2'] if row['code_2'] else None,
                    row['code_3'] if row['code_3'] else None,
                    row['code_4'] if row['code_4'] else None,
                    row['description'],
                    row['description'].lower(),
                    int(row['level']) if row['level'] else 0,
                    row['source']
                ))
                registros_importados += 1

                if registros_importados % 100 == 0:
                    print(f"  → {registros_importados} registros importados...")

            except Exception as e:
                print(f"  ⚠️  Error importando {row.get('code')}: {e}")

    conn.commit()
    print(f"  ✅ {registros_importados} enfermedades CIE-10 importadas")

def importar_disease_symptom(conn):
    """Importa el dataset Disease-Symptom"""
    print("\n📊 Importando Disease-Symptom dataset...")

    cursor = conn.cursor()

    # Paso 1: Leer CSV y extraer síntomas únicos
    print("  → Paso 1: Importando síntomas...")
    sintomas_unicos = set()

    with open(ARCHIVO_DISEASE_SYMPTOM, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        columnas = reader.fieldnames
        sintomas_unicos = set([col for col in columnas if col != 'prognosis'])

    # Insertar síntomas
    sintomas_importados = 0
    for sintoma_orig in sintomas_unicos:
        sintoma_esp = TRADUCCIONES_SINTOMAS.get(sintoma_orig, sintoma_orig)

        try:
            cursor.execute("""
                INSERT INTO sintomas_catalogo
                (nombre_original, nombre_espanol, nombre_lower)
                VALUES (%s, %s, %s)
                ON CONFLICT (nombre_original) DO NOTHING
            """, (sintoma_orig, sintoma_esp, sintoma_esp.lower()))
            sintomas_importados += 1
        except Exception as e:
            print(f"  ⚠️  Error importando síntoma {sintoma_orig}: {e}")

    conn.commit()
    print(f"  ✅ {sintomas_importados} síntomas importados")

    # Paso 2: Extraer enfermedades únicas
    print("  → Paso 2: Importando enfermedades...")
    enfermedades_unicas = set()

    with open(ARCHIVO_DISEASE_SYMPTOM, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            enfermedades_unicas.add(row['prognosis'])

    # Insertar enfermedades
    enfermedades_importadas = 0
    for enfermedad_orig in enfermedades_unicas:
        enfermedad_esp = TRADUCCIONES_ENFERMEDADES.get(enfermedad_orig, enfermedad_orig)

        try:
            cursor.execute("""
                INSERT INTO enfermedades_dataset
                (nombre_original, nombre_espanol, nombre_lower)
                VALUES (%s, %s, %s)
                ON CONFLICT (nombre_original) DO NOTHING
            """, (enfermedad_orig, enfermedad_esp, enfermedad_esp.lower()))
            enfermedades_importadas += 1
        except Exception as e:
            print(f"  ⚠️  Error importando enfermedad {enfermedad_orig}: {e}")

    conn.commit()
    print(f"  ✅ {enfermedades_importadas} enfermedades importadas")

    # Paso 3: Crear relaciones enfermedad-síntoma
    print("  → Paso 3: Creando relaciones enfermedad-síntoma...")
    relaciones_creadas = 0

    with open(ARCHIVO_DISEASE_SYMPTOM, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            enfermedad_nombre = row['prognosis']

            # Obtener ID de enfermedad
            cursor.execute("""
                SELECT id FROM enfermedades_dataset
                WHERE nombre_original = %s
            """, (enfermedad_nombre,))
            enfermedad_result = cursor.fetchone()

            if not enfermedad_result:
                continue

            enfermedad_id = enfermedad_result[0]

            # Para cada síntoma con valor 1
            for sintoma_nombre, valor in row.items():
                if sintoma_nombre == 'prognosis':
                    continue

                if valor == '1':
                    # Obtener ID de síntoma
                    cursor.execute("""
                        SELECT id FROM sintomas_catalogo
                        WHERE nombre_original = %s
                    """, (sintoma_nombre,))
                    sintoma_result = cursor.fetchone()

                    if not sintoma_result:
                        continue

                    sintoma_id = sintoma_result[0]

                    # Crear relación
                    try:
                        cursor.execute("""
                            INSERT INTO enfermedad_sintoma_dataset
                            (enfermedad_id, sintoma_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                        """, (enfermedad_id, sintoma_id))
                        relaciones_creadas += 1
                    except Exception as e:
                        print(f"  ⚠️  Error creando relación: {e}")

            if relaciones_creadas % 100 == 0:
                print(f"    → {relaciones_creadas} relaciones creadas...")
                conn.commit()

    conn.commit()
    print(f"  ✅ {relaciones_creadas} relaciones enfermedad-síntoma creadas")

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal del script"""
    print("=" * 70)
    print("🏥 IMPORTACIÓN DE DATASETS MÉDICOS A POSTGRESQL")
    print("=" * 70)

    try:
        # 1. Descargar datasets
        descargar_datasets()

        # 2. Conectar a PostgreSQL
        print("\n🔌 Conectando a PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        print("  ✅ Conexión exitosa")

        # 3. Crear tablas
        crear_tablas(conn)

        # 4. Importar CIE-10
        importar_cie10(conn)

        # 5. Importar Disease-Symptom
        importar_disease_symptom(conn)

        # 6. Cerrar conexión
        conn.close()

        print("\n" + "=" * 70)
        print("✅ IMPORTACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 70)
        print("\n📊 Resumen:")
        print("  - Enfermedades CIE-10: importadas")
        print("  - Síntomas: 132 importados")
        print("  - Enfermedades dataset: ~41 importadas")
        print("  - Relaciones: miles creadas")
        print("\n💡 Próximo paso:")
        print("  Modificar algoritmo de sugerencia de síntomas para usar BD")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
