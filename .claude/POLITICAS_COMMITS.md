# Políticas de Commits y Despliegue

## 🎯 Objetivo
Mantener un historial de commits limpio, organizado y que no sature Render con deploys innecesarios.

## 📋 Cuándo hacer commit

### ✅ HACER COMMIT cuando:
1. **Feature completa funcionando**
   - Ej: "Sistema de recordatorios sin botones + horarios fijos"
   - Incluye todos los cambios relacionados a esa feature

2. **Bug crítico corregido**
   - Ej: "Fix: Error 500 en /api/restaurar-sesion por emojis"
   - Solo si rompe funcionalidad en producción

3. **Fin del día de trabajo**
   - Commits acumulados del día
   - Mensaje descriptivo de todos los cambios

### 🔴 CAMBIOS EN BASE DE DATOS - TRATAMIENTO ESPECIAL

**Los cambios de estructura de BD SIEMPRE requieren:**

1. **Script SQL de migración separado**
   - Crear archivo `migracion_YYYY-MM-DD_descripcion.sql`
   - Documentar claramente qué columnas/tablas se agregan/modifican
   - Incluir comentarios SQL explicativos

2. **Endpoint de migración temporal** (si es necesario)
   - Crear endpoint `/api/migrar-[nombre-feature]`
   - Solo para agregar columnas o modificar estructura
   - Documentar en el commit que existe el endpoint

3. **Commit separado ANTES del código que usa las columnas**
   - Commit 1: "DB: Agregar columnas tipo_medicamento y campos de tratamiento"
   - Deploy y ejecutar migración en producción
   - Verificar que migración funcionó
   - Commit 2: "Add: Sistema de tipos de medicamentos (botiquín/tratamiento)"

4. **Verificación obligatoria**
   - Probar migración en local primero
   - Ejecutar en producción vía endpoint
   - Verificar con consulta SQL que columnas existen
   - Solo entonces hacer el commit del código que las usa

**Ejemplo de flujo correcto:**
```
1. Crear migracion_2026-01-02_tipos_medicamentos.sql
2. Crear endpoint /api/migrar-tipos-medicamentos
3. Commit: "DB: Agregar columnas para tipos de medicamentos"
4. Push y deploy
5. Ejecutar endpoint en producción
6. Verificar columnas en PostgreSQL
7. Escribir código que usa las nuevas columnas
8. Commit: "Add: Sistema de tipos de medicamentos"
9. Push y deploy
```

**⚠️ NUNCA:**
- Hacer commit de código que usa columnas que no existen en producción
- Asumir que la migración funcionó sin verificar
- Deployar código y migración al mismo tiempo sin probar

### ❌ NO hacer commit individual por:
- Cada pequeño cambio de una línea
- Cambios experimentales que aún no probamos
- Refactorizaciones parciales

## 🔄 Workflow recomendado

```
1. Usuario pide cambios relacionados
   ↓
2. Acumular cambios en archivos locales
   ↓
3. Probar localmente con Flask
   ↓
4. Cuando la feature esté completa y probada:
   → git add .
   → git commit (con mensaje descriptivo)
   → git push
```

## 📝 Formato de mensajes de commit

```
Tipo: Descripción breve en español

Cambios detallados:
- Punto 1
- Punto 2
- Punto 3

Impacto:
- Qué mejora o soluciona

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Tipos:**
- `Fix:` - Corrección de bug
- `Add:` - Nueva funcionalidad
- `Update:` - Mejora de funcionalidad existente
- `Refactor:` - Cambio de código sin cambiar funcionalidad
- `Docs:` - Documentación
- `DB:` - Cambios en estructura de base de datos (migraciones)

## 🚫 Evitar
- Commits cada 5 minutos
- Mensajes vagos como "cambios" o "fix"
- Push sin probar localmente

## ✅ Regla de oro
**1 feature completa y probada = 1 commit**

---

*Última actualización: 2026-01-02*
