-- Migración: Tabla para contactos adicionales de recordatorios
-- Fecha: 2025-12-23
-- Propósito: Permitir que usuarios del pastillero agreguen contactos (hijos, cuidadores)
--            que recibirán recordatorios de medicamentos

-- Crear tabla para relacionar usuarios con sus contactos adicionales
CREATE TABLE IF NOT EXISTS pastillero_contactos_adicionales (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
    contacto_id INTEGER NOT NULL REFERENCES terceros(id) ON DELETE CASCADE,
    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(usuario_id, contacto_id)  -- Un contacto no puede estar duplicado para el mismo usuario
);

-- Crear índices para optimizar queries
CREATE INDEX IF NOT EXISTS idx_contactos_adicionales_usuario_id ON pastillero_contactos_adicionales(usuario_id);
CREATE INDEX IF NOT EXISTS idx_contactos_adicionales_contacto_id ON pastillero_contactos_adicionales(contacto_id);

-- Comentarios para documentación
COMMENT ON TABLE pastillero_contactos_adicionales IS 'Relaciona usuarios del pastillero con contactos adicionales (hijos, cuidadores) que recibirán recordatorios';
COMMENT ON COLUMN pastillero_contactos_adicionales.usuario_id IS 'ID del usuario dueño del pastillero (quien toma los medicamentos)';
COMMENT ON COLUMN pastillero_contactos_adicionales.contacto_id IS 'ID del contacto adicional (hijo, cuidador) que recibirá recordatorios';
