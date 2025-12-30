# Reporte de Código Basura en 1_medicamentos.py

**Fecha**: 2025-12-30
**Archivo**: 1_medicamentos.py (15,649 líneas, 608 KB)
**Backup**: backups/1_medicamentos_backup_20251230_110331.py

---

## 🔴 CATEGORÍA 1: CÓDIGO SQLITE OBSOLETO (YA USAMOS POSTGRESQL)

### Imports obsoletos:
- **Línea 4**: `import sqlite3` - Ya no se usa, todo es PostgreSQL
- **Línea 205**: `DB_NAME = 'medicamentos.db'` - Constante obsoleta

### Rutas/Funciones que usan SQLite directamente:

#### 1. **Línea 7507-7531**: Ruta `/buscar_medicamentos`
```python
@app.route('/buscar_medicamentos')
def buscar_medicamentos():
    conn = sqlite3.connect('medicamentos.db')  # LÍNEA 7515
```
- **USO**: Buscar medicamentos por nombre (autocompletado)
- **PROBLEMA**: Usa SQLite en lugar de PostgreSQL
- **ACCIÓN**: REEMPLAZAR con get_db_connection()

#### 2. **Línea 7537-7613**: Ruta `/crear_medicamento_rapido`
```python
@app.route('/crear_medicamento_rapido', methods=['POST'])
def crear_medicamento_rapido():
    conn = sqlite3.connect('medicamentos.db')  # LÍNEA 7546
```
- **USO**: Crear medicamento sin recargar página
- **PROBLEMA**: Usa SQLite en lugar de PostgreSQL
- **ACCIÓN**: REEMPLAZAR con get_db_connection()

#### 3. **Línea 8627-8764**: Ruta `/admin/actualizar_precios`
```python
@app.route('/admin/actualizar_precios', methods=['GET', 'POST'])
def actualizar_precios():
    conn = sqlite3.connect('medicamentos.db')  # LÍNEA 8633
```
- **USO**: Actualizar precios según políticas de competencia
- **PROBLEMA**: Usa SQLite en lugar de PostgreSQL
- **ACCIÓN**: REEMPLAZAR con get_db_connection() + verificar si se usa esta feature

#### 4. **Línea 8695**: Dentro de `actualizar_precios()`
```python
conn = sqlite3.connect('medicamentos.db')  # Segunda conexión en misma función
```
- **PROBLEMA**: Conexión duplicada dentro de la misma función
- **ACCIÓN**: Eliminar y usar la conexión principal

### Código de migración (una sola vez):
- **Líneas 10117-10164**: Migración de pastillero de SQLite a PostgreSQL
  - **DECISIÓN**: ¿Ya se ejecutó esta migración? Si sí, es basura.

### Excepciones SQLite:
- **Línea 4782**: `except sqlite3.Error as e:` - Catch obsoleto
- **Línea 5554**: `except (sqlite3.Error, Exception) as e:` - Catch obsoleto
- **Línea 7071**: `except sqlite3.OperationalError as e:` - Catch obsoleto

---

## 🟡 CATEGORÍA 2: PRINTS DE DEBUG (469 ocurrencias)

**Total**: 469 `print()` statements en todo el archivo

**Ejemplos**:
- **Línea 1982**: `# DEBUG: Print de entrada` - Comentario explícito de debug

**DECISIÓN NECESARIA**:
- ¿Eliminar todos los prints?
- ¿Reemplazar con logging?
- ¿Dejar algunos para producción?

---

## 🟢 CATEGORÍA 3: CÓDIGO DE POLÍTICAS DE PRECIOS

### Funciones relacionadas con cotizaciones:
- **Línea 61**: `calcular_precio_segun_politica()` - Función completa (líneas 61-100+)
- Usa tablas: `CONFIGURACION_PRECIOS`, `precios_competencia`

**PREGUNTA**: ¿Esta feature se usa actualmente? ¿Hay rutas que la llamen?

---

## 📊 ESTADÍSTICAS GENERALES

- **Total funciones**: 290
- **Total rutas**: 240
- **Líneas de código**: 15,649
- **Tamaño**: 608 KB

---

## ⚠️ RECOMENDACIONES DE ANÁLISIS ADICIONAL

1. **Buscar rutas no usadas**: Rutas que nunca se llaman desde templates
2. **Buscar funciones huérfanas**: Funciones definidas pero nunca llamadas
3. **Buscar código comentado**: Bloques grandes de código en comentarios
4. **Verificar imports no usados**: sqlalchemy, pandas si no se usan

---

## 🎯 PRÓXIMOS PASOS SEGUROS

1. **PRIMERO**: Identificar qué líneas específicas (7515, 7546, 8633, 8695) contienen
2. **SEGUNDO**: Determinar si la migración de pastillero ya se ejecutó
3. **TERCERO**: Decidir qué hacer con prints (eliminar, logging, o dejar)
4. **CUARTO**: Verificar si políticas de precios se usan

**ESPERANDO INSTRUCCIONES DEL USUARIO ANTES DE ELIMINAR CUALQUIER CÓDIGO**
