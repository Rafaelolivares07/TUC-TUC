-- Tabla para solicitudes de servicios de transporte y acompañamiento
-- Compatible con PostgreSQL

CREATE TABLE IF NOT EXISTS solicitudes_transporte (
    id SERIAL PRIMARY KEY,
    tercero_id INTEGER NOT NULL,
    tipo_servicio VARCHAR(20) NOT NULL CHECK (tipo_servicio IN ('transporte', 'acompanamiento')),

    -- Para transporte: origen y destino
    origen_direccion_id INTEGER,
    destino_direccion_id INTEGER,
    origen_texto TEXT,  -- Dirección en texto si no usa terceros_direcciones
    destino_texto TEXT,

    -- Para acompañamiento: horas requeridas
    horas_acompanamiento INTEGER,

    -- Detalles calculados (desde frontend)
    distancia_km NUMERIC(10, 2),
    tiempo_estimado_minutos INTEGER,
    precio NUMERIC(10, 2),

    -- Estado y seguimiento
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'en_curso', 'completada', 'cancelada')),
    fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_servicio TIMESTAMP,  -- Cuándo quiere el servicio (ahora o programado)
    notas TEXT,

    -- Conductor asignado (si aplica - puedes expandir después)
    conductor_id INTEGER,
    fecha_asignacion TIMESTAMP,
    fecha_completado TIMESTAMP,

    -- Auditoría
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (tercero_id) REFERENCES terceros(id) ON DELETE CASCADE,
    FOREIGN KEY (origen_direccion_id) REFERENCES terceros_direcciones(id) ON DELETE SET NULL,
    FOREIGN KEY (destino_direccion_id) REFERENCES terceros_direcciones(id) ON DELETE SET NULL,
    FOREIGN KEY (conductor_id) REFERENCES colaboradores_entrega(id) ON DELETE SET NULL
);

-- Índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_solicitudes_tercero ON solicitudes_transporte(tercero_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado ON solicitudes_transporte(estado);
CREATE INDEX IF NOT EXISTS idx_solicitudes_fecha ON solicitudes_transporte(fecha_solicitud DESC);
CREATE INDEX IF NOT EXISTS idx_solicitudes_conductor ON solicitudes_transporte(conductor_id);

-- Comentarios
COMMENT ON TABLE solicitudes_transporte IS 'Solicitudes de servicios de transporte y acompañamiento tipo Uber/Didi';
COMMENT ON COLUMN solicitudes_transporte.tipo_servicio IS 'Tipo: transporte (punto A a B) o acompanamiento (horas de espera)';
COMMENT ON COLUMN solicitudes_transporte.estado IS 'Estado: pendiente, aceptada, en_curso, completada, cancelada';
