# Módulo de Requerimientos

## 📋 Propósito
Este documento centraliza todos los requerimientos, features y bugs del proyecto **MiAppMedicamentos**.
Se enlaza con:
- [POLITICAS_COMMITS.md](POLITICAS_COMMITS.md) - Cómo y cuándo hacer commits
- [CAMBIOS_PENDIENTES.md](CAMBIOS_PENDIENTES.md) - Tracking de cambios en progreso
- **Sistema Web:** `/admin/requerimientos` - Interfaz de gestión de requerimientos

---

## 🎯 Requerimientos Activos

### 🟢 Pendientes de Implementar

*Ninguno actualmente*

### 🔵 En Análisis/Discusión

*Ninguno actualmente*

### 🟡 En Espera (Bloqueados)

*Ninguno actualmente*

---

## ✅ Requerimientos Completados (2026-01)

### REQ-005: Mejorar Detección de Suplementos y Deficiencias Nutricionales
**Fecha:** 2026-01-02
**Tipo:** Update
**Prioridad:** Media

**Descripción:**
Mejorar el sistema de sugerencia de síntomas para detectar correctamente suplementos vitamínicos y minerales, así como sus indicaciones de prevención y tratamiento.

**Problema identificado:**
- Suplementos como Vitamina D3 no generaban síntomas sugeridos
- No se detectaban patrones de prevención ("prevenir osteoporosis")
- No se reconocían deficiencias nutricionales como diagnósticos
- Keywords limitadas a síntomas comunes, sin cobertura ósea/nutricional

**Solución implementada:**

1. **Nuevas reglas de diagnóstico** (9 diagnósticos agregados):
   - Condiciones óseas: osteoporosis, raquitismo, osteomalacia
   - Deficiencias vitamínicas: vitamina D, C, B12
   - Deficiencias minerales: calcio, hierro
   - Condición endocrina: hipoparatiroidismo

2. **Sistema de detección de patrones de prevención/tratamiento**:
   - Detecta frases: "prevenir", "tratar", "usado para", "indicado para"
   - Extrae enfermedad mencionada del contexto
   - Asocia síntomas automáticamente desde REGLAS_DIAGNOSTICOS

3. **Expansión de keywords de síntomas** (15 nuevos síntomas):
   - Óseos: debilidad ósea, dolor óseo, fracturas, deformidades, pérdida de altura
   - Musculares: debilidad muscular, calambres, espasmos
   - Nutricionales: anemia, palidez, encías sangrantes
   - Sistémicos: hormigueo, depresión, crecimiento deficiente, dolor de espalda

**Resultado:**
Ahora el sistema detecta correctamente:
- "Vitamina D3 previene osteoporosis" → Síntomas: debilidad ósea, dolor óseo, fracturas
- "Usado para tratar raquitismo" → Síntomas: deformidades óseas, crecimiento deficiente
- "Deficiencia de vitamina C" → Síntomas: fatiga, encías sangrantes, anemia

**Commit:** `f631823` - Update: Mejorar detección de suplementos y deficiencias nutricionales
**Archivos:** [sugerir_sintomas_helpers.py](../sugerir_sintomas_helpers.py) (líneas 13-65, 212-268)

---

### REQ-001: Sistema de Recordatorios Telegram sin Botones
**Fecha:** 2026-01-02
**Tipo:** Fix + Update
**Prioridad:** Alta

**Descripción:**
Modificar sistema de recordatorios para mantener horarios fijos y eliminar botones interactivos temporalmente.

**Problema identificado:**
- Usuarios reportaban desplazamiento de horarios
- Botones "Ya tomé" y "Cancelar hoy" aún no son necesarios en esta etapa

**Solución implementada:**
- Eliminados botones de Telegram InlineKeyboard
- Cálculo de próxima_toma desde horario original (no desde "ahora")
- Mantiene horarios fijos como usuarios esperan

**Commit:** `3402815` - Fix: Recordatorios Telegram sin botones + horarios fijos
**Archivos:** [1_medicamentos.py](../1_medicamentos.py) (líneas 471-534)

---

### REQ-002: Mantener Medicamentos en Pastillero con Cantidad = 0
**Fecha:** 2026-01-02
**Tipo:** Fix
**Prioridad:** Media

**Descripción:**
Medicamentos no deben eliminarse automáticamente cuando cantidad = 0.

**Problema identificado:**
- Medicamentos desaparecían del pastillero al agotarse
- No se podía ver historial de medicamentos usados
- Botiquín necesita alertas de reposición aún con cantidad = 0
- Tratamientos deben mantenerse hasta fecha_fin_tratamiento

**Solución implementada:**
- Eliminar DELETE automático en línea 13432
- Permitir cantidad = 0 (no negativa)
- Mantener registro para historial y alertas

**Commit:** `3f38ffe` - Fix: Mantener medicamentos en pastillero con cantidad = 0
**Archivos:** [1_medicamentos.py](../1_medicamentos.py) (líneas 13428-13451)

---

### REQ-003: Políticas de Commits y Tracking de Cambios
**Fecha:** 2026-01-02
**Tipo:** Docs
**Prioridad:** Alta

**Descripción:**
Establecer políticas claras para commits y sistema de tracking de cambios.

**Problema identificado:**
- Múltiples commits pequeños saturaban Render con deploys
- No había claridad sobre cuándo hacer commit
- Cambios de BD necesitan tratamiento especial

**Solución implementada:**
- Creado `.claude/POLITICAS_COMMITS.md` con reglas claras
- Creado `.claude/CAMBIOS_PENDIENTES.md` para tracking
- Sección especial para migraciones de BD
- Regla de oro: 1 feature completa = 1 commit

**Archivos creados:**
- [POLITICAS_COMMITS.md](POLITICAS_COMMITS.md)
- [CAMBIOS_PENDIENTES.md](CAMBIOS_PENDIENTES.md)

---

### REQ-004: Migración de Módulo de Requerimientos a PostgreSQL
**Fecha:** 2026-01-02
**Tipo:** DB + Update
**Prioridad:** Alta

**Descripción:**
Migrar el módulo de gestión de requerimientos que funcionaba con SQLite a PostgreSQL para que funcione en producción (Render).

**Problema identificado:**
- Módulo de requerimientos web funcionaba solo con SQLite
- SQLite está prohibido, todo debe usar PostgreSQL
- Sintaxis SQLite (`?` placeholders) no compatible con PostgreSQL

**Solución implementada:**

#### 1. Script de Migración SQL
- Archivo: [migracion_requerimientos.sql](../migracion_requerimientos.sql)
- Tablas creadas:
  - `REQUERIMIENTOS` (id, descripcion, modulo, prioridad, estado, fechas)
  - `REQUERIMIENTO_REFERENCIAS` (referencias a código específico)
  - `archivos` (catálogo de archivos del proyecto)
- 6 índices para optimización
- Triggers automáticos para `fecha_actualizacion`

#### 2. Actualización de Endpoints
- 9 endpoints actualizados de sintaxis SQLite a PostgreSQL
- Cambio de `?` a `%s` en placeholders
- Cambio de `lastrowid` a `RETURNING id`
- Archivos modificados: [1_medicamentos.py](../1_medicamentos.py) líneas 4381-4855

**Endpoints actualizados:**
- `/api/requerimientos` (GET, POST)
- `/api/requerimientos/<id>` (PUT)
- `/api/requerimientos/<id>/referencias` (GET, POST)
- `/api/requerimientos/<id>/referencias/<ref_id>` (DELETE)
- `/api/requerimientos/<id>/referencias/<ref_id>/estado` (PUT)
- `/api/requerimientos/buscar_codigo` (GET)
- `/api/requerimientos/extraer_identificadores` (GET)
- `/api/archivos` (GET, POST)
- `/api/archivos/<id>` (DELETE)
- `/api/archivos/poblar` (POST)

#### 3. Endpoint de Migración Temporal
- Endpoint: `/api/migrar-requerimientos-db`
- Ejecuta script SQL completo directamente en PostgreSQL
- Verifica que las tablas existan correctamente
- Fecha ejecución: 2026-01-02

**Status:** ✅ Completado y verificado
**Próximo paso:** Commit y deploy a producción

---

## 🗄️ Migraciones de Base de Datos

### Ejecutadas en Producción

#### MIG-001: Columnas de Carrito (precio, estado)
**Fecha ejecución:** 2026-01-01
**Script:** `migracion_carrito_columnas.sql`
**Endpoint:** `/api/migrar-carrito-db`

**Columnas agregadas a `existencias`:**
- `precio_unitario` DECIMAL(10,2)
- `precio_total` DECIMAL(10,2)
- `estado` VARCHAR(20) DEFAULT 'pendiente'

**Status:** ✅ Verificada y funcionando

---

#### MIG-002: Tipos de Medicamentos (Botiquín/Tratamiento)
**Fecha ejecución:** 2026-01-01
**Script:** `agregar_tipos_medicamentos.sql`
**Endpoint:** `/api/migrar-carrito-db`

**Columnas agregadas a `pastillero_usuarios`:**
- `tipo_medicamento` VARCHAR(20) DEFAULT 'botiquin'
- `alerta_reposicion` BOOLEAN DEFAULT FALSE
- `nivel_minimo_alerta` INTEGER DEFAULT 10
- `fecha_inicio_tratamiento` DATE
- `fecha_fin_tratamiento` DATE
- `tomas_completadas` INTEGER DEFAULT 0
- `alerta_pospuesta_hasta` TIMESTAMP

**Índices creados:**
- `idx_pastillero_tipo_medicamento`
- `idx_pastillero_alertas_botiquin`
- `idx_pastillero_tratamientos_activos`

**Status:** ✅ Verificada y funcionando

---

#### MIG-003: Sistema de Requerimientos a PostgreSQL
**Fecha ejecución:** 2026-01-02
**Script:** [migracion_requerimientos.sql](../migracion_requerimientos.sql)
**Endpoint:** `/api/migrar-requerimientos-db`

**Tablas creadas:**
- `REQUERIMIENTOS` - Tabla principal de requerimientos
- `REQUERIMIENTO_REFERENCIAS` - Referencias a código específico (funciones, IDs, clases)
- `archivos` - Catálogo de archivos HTML/JS del proyecto

**Columnas principales:**

`REQUERIMIENTOS`:
- id SERIAL PRIMARY KEY
- descripcion TEXT NOT NULL
- modulo VARCHAR(100) NOT NULL
- prioridad VARCHAR(20) CHECK (Alta/Media/Baja)
- estado VARCHAR(50) DEFAULT 'Planificación'
- fecha_creacion TIMESTAMP
- fecha_actualizacion TIMESTAMP

`REQUERIMIENTO_REFERENCIAS`:
- id SERIAL PRIMARY KEY
- requerimiento_id INTEGER (FK a REQUERIMIENTOS)
- archivo_relacionado VARCHAR(255)
- seccion_identificador VARCHAR(255)
- descripcion_referencia TEXT
- estado VARCHAR(50) DEFAULT 'Pendiente'
- fecha_creacion TIMESTAMP
- fecha_actualizacion TIMESTAMP

`archivos`:
- id SERIAL PRIMARY KEY
- nombre_archivo VARCHAR(255) UNIQUE
- descripcion TEXT
- ruta VARCHAR(500)
- fecha_creacion TIMESTAMP

**Índices creados:**
- `idx_requerimientos_estado`
- `idx_requerimientos_prioridad`
- `idx_requerimientos_modulo`
- `idx_referencias_requerimiento_id`
- `idx_referencias_estado`
- `idx_archivos_nombre`

**Triggers:**
- `trigger_requerimientos_actualizacion` - Actualiza `fecha_actualizacion` automáticamente
- `trigger_referencias_actualizacion` - Actualiza `fecha_actualizacion` automáticamente

**Verificación:**
```bash
✅ Script SQL ejecutado completamente
✅ Tabla REQUERIMIENTOS existe
✅ Tabla REQUERIMIENTO_REFERENCIAS existe
✅ Tabla archivos existe
```

**Status:** ✅ Ejecutada y verificada exitosamente

---

### Pendientes

*Ninguna migración pendiente*

---

## 📊 Workflow de Requerimientos

### 1. Nuevo Requerimiento
Cuando el usuario solicita algo nuevo:

1. **Agregar a sección "🟢 Pendientes de Implementar"**
   ```markdown
   ### REQ-XXX: Título descriptivo
   **Tipo:** Fix / Add / Update / Refactor / DB
   **Prioridad:** Alta / Media / Baja
   **Descripción:** ...
   **Archivos afectados estimados:** ...
   ```

2. **Si es cambio de BD:**
   - Crear sección en "🗄️ Migraciones de Base de Datos"
   - Seguir workflow de [POLITICAS_COMMITS.md](POLITICAS_COMMITS.md)

### 2. Durante Implementación
1. Mover a "🔵 En Análisis/Discusión" o iniciar directamente
2. Agregar a [CAMBIOS_PENDIENTES.md](CAMBIOS_PENDIENTES.md) sección "🔨 Cambios en progreso"
3. Implementar y probar localmente

### 3. Al Completar
1. Hacer commit siguiendo [POLITICAS_COMMITS.md](POLITICAS_COMMITS.md)
2. Mover requerimiento a "✅ Requerimientos Completados"
3. Agregar hash de commit y archivos modificados
4. Actualizar [CAMBIOS_PENDIENTES.md](CAMBIOS_PENDIENTES.md) sección "✅ Cambios YA commiteados"

---

## 🔗 Enlaces entre Documentos

```
REQUERIMIENTOS.md (este archivo)
    ↓
    ├─→ Define QUÉ hacer
    ├─→ Tracking de features/bugs
    └─→ Historial de implementaciones

POLITICAS_COMMITS.md
    ↓
    ├─→ Define CÓMO commitear
    ├─→ Cuándo hacer commit
    └─→ Workflow de BD

CAMBIOS_PENDIENTES.md
    ↓
    ├─→ Estado ACTUAL de cambios
    ├─→ Qué está en progreso HOY
    └─→ Commits del día actual

Sistema Web: /admin/requerimientos
    ↓
    ├─→ Interfaz visual para gestionar requerimientos
    ├─→ Referencias de código vinculadas
    └─→ Export a JSON disponible
```

---

## 🌐 Sistema Web de Requerimientos

El proyecto incluye un módulo web completo para gestionar requerimientos:

### Acceso
- **URL:** `http://localhost:5000/admin/requerimientos` (requiere admin)
- **Template:** [admin_requerimientos.html](../templates/admin_requerimientos.html)

### Funcionalidades
1. **CRUD de Requerimientos:**
   - Crear, editar, listar requerimientos
   - Campos: descripción, módulo, prioridad, estado
   - Filtrado y búsqueda

2. **Referencias de Código:**
   - Vincular requerimientos a código específico
   - Buscar automáticamente funciones, IDs, clases en archivos HTML/JS
   - Vista previa de código
   - Estados: Pendiente / En Progreso / Completado

3. **Catálogo de Archivos:**
   - Auto-poblar archivos desde `/templates`
   - Filtrar por extensiones (.html, .js, .py, .css)

4. **Export JSON:**
   - Exportar requerimientos con todas sus referencias
   - Formato estructurado para backup o integración

### Base de Datos
- Tablas: `REQUERIMIENTOS`, `REQUERIMIENTO_REFERENCIAS`, `archivos`
- Motor: PostgreSQL (migrado desde SQLite)
- Ver [migracion_requerimientos.sql](../migracion_requerimientos.sql) para estructura completa

---

## 📝 Plantillas

### Template: Nuevo Requerimiento

```markdown
### REQ-XXX: [Título]
**Fecha:** YYYY-MM-DD
**Tipo:** Fix / Add / Update / Refactor / DB
**Prioridad:** Alta / Media / Baja

**Descripción:**
[Qué se necesita]

**Problema identificado:**
- [Problema 1]
- [Problema 2]

**Solución propuesta:**
- [Solución 1]
- [Solución 2]

**Archivos afectados estimados:**
- [archivo1.py](../archivo1.py) (líneas aproximadas)
- [archivo2.html](../templates/archivo2.html)

**Dependencias:**
- [Otros REQ-XXX si aplica]

**Status:** ⏳ Pendiente / 🔄 En progreso / ✅ Completado
```

### Template: Nueva Migración

```markdown
#### MIG-XXX: [Título]
**Fecha creación:** YYYY-MM-DD
**Fecha ejecución:** Pendiente / YYYY-MM-DD
**Script:** `migracion_nombre.sql`
**Endpoint:** `/api/migrar-[nombre]`

**Cambios:**
- Tabla `nombre_tabla`:
  - ADD COLUMN `campo1` TIPO
  - ADD COLUMN `campo2` TIPO

**Verificación:**
- [ ] Script SQL creado
- [ ] Probado en local
- [ ] Endpoint creado
- [ ] Commit de migración hecho
- [ ] Deploy ejecutado
- [ ] Migración corrida en producción
- [ ] Verificación con SELECT exitosa

**Status:** ⏳ Pendiente / ✅ Ejecutada
```

---

## 📈 Estadísticas

**Total requerimientos implementados:** 5
**Total migraciones ejecutadas:** 3
**Último update:** 2026-01-02

---

*Documento enlazado con [POLITICAS_COMMITS.md](POLITICAS_COMMITS.md) y [CAMBIOS_PENDIENTES.md](CAMBIOS_PENDIENTES.md)*
