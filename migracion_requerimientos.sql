-- =========================================================
-- MIGRACIÓN: Sistema de Requerimientos a PostgreSQL
-- Fecha: 2026-01-02
-- Descripción: Crear tablas para el módulo de gestión de
--              requerimientos con referencias de código
-- =========================================================

-- TABLA 1: requerimientos
-- Almacena los requerimientos principales del proyecto
CREATE TABLE IF NOT EXISTS requerimientos (
    id SERIAL PRIMARY KEY,
    descripcion TEXT NOT NULL,
    modulo VARCHAR(100) NOT NULL,
    prioridad VARCHAR(20) NOT NULL CHECK (prioridad IN ('Alta', 'Media', 'Baja')),
    estado VARCHAR(50) NOT NULL DEFAULT 'Planificación',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TABLA 2: requerimiento_referencias
-- Almacena referencias a código específico (funciones, IDs, clases) relacionadas con cada requerimiento
CREATE TABLE IF NOT EXISTS requerimiento_referencias (
    id SERIAL PRIMARY KEY,
    requerimiento_id INTEGER NOT NULL REFERENCES requerimientos(id) ON DELETE CASCADE,
    archivo_relacionado VARCHAR(255) NOT NULL,
    seccion_identificador VARCHAR(255) NOT NULL,
    descripcion_referencia TEXT,
    estado VARCHAR(50) NOT NULL DEFAULT 'Pendiente',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TABLA 3: archivos
-- Catálogo de archivos del proyecto para facilitar la selección en el módulo
CREATE TABLE IF NOT EXISTS archivos (
    id SERIAL PRIMARY KEY,
    nombre_archivo VARCHAR(255) NOT NULL UNIQUE,
    descripcion TEXT,
    ruta VARCHAR(500),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_requerimientos_estado ON requerimientos(estado);
CREATE INDEX IF NOT EXISTS idx_requerimientos_prioridad ON requerimientos(prioridad);
CREATE INDEX IF NOT EXISTS idx_requerimientos_modulo ON requerimientos(modulo);
CREATE INDEX IF NOT EXISTS idx_referencias_requerimiento_id ON requerimiento_referencias(requerimiento_id);
CREATE INDEX IF NOT EXISTS idx_referencias_estado ON requerimiento_referencias(estado);
CREATE INDEX IF NOT EXISTS idx_archivos_nombre ON archivos(nombre_archivo);

-- Trigger para actualizar fecha_actualizacion automáticamente
CREATE OR REPLACE FUNCTION update_fecha_actualizacion()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_requerimientos_actualizacion
    BEFORE UPDATE ON requerimientos
    FOR EACH ROW
    EXECUTE FUNCTION update_fecha_actualizacion();

CREATE TRIGGER trigger_referencias_actualizacion
    BEFORE UPDATE ON requerimiento_referencias
    FOR EACH ROW
    EXECUTE FUNCTION update_fecha_actualizacion();

-- Comentarios para documentación
COMMENT ON TABLE requerimientos IS 'Requerimientos del proyecto (features, bugs, mejoras)';
COMMENT ON TABLE requerimiento_referencias IS 'Referencias a código específico relacionado con requerimientos';
COMMENT ON TABLE archivos IS 'Catálogo de archivos del proyecto';

COMMENT ON COLUMN requerimientos.estado IS 'Valores: Planificación, En Progreso, Completado, Bloqueado';
COMMENT ON COLUMN requerimiento_referencias.estado IS 'Valores: Pendiente, En Progreso, Completado';
