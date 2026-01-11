# 📊 Análisis de Datasets Médicos para Importar a PostgreSQL

## 🎯 Objetivo
Importar librerías médicas completas a nuestra BD para automatizar la sugerencia de síntomas basada en datos médicos reales.

---

## 📦 Dataset 1: CIE-10 en Español (Enfermedades)

**Fuente:** https://github.com/verasativa/CIE-10
**Archivo:** cie-10.csv

### Estructura del CSV:
```
code,code_0,code_1,code_2,code_3,code_4,description,level,source
A00-B99,,,,,,"Ciertas enfermedades infecciosas y parasitarias",0,icdcode.info
G130,G00-G99,G10-G13,G13,,,Neuromiopatía y neuropatía paraneoplásica,3,icdcode.info
```

### Columnas:
- **code**: Código ICD-10 (ej: "A00-B99", "G130")
- **code_0 a code_4**: Jerarquía de códigos padre (5 niveles)
- **description**: Descripción en español de la enfermedad
- **level**: Nivel jerárquico (0=capítulo, 1=bloque, 2=categoría, 3=subcategoría)
- **source**: Fuente del dato (icdcode.info)

### Datos:
- ✅ **Idioma:** Español
- ✅ **Encoding:** UTF-8
- ✅ **Separador:** Coma (,)
- ✅ **Cantidad estimada:** Miles de códigos jerárquicos
- ❌ **Limitación:** NO incluye síntomas, solo clasificación de enfermedades

### Tabla PostgreSQL Propuesta:
```sql
CREATE TABLE enfermedades_catalogo (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    codigo_padre_0 VARCHAR(20),
    codigo_padre_1 VARCHAR(20),
    codigo_padre_2 VARCHAR(20),
    codigo_padre_3 VARCHAR(20),
    codigo_padre_4 VARCHAR(20),
    descripcion TEXT NOT NULL,
    descripcion_lower TEXT, -- Para búsquedas case-insensitive
    nivel INTEGER,
    fuente VARCHAR(100),
    fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_enfermedades_descripcion_lower ON enfermedades_catalogo(descripcion_lower);
CREATE INDEX idx_enfermedades_codigo ON enfermedades_catalogo(codigo);
```

---

## 📦 Dataset 2: Disease-Symptom Dataset (Relaciones Enfermedad-Síntoma)

**Fuente:** https://github.com/anujdutt9/Disease-Prediction-from-Symptoms
**Archivo:** training_data.csv

### Estructura del CSV:
```
itching,skin_rash,nodal_skin_eruptions,...,yellow_crust_ooze,prognosis
1,1,1,0,0,...,0,Fungal infection
0,1,1,0,0,...,0,Fungal infection
```

### Datos:
- ✅ **132 síntomas** (columnas con valores binarios 0/1)
- ✅ **41-42 enfermedades únicas** en la columna "prognosis"
- ✅ **4,920 filas** de datos (combinaciones síntoma-enfermedad)
- ✅ **Formato:** Binario (0=sin síntoma, 1=con síntoma)
- ✅ **Separador:** Coma (,)
- ✅ **Encoding:** UTF-8
- ❌ **Idioma:** Inglés (requiere traducción)

### Lista de los 132 Síntomas:
1. itching
2. skin_rash
3. nodal_skin_eruptions
4. continuous_sneezing
5. shivering
6. chills
7. joint_pain
8. stomach_pain
9. acidity
10. ulcers_on_tongue
11. muscle_wasting
12. vomiting
13. burning_micturition
14. spotting_urination
15. fatigue
16. weight_gain
17. anxiety
18. cold_hands_and_feets
19. mood_swings
20. weight_loss
21. restlessness
22. lethargy
23. patches_in_throat
24. irregular_sugar_level
25. cough
26. high_fever
27. sunken_eyes
28. breathlessness
29. sweating
30. dehydration
31. indigestion
32. headache
33. yellowish_skin
34. dark_urine
35. nausea
36. loss_of_appetite
37. pain_behind_the_eyes
38. back_pain
39. constipation
40. abdominal_pain
41. diarrhoea
42. mild_fever
43. yellow_urine
44. yellowing_of_eyes
45. acute_liver_failure
46. fluid_overload
47. swelling_of_stomach
48. swelled_lymph_nodes
49. malaise
50. blurred_and_distorted_vision
51. phlegm
52. throat_irritation
53. redness_of_eyes
54. sinus_pressure
55. runny_nose
56. congestion
57. chest_pain
58. weakness_in_limbs
59. fast_heart_rate
60. pain_during_bowel_movements
61. pain_in_anal_region
62. bloody_stool
63. irritation_in_anus
64. neck_pain
65. dizziness
66. cramps
67. bruising
68. obesity
69. swollen_legs
70. swollen_blood_vessels
71. puffy_face_and_eyes
72. enlarged_thyroid
73. brittle_nails
74. swollen_extremeties
75. excessive_hunger
76. extra_marital_contacts
77. drying_and_tingling_lips
78. slurred_speech
79. knee_pain
80. hip_joint_pain
81. muscle_weakness
82. stiff_neck
83. swelling_joints
84. movement_stiffness
85. spinning_movements
86. loss_of_balance
87. unsteadiness
88. weakness_of_one_body_side
89. loss_of_smell
90. bladder_discomfort
91. foul_smell_of_urine
92. continuous_feel_of_urine
93. passage_of_gases
94. internal_itching
95. toxic_look_(typhos)
96. depression
97. irritability
98. muscle_pain
99. altered_sensorium
100. red_spots_over_body
101. belly_pain
102. abnormal_menstruation
103. dischromic_patches
104. watering_from_eyes
105. increased_appetite
106. polyuria
107. family_history
108. mucoid_sputum
109. rusty_sputum
110. lack_of_concentration
111. visual_disturbances
112. receiving_blood_transfusion
113. receiving_unsterile_injections
114. coma
115. stomach_bleeding
116. distention_of_abdomen
117. history_of_alcohol_consumption
118. fluid_overload
119. blood_in_sputum
120. prominent_veins_on_calf
121. palpitations
122. painful_walking
123. pus_filled_pimples
124. blackheads
125. scurring
126. skin_peeling
127. silver_like_dusting
128. small_dents_in_nails
129. inflammatory_nails
130. blister
131. red_sore_around_nose
132. yellow_crust_ooze

### Tablas PostgreSQL Propuestas:

```sql
-- Catálogo de síntomas del dataset
CREATE TABLE sintomas_catalogo (
    id SERIAL PRIMARY KEY,
    nombre_original VARCHAR(100) UNIQUE NOT NULL, -- En inglés
    nombre_espanol VARCHAR(100), -- Traducción
    nombre_lower TEXT, -- Para búsquedas
    categoria VARCHAR(50), -- Ej: dermatológico, respiratorio, digestivo
    fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Catálogo de enfermedades del dataset
CREATE TABLE enfermedades_dataset (
    id SERIAL PRIMARY KEY,
    nombre_original VARCHAR(100) UNIQUE NOT NULL, -- En inglés
    nombre_espanol VARCHAR(100), -- Traducción
    nombre_lower TEXT,
    fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relaciones enfermedad-síntoma (importadas del dataset)
CREATE TABLE enfermedad_sintoma_dataset (
    id SERIAL PRIMARY KEY,
    enfermedad_id INTEGER NOT NULL REFERENCES enfermedades_dataset(id),
    sintoma_id INTEGER NOT NULL REFERENCES sintomas_catalogo(id),
    frecuencia VARCHAR(20) DEFAULT 'comun', -- común, raro, muy común
    fuente VARCHAR(100) DEFAULT 'kaggle-disease-symptom-dataset',
    fecha_importacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enfermedad_id, sintoma_id)
);

CREATE INDEX idx_enfermedad_sintoma_enfermedad ON enfermedad_sintoma_dataset(enfermedad_id);
CREATE INDEX idx_enfermedad_sintoma_sintoma ON enfermedad_sintoma_dataset(sintoma_id);
```

---

## 📦 Dataset 3: Tabla de Sinónimos Médicos

**Propósito:** Normalizar términos para mejorar el matching

### Tabla PostgreSQL:
```sql
CREATE TABLE sinonimos_medicos (
    id SERIAL PRIMARY KEY,
    termino_original VARCHAR(200) NOT NULL,
    termino_normalizado VARCHAR(200) NOT NULL,
    tipo VARCHAR(20), -- 'enfermedad', 'sintoma', 'medicamento'
    idioma VARCHAR(10) DEFAULT 'es',
    fuente VARCHAR(100),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sinonimos_original ON sinonimos_medicos(termino_original);
CREATE INDEX idx_sinonimos_normalizado ON sinonimos_medicos(termino_normalizado);

-- Ejemplos de sinónimos a insertar:
-- 'dolor de cabeza' → 'cefalea'
-- 'gripe' → 'influenza'
-- 'fiebre' → 'hipertermia'
-- 'headache' → 'cefalea'
-- 'itching' → 'picazón'
```

---

## 🔄 Plan de Importación Completo

### Paso 1: Descargar Datasets
```bash
# CIE-10 español
curl -L "https://raw.githubusercontent.com/verasativa/CIE-10/master/cie-10.csv" -o cie10.csv

# Disease-Symptom dataset
curl -L "https://raw.githubusercontent.com/anujdutt9/Disease-Prediction-from-Symptoms/master/dataset/training_data.csv" -o disease_symptom.csv
```

### Paso 2: Crear Script Python de Importación

El script debe:
1. Leer cie-10.csv e importar a `enfermedades_catalogo`
2. Leer disease_symptom.csv y:
   - Extraer lista única de síntomas → importar a `sintomas_catalogo`
   - Extraer lista única de enfermedades → importar a `enfermedades_dataset`
   - Crear relaciones enfermedad-síntoma → importar a `enfermedad_sintoma_dataset`
3. Traducir términos del inglés al español usando Google Translate API (o manual)
4. Generar tabla de sinónimos automáticamente

### Paso 3: Integración con Algoritmo de Sugerencia

**Algoritmo actual (hardcodeado):**
```python
REGLAS_DIAGNOSTICOS = {
    'gripe': ['fiebre', 'tos', 'dolor de garganta'],
    ...
}
```

**Nuevo algoritmo (basado en BD):**
```python
def sugerir_sintomas_desde_texto(texto):
    # 1. Normalizar texto con sinónimos
    texto_normalizado = normalizar_con_sinonimos(texto)

    # 2. Buscar enfermedades mencionadas en el texto
    enfermedades_encontradas = buscar_enfermedades_en_bd(texto_normalizado)

    # 3. Para cada enfermedad, obtener síntomas relacionados
    sintomas_sugeridos = []
    for enfermedad in enfermedades_encontradas:
        sintomas = obtener_sintomas_de_enfermedad(enfermedad.id)
        sintomas_sugeridos.extend(sintomas)

    # 4. Deduplicar y ordenar por frecuencia
    return deduplicar_y_ordenar(sintomas_sugeridos)
```

---

## 💡 Ventajas del Sistema Propuesto

1. ✅ **Escalable:** Miles de enfermedades y síntomas disponibles
2. ✅ **Actualizable:** Puedes importar nuevas versiones de datasets
3. ✅ **Preciso:** Basado en datos médicos reales (no opiniones)
4. ✅ **Flexible:** Puedes agregar/editar relaciones desde admin
5. ✅ **Multiidioma:** Soporte español + inglés con traducciones
6. ✅ **Inteligente:** Maneja sinónimos automáticamente
7. ✅ **Trazable:** Sabes de dónde viene cada dato (fuente)

---

## 📋 Próximos Pasos

1. **Crear tablas en PostgreSQL** (ejecutar en Render)
2. **Descargar datasets localmente**
3. **Crear script Python de importación** (`importar_datasets_medicos.py`)
4. **Traducir términos al español** (manual o con API)
5. **Ejecutar importación** (conectando a BD de producción)
6. **Modificar algoritmo** de sugerencia de síntomas
7. **Probar en template** `admin_sugerir_sintomas.html`
8. **Crear interfaz admin** para gestionar catálogos

---

## 🔗 Referencias

- [CIE-10 en español (GitHub)](https://github.com/verasativa/CIE-10)
- [Disease-Symptom Dataset (GitHub)](https://github.com/anujdutt9/Disease-Prediction-from-Symptoms)
- [Disease Symptom Prediction (Kaggle)](https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset)
- [Mendeley Dataset 2023](https://data.mendeley.com/datasets/2cxccsxydc/1)
- [datos.gob.es - Datasets Enfermedades](https://datos.gob.es/en/catalogo?res_format_label=CSV&tags=enfermedades&theme_id=salud)
