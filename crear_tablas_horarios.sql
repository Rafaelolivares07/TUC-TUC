-- Tablas para gestión de horarios de entrega y festivos
-- Ejecutar este script en PostgreSQL el 1 de enero de 2025

-- Tabla de horarios de entrega
CREATE TABLE IF NOT EXISTS parametros_horarios (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(50) NOT NULL, -- 'lun_sab' o 'dom_festivos'
    hora_apertura_h INTEGER NOT NULL, -- Hora (1-12)
    hora_apertura_m INTEGER NOT NULL DEFAULT 0, -- Minutos (0, 15, 30, 45)
    hora_apertura_ampm VARCHAR(2) NOT NULL, -- 'AM' o 'PM'
    hora_cierre_h INTEGER NOT NULL,
    hora_cierre_m INTEGER NOT NULL DEFAULT 0,
    hora_cierre_ampm VARCHAR(2) NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tipo)
);

-- Tabla de festivos
CREATE TABLE IF NOT EXISTS festivos (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL, -- Ej: "Año Nuevo", "Navidad"
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_fecha_futura CHECK (fecha >= CURRENT_DATE)
);

-- Índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_festivos_fecha ON festivos(fecha);
CREATE INDEX IF NOT EXISTS idx_festivos_activo ON festivos(activo);

-- Insertar horarios por defecto
INSERT INTO parametros_horarios (tipo, hora_apertura_h, hora_apertura_m, hora_apertura_ampm, hora_cierre_h, hora_cierre_m, hora_cierre_ampm)
VALUES
    ('lun_sab', 7, 0, 'AM', 12, 0, 'AM'), -- Lunes a Sábado: 7:00 AM - 12:00 AM
    ('dom_festivos', 10, 0, 'AM', 2, 0, 'PM') -- Domingos y Festivos: 10:00 AM - 2:00 PM
ON CONFLICT (tipo) DO NOTHING;

-- Insertar algunos festivos de ejemplo para 2025
INSERT INTO festivos (fecha, nombre)
VALUES
    ('2025-01-01', 'Año Nuevo'),
    ('2025-01-06', 'Día de los Reyes Magos'),
    ('2025-03-24', 'Día de San José'),
    ('2025-04-17', 'Jueves Santo'),
    ('2025-04-18', 'Viernes Santo'),
    ('2025-05-01', 'Día del Trabajo'),
    ('2025-06-23', 'Sagrado Corazón'),
    ('2025-06-30', 'San Pedro y San Pablo'),
    ('2025-07-20', 'Día de la Independencia'),
    ('2025-08-07', 'Batalla de Boyacá'),
    ('2025-08-18', 'Asunción de la Virgen'),
    ('2025-10-13', 'Día de la Raza'),
    ('2025-11-03', 'Todos los Santos'),
    ('2025-11-17', 'Independencia de Cartagena'),
    ('2025-12-08', 'Inmaculada Concepción'),
    ('2025-12-25', 'Navidad')
ON CONFLICT (fecha) DO NOTHING;

COMMENT ON TABLE parametros_horarios IS 'Horarios de entrega de la tienda (Lun-Sáb y Dom-Festivos)';
COMMENT ON TABLE festivos IS 'Lista de días festivos donde aplica horario especial';

-- Tabla de parámetros del sistema (generales)
CREATE TABLE IF NOT EXISTS parametros_sistema (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    seccion VARCHAR(100) NOT NULL, -- Ej: 'HORARIOS DE ENTREGA', 'POLITICAS DE PRECIOS'
    descripcion TEXT,
    valor_numerico DECIMAL(10,2),
    valor_texto TEXT,
    valor_booleano BOOLEAN,
    tipo VARCHAR(20) NOT NULL, -- 'numerico', 'texto', 'booleano'
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para búsquedas rápidas por nombre
CREATE INDEX IF NOT EXISTS idx_parametros_nombre ON parametros_sistema(nombre);
CREATE INDEX IF NOT EXISTS idx_parametros_seccion ON parametros_sistema(seccion);

-- Insertar parámetro de diferencia máxima en cotizaciones
INSERT INTO parametros_sistema (nombre, seccion, descripcion, valor_numerico, tipo)
VALUES (
    'diferencia_maxima_cotizaciones',
    'POLITICAS DE PRECIOS',
    'Porcentaje máximo de diferencia RAZONABLE entre una nueva cotización y las existentes antes de mostrar alerta',
    30,
    'numerico'
) ON CONFLICT (nombre) DO NOTHING;

COMMENT ON TABLE parametros_sistema IS 'Parámetros configurables del sistema organizados por secciones';
