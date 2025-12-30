-- ================================================================
-- SCRIPT: Agregar tipos de medicamentos (Botiquín vs Tratamiento)
-- FECHA: 2025-12-30
-- DESCRIPCIÓN: Extiende pastillero_usuarios con campos para diferenciar
--              medicamentos de botiquín (stock permanente) vs tratamiento
-- ================================================================

-- 1. Agregar campo tipo_medicamento
ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS tipo_medicamento VARCHAR(20) DEFAULT 'botiquin'
CHECK (tipo_medicamento IN ('botiquin', 'tratamiento'));

-- 2. Campos para BOTIQUÍN (alertas de reposición)
ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS alerta_reposicion BOOLEAN DEFAULT FALSE;

ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS nivel_minimo_alerta INTEGER DEFAULT 10;

-- 3. Campos para TRATAMIENTO (fechas y tomas)
ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS fecha_inicio_tratamiento DATE DEFAULT NULL;

ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS fecha_fin_tratamiento DATE DEFAULT NULL;

ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS tomas_completadas INTEGER DEFAULT 0;

-- 4. Campo para posponer alertas (botón "Ahora no")
ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS alerta_pospuesta_hasta TIMESTAMP DEFAULT NULL;

-- 5. Crear índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_pastillero_tipo_medicamento
ON pastillero_usuarios(tipo_medicamento);

CREATE INDEX IF NOT EXISTS idx_pastillero_alertas_botiquin
ON pastillero_usuarios(tipo_medicamento, alerta_reposicion, cantidad)
WHERE tipo_medicamento = 'botiquin' AND alerta_reposicion = TRUE;

CREATE INDEX IF NOT EXISTS idx_pastillero_tratamientos_activos
ON pastillero_usuarios(tipo_medicamento, fecha_fin_tratamiento)
WHERE tipo_medicamento = 'tratamiento' AND fecha_fin_tratamiento IS NOT NULL;

-- 6. Comentarios para documentación
COMMENT ON COLUMN pastillero_usuarios.tipo_medicamento IS
'Tipo de medicamento: botiquin (stock permanente) o tratamiento (temporal con fecha fin)';

COMMENT ON COLUMN pastillero_usuarios.alerta_reposicion IS
'Activa alerta cuando cantidad <= nivel_minimo_alerta (solo para tipo botiquin)';

COMMENT ON COLUMN pastillero_usuarios.nivel_minimo_alerta IS
'Cantidad mínima que dispara alerta de reposición (default 10 unidades)';

COMMENT ON COLUMN pastillero_usuarios.fecha_inicio_tratamiento IS
'Fecha inicio del tratamiento (solo para tipo tratamiento)';

COMMENT ON COLUMN pastillero_usuarios.fecha_fin_tratamiento IS
'Fecha fin del tratamiento - usado para calcular tomas pendientes (solo para tipo tratamiento)';

COMMENT ON COLUMN pastillero_usuarios.tomas_completadas IS
'Contador de tomas realizadas - se incrementa al marcar "Ya tomé" (solo para tipo tratamiento)';

COMMENT ON COLUMN pastillero_usuarios.alerta_pospuesta_hasta IS
'Timestamp hasta cuando posponer alerta (botón "Ahora no" = +24 horas)';

-- 7. Verificación
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'pastillero_usuarios'
  AND column_name IN (
      'tipo_medicamento',
      'alerta_reposicion',
      'nivel_minimo_alerta',
      'fecha_inicio_tratamiento',
      'fecha_fin_tratamiento',
      'tomas_completadas',
      'alerta_pospuesta_hasta'
  )
ORDER BY ordinal_position;

-- Script completado exitosamente
