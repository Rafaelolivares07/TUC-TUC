# Registro de Cambios Pendientes

## 📅 Fecha: 2026-01-02

### ✅ Cambios YA commiteados hoy:

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

#### En progreso: Migración de módulo de requerimientos a PostgreSQL
- **Script SQL:** `migracion_requerimientos.sql` creado
- **Endpoint migración:** `/api/migrar-requerimientos-db` implementado
- **Cambios en código:**
  - Actualizado sintaxis SQLite (`?`) a PostgreSQL (`%s`) en todos los endpoints de requerimientos
  - Archivos: `1_medicamentos.py` (líneas 4381-4855)
  - Endpoints modificados: 9 endpoints relacionados con requerimientos, referencias y archivos
- **Tablas creadas:** `REQUERIMIENTOS`, `REQUERIMIENTO_REFERENCIAS`, `archivos`
- **Estado:** Migración ejecutada y verificada exitosamente
- **Próximo paso:** Commit siguiendo política de commits

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

3. **migracion_requerimientos.sql** - Ejecutada (2026-01-02)
   - Tablas creadas: `REQUERIMIENTOS`, `REQUERIMIENTO_REFERENCIAS`, `archivos`
   - Columnas: Completo sistema de gestión de requerimientos con referencias a código
   - Índices: 6 índices para optimización de queries
   - Triggers: Sistema automático para actualizar `fecha_actualizacion`
   - Endpoint: `/api/migrar-requerimientos-db`
   - Fecha ejecución: 2026-01-02
   - **Objetivo:** Migrar módulo de requerimientos de SQLite a PostgreSQL

### 🔄 Migraciones pendientes:

*Ninguna actualmente*

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
