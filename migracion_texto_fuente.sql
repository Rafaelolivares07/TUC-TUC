-- Migración: Agregar columna texto_fuente a tabla medicamentos
-- Fecha: 2026-01-04
-- Propósito: Guardar el texto completo usado para detectar síntomas de cada medicamento

-- Verificar si la columna ya existe antes de agregarla
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'medicamentos'
        AND column_name = 'texto_fuente'
    ) THEN
        ALTER TABLE medicamentos
        ADD COLUMN texto_fuente TEXT;

        RAISE NOTICE 'Columna texto_fuente agregada exitosamente';
    ELSE
        RAISE NOTICE 'Columna texto_fuente ya existe, no se realizaron cambios';
    END IF;
END $$;

-- Verificación
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'medicamentos'
AND column_name = 'texto_fuente';
