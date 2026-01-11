# 📚 Instrucciones para Importar Datasets Médicos

## 🎯 Objetivo

Importar librerías médicas completas (CIE-10 + Disease-Symptom Dataset) a PostgreSQL para automatizar la sugerencia de síntomas basada en datos reales.

---

## 📋 Pre-requisitos

1. ✅ Python 3.x instalado
2. ✅ Librería `psycopg2` instalada
3. ✅ Acceso a la BD de producción en Render
4. ✅ Variable de entorno `DATABASE_URL` configurada

---

## 🚀 Pasos de Ejecución

### Paso 1: Instalar dependencias

```bash
pip install psycopg2-binary
```

### Paso 2: Configurar DATABASE_URL

**Opción A: Variable de entorno (Linux/Mac)**
```bash
export DATABASE_URL="postgresql://usuario:password@host:puerto/database"
```

**Opción B: Variable de entorno (Windows)**
```cmd
set DATABASE_URL=postgresql://usuario:password@host:puerto/database
```

**Opción C: Editar el script**
Reemplazar en `importar_datasets_medicos.py`:
```python
DATABASE_URL = os.getenv('DATABASE_URL')
```

Por:
```python
DATABASE_URL = "tu_url_de_render_aqui"
```

### Paso 3: Ejecutar el script

```bash
python importar_datasets_medicos.py
```

### Paso 4: Verificar importación

El script mostrará el progreso:
```
📥 Descargando datasets...
  ✅ CIE-10 descargado
  ✅ Disease-Symptom descargado

🔌 Conectando a PostgreSQL...
  ✅ Conexión exitosa

🔨 Creando tablas en PostgreSQL...
  ✅ Tablas creadas exitosamente

📊 Importando CIE-10...
  → 100 registros importados...
  → 200 registros importados...
  ✅ XXXX enfermedades CIE-10 importadas

📊 Importando Disease-Symptom dataset...
  → Paso 1: Importando síntomas...
  ✅ 132 síntomas importados
  → Paso 2: Importando enfermedades...
  ✅ 41 enfermedades importadas
  → Paso 3: Creando relaciones enfermedad-síntoma...
    → 100 relaciones creadas...
    → 200 relaciones creadas...
  ✅ XXXX relaciones enfermedad-síntoma creadas

✅ IMPORTACIÓN COMPLETADA EXITOSAMENTE
```

---

## 📊 Tablas Creadas

Después de la importación, tendrás estas tablas en PostgreSQL:

### 1. `enfermedades_catalogo`
```sql
id | codigo | codigo_padre_0 | ... | descripcion | descripcion_lower | nivel | fuente
---|--------|---------------|-----|-------------|-------------------|-------|--------
1  | A00-B99| NULL          | ... | Ciertas...  | ciertas...        | 0     | icdcode
```

**Uso:** Catálogo completo de enfermedades del CIE-10 en español

### 2. `sintomas_catalogo`
```sql
id | nombre_original | nombre_espanol    | nombre_lower      | categoria
---|----------------|-------------------|-------------------|----------
1  | itching        | picazón           | picazón           | NULL
2  | skin_rash      | erupción cutánea  | erupción cutánea  | NULL
```

**Uso:** Catálogo de 132 síntomas en inglés y español

### 3. `enfermedades_dataset`
```sql
id | nombre_original    | nombre_espanol       | nombre_lower
---|-------------------|---------------------|-------------
1  | Fungal infection  | Infección fúngica   | infección fúngica
2  | Allergy           | Alergia             | alergia
```

**Uso:** Catálogo de ~41 enfermedades comunes del dataset

### 4. `enfermedad_sintoma_dataset`
```sql
id | enfermedad_id | sintoma_id | frecuencia | fuente
---|--------------|-----------|-----------|---------
1  | 1            | 1         | comun     | kaggle-disease-symptom-dataset
2  | 1            | 2         | comun     | kaggle-disease-symptom-dataset
```

**Uso:** Relaciones enfermedad ↔ síntoma (miles de registros)

### 5. `sinonimos_medicos`
```sql
id | termino_original | termino_normalizado | tipo      | idioma
---|------------------|---------------------|-----------|-------
1  | dolor de cabeza  | cefalea             | sintoma   | es
2  | headache         | cefalea             | sintoma   | en
```

**Uso:** Normalización de términos médicos (para futuro)

---

## 🔍 Consultas de Verificación

Después de importar, puedes verificar con estas queries:

```sql
-- Contar enfermedades CIE-10
SELECT COUNT(*) FROM enfermedades_catalogo;

-- Contar síntomas
SELECT COUNT(*) FROM sintomas_catalogo;

-- Contar enfermedades del dataset
SELECT COUNT(*) FROM enfermedades_dataset;

-- Contar relaciones enfermedad-síntoma
SELECT COUNT(*) FROM enfermedad_sintoma_dataset;

-- Ver enfermedades con más síntomas asociados
SELECT
    e.nombre_espanol,
    COUNT(es.sintoma_id) as num_sintomas
FROM enfermedades_dataset e
LEFT JOIN enfermedad_sintoma_dataset es ON e.id = es.enfermedad_id
GROUP BY e.id, e.nombre_espanol
ORDER BY num_sintomas DESC
LIMIT 10;

-- Ver síntomas más comunes (en más enfermedades)
SELECT
    s.nombre_espanol,
    COUNT(es.enfermedad_id) as num_enfermedades
FROM sintomas_catalogo s
LEFT JOIN enfermedad_sintoma_dataset es ON s.id = es.sintoma_id
GROUP BY s.id, s.nombre_espanol
ORDER BY num_enfermedades DESC
LIMIT 20;

-- Ejemplo: Obtener todos los síntomas de "Gripe"
SELECT
    s.nombre_espanol as sintoma
FROM enfermedades_dataset e
JOIN enfermedad_sintoma_dataset es ON e.id = es.enfermedad_id
JOIN sintomas_catalogo s ON es.sintoma_id = s.id
WHERE e.nombre_espanol ILIKE '%gripe%'
   OR e.nombre_espanol ILIKE '%resfriado%'
   OR e.nombre_espanol ILIKE '%cold%';
```

---

## 💡 Próximos Pasos

### 1. Modificar Algoritmo de Sugerencia de Síntomas

**Antes (hardcodeado):**
```python
REGLAS_DIAGNOSTICOS = {
    'gripe': ['fiebre', 'tos', 'dolor de garganta'],
    ...
}

def extraer_diagnosticos_de_texto(texto):
    for diagnostico, sintomas in REGLAS_DIAGNOSTICOS.items():
        if diagnostico in texto.lower():
            return sintomas
```

**Después (basado en BD):**
```python
def extraer_diagnosticos_de_texto(texto, conn):
    sintomas_sugeridos = []

    # Buscar enfermedades en el texto
    cursor = conn.cursor()

    # Opción 1: Buscar en enfermedades_dataset (41 enfermedades comunes)
    cursor.execute("""
        SELECT id, nombre_espanol
        FROM enfermedades_dataset
        WHERE %s ILIKE '%%' || nombre_lower || '%%'
    """, (texto.lower(),))

    enfermedades_encontradas = cursor.fetchall()

    for enfermedad_id, enfermedad_nombre in enfermedades_encontradas:
        # Obtener síntomas de esta enfermedad
        cursor.execute("""
            SELECT s.nombre_espanol
            FROM enfermedad_sintoma_dataset es
            JOIN sintomas_catalogo s ON es.sintoma_id = s.id
            WHERE es.enfermedad_id = %s
        """, (enfermedad_id,))

        sintomas = [row[0] for row in cursor.fetchall()]
        sintomas_sugeridos.extend(sintomas)

    # Deduplicar
    return list(set(sintomas_sugeridos))
```

### 2. Mejorar con Sinónimos

```python
def normalizar_termino(texto, conn):
    """Normaliza términos médicos usando tabla de sinónimos"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT termino_normalizado
        FROM sinonimos_medicos
        WHERE termino_original = %s
    """, (texto.lower(),))

    result = cursor.fetchone()
    return result[0] if result else texto
```

### 3. Crear Interfaz Admin para Gestionar

- Ver/editar catálogo de enfermedades
- Ver/editar catálogo de síntomas
- Agregar/eliminar relaciones enfermedad-síntoma
- Agregar sinónimos manualmente
- Importar nuevas versiones de datasets

---

## ⚠️ Notas Importantes

1. **Traducciones:** El script incluye traducciones manuales de los 132 síntomas y 41 enfermedades más comunes. Puedes expandir el diccionario `TRADUCCIONES_SINTOMAS` y `TRADUCCIONES_ENFERMEDADES`.

2. **ON CONFLICT:** El script usa `ON CONFLICT DO NOTHING` para evitar duplicados. Si re-ejecutas el script, no duplicará datos.

3. **Rendimiento:** La importación puede tardar varios minutos dependiendo de la conexión a Render.

4. **Backup:** Considera hacer backup de la BD antes de importar en producción.

5. **Datasets locales:** Los archivos `cie10_dataset.csv` y `disease_symptom_dataset.csv` se descargarán automáticamente y quedarán en el directorio del proyecto.

---

## 🐛 Solución de Problemas

### Error: "psycopg2 not found"
```bash
pip install psycopg2-binary
```

### Error: "DATABASE_URL no encontrada"
Configura la variable de entorno o edita el script directamente.

### Error: "Connection refused"
Verifica que la URL de Render sea correcta y que la BD esté accesible.

### Error: "Permission denied"
Verifica que el usuario de PostgreSQL tenga permisos para crear tablas.

### Importación muy lenta
Es normal. El script crea miles de relaciones. Puedes ver el progreso en consola.

---

## 📞 Soporte

Si tienes problemas, revisa:
1. Los logs del script
2. Las queries de verificación
3. La conexión a PostgreSQL

---

**Autor:** Claude Code
**Fecha:** 2026-01-03
**Versión:** 1.0
