# Registro de Cambios Pendientes

## 📅 Fecha: 2026-01-02

### ✅ Cambios YA commiteados hoy:

#### Commit `a8f2ad8` - Fix: Usar ON CONFLICT DO NOTHING para evitar duplicados
- Error: "duplicate key value violates unique constraint DIAGNOSTICO_MEDICAMENTO_pkey"
- Reemplazar SELECT previo + INSERT condicional por INSERT ... ON CONFLICT DO NOTHING
- Aplicado a medicamento_sintoma y diagnostico_medicamento
- Más eficiente y thread-safe que verificación manual
- **Verificado en producción**: Guardado de síntomas funciona correctamente
- Archivo: 1_medicamentos.py (líneas 16530-16545)

#### Commit `de48cde` - Fix: Usar information_schema en vez de pg_get_serial_sequence
- Endpoint /api/diagnosticar-sintomas-db fallaba con "relation 'sintomas' does not exist"
- pg_get_serial_sequence('SINTOMAS', 'id') busca internamente en lowercase
- Solución: Consultar information_schema.columns directamente para obtener column_default
- Extraer nombre de secuencia del valor nextval() si existe
- **Ejecutado en producción**: Secuencia sintomas_id_seq creada y asociada (next_value: 17076)
- Archivo: 1_medicamentos.py (líneas 3123-3144)

#### Commit `f631823` - Update: Mejorar detección de suplementos y deficiencias nutricionales
- Agregadas 9 nuevas reglas de diagnóstico (osteoporosis, raquitismo, deficiencias vitamínicas/minerales)
- Implementado sistema de detección de patrones de prevención/tratamiento
- Expandidas keywords de síntomas: 15 nuevos síntomas relacionados con deficiencias nutricionales
- Ahora detecta correctamente suplementos como Vitamina D3
- Archivo: sugerir_sintomas_helpers.py

#### Commit `f3ae651` - Fix: Corregir nombre de tabla diagnostico_medicamento
- Tabla correcta: `diagnostico_medicamento` (no `medicamento_diagnostico`)
- Corregidos SELECT e INSERT en endpoints de sugerir-sintomas
- Error: "relation 'medicamento_diagnostico' does not exist"
- Archivo: 1_medicamentos.py (líneas 16410-16431)

#### Commit `b428635` - Fix: Especificar RETURNING medicamento_id en tablas de relación
- Agregado `RETURNING medicamento_id` explícito para medicamento_sintoma y diagnostico_medicamento
- Evita que wrapper auto-agregue `RETURNING id` en tablas sin columna id
- Error: "column 'id' does not exist"
- Archivo: 1_medicamentos.py (líneas 16410-16431)

#### Commit `c6ffe1d` - Fix: Agregar ORDER BY expressions en SELECT DISTINCT
- Agregadas columnas `es_generico_sort` y `sin_precio_sort` al SELECT
- Requerido por PostgreSQL cuando se usa DISTINCT con ORDER BY
- Error: "ORDER BY expressions must appear in select list"
- Archivo: 1_medicamentos.py (líneas 16195-16212)

#### Commit `72b977e` - Fix: Cambiar f-string a concatenación en query de filtros
- Cambiado de f-string a concatenación para que wrapper PostgreSQL funcione
- F-string bypass wrapper y causaba error 500 en filtros
- Archivo: 1_medicamentos.py (líneas 16195-16212)

#### Commit `fdf2e61` - DB: Migrar módulo de requerimientos a PostgreSQL
- Creadas 3 tablas: REQUERIMIENTOS, REQUERIMIENTO_REFERENCIAS, archivos
- Actualizados 9 endpoints de sintaxis SQLite a PostgreSQL
- Endpoint temporal `/api/migrar-requerimientos-db` implementado
- Documentación completa: REQUERIMIENTOS.md, POLITICAS_COMMITS.md
- **PENDIENTE:** Ejecutar migración en producción (Render)

#### Commit `0bd74f5` - Fix: Remover emojis de print statements
- Eliminados emojis que causaban UnicodeEncodeError en Windows
- Afecta: líneas 644, 683, 686, 1882, 1945, 1954, 1957, 1968, 12736, 12746, 12752, 12759, 12771, 12775, 12798, 12816, 12852, 12875, 12884, 12897

#### Commit `3402815` - Fix: Recordatorios Telegram sin botones + horarios fijos
- Eliminados botones "Ya tomé" y "Cancelar hoy"
- Cálculo de próxima_toma desde horario original, no desde "ahora"
- Evita desplazamiento de horarios

#### Commit `3f38ffe` - Fix: Mantener medicamentos en pastillero con cantidad = 0
- No eliminar automáticamente medicamentos cuando cantidad = 0
- Permite historial y alertas de reposición
- Beneficia tanto botiquín como tratamiento

---

### 🔨 Cambios en progreso (NO commiteados):

*Ninguno actualmente*

### 📋 Próximos pasos:
1. **Esperar deploy automático en Render** (GitHub → Render)
2. **Ejecutar migración en producción:**
   - Visitar: `https://tu-app.onrender.com/api/migrar-requerimientos-db`
   - Verificar respuesta exitosa
3. **Probar módulo de requerimientos:**
   - Acceder: `https://tu-app.onrender.com/admin/requerimientos`
   - Crear requerimiento de prueba
4. **Actualizar este documento** cuando se complete

---

## 🗄️ Estado de Migraciones de Base de Datos

### ✅ Migraciones ejecutadas en producción:

1. **migracion_carrito_columnas.sql** - Ejecutada
   - Agregadas: `precio_unitario`, `precio_total`, `estado` en `existencias`
   - Endpoint: `/api/migrar-carrito-db`
   - Fecha ejecución: 2026-01-01

2. **agregar_tipos_medicamentos.sql** - Ejecutada
   - Agregadas: `tipo_medicamento`, `alerta_reposicion`, `nivel_minimo_alerta`,
     `fecha_inicio_tratamiento`, `fecha_fin_tratamiento`, `tomas_completadas`,
     `alerta_pospuesta_hasta` en `pastillero_usuarios`
   - Endpoint: `/api/migrar-carrito-db` (mismo endpoint)
   - Fecha ejecución: 2026-01-01

3. **migracion_requerimientos.sql** - ⏳ Pendiente ejecución en producción
   - Tablas a crear: `REQUERIMIENTOS`, `REQUERIMIENTO_REFERENCIAS`, `archivos`
   - Columnas: Completo sistema de gestión de requerimientos con referencias a código
   - Índices: 6 índices para optimización de queries
   - Triggers: Sistema automático para actualizar `fecha_actualizacion`
   - Endpoint: `/api/migrar-requerimientos-db`
   - Fecha commit: 2026-01-02 (commit `fdf2e61`)
   - **Status:** Código deployado, falta ejecutar migración
   - **Objetivo:** Migrar módulo de requerimientos de SQLite a PostgreSQL

### 🔄 Migraciones pendientes:

1. **migracion_requerimientos.sql** - Ejecutar en Render después del deploy

### ⚠️ Notas importantes:
- Verificar siempre que las columnas existen antes de usar en código
- Mantener scripts SQL en el repositorio para referencia
- Documentar fecha de ejecución en producción

---

### 📝 Notas:
- Desde este punto seguiremos la política: **1 feature completa = 1 commit**
- Probar localmente antes de commit
- Agrupar cambios relacionados

---

*Actualizado automáticamente por Claude Code*
