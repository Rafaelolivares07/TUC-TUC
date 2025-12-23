-- Migración para sistema de recordatorios de medicamentos
-- Fecha: 2025-12-23

-- 1. Agregar telegram_chat_id a tabla terceros
ALTER TABLE terceros
ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT;

-- 2. Agregar campos de recordatorio a pastillero_usuarios
ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS horas_entre_tomas INTEGER DEFAULT NULL;

ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS proxima_toma TIMESTAMP DEFAULT NULL;

ALTER TABLE pastillero_usuarios
ADD COLUMN IF NOT EXISTS recordatorio_activo BOOLEAN DEFAULT FALSE;

-- 3. Crear índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_terceros_telegram_chat_id ON terceros(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_pastillero_recordatorio_activo ON pastillero_usuarios(recordatorio_activo);
CREATE INDEX IF NOT EXISTS idx_pastillero_proxima_toma ON pastillero_usuarios(proxima_toma);

-- Comentarios
COMMENT ON COLUMN terceros.telegram_chat_id IS 'Chat ID de Telegram del usuario para enviar recordatorios';
COMMENT ON COLUMN pastillero_usuarios.horas_entre_tomas IS 'Cada cuántas horas debe tomar el medicamento (4, 6, 8, 12, 24)';
COMMENT ON COLUMN pastillero_usuarios.proxima_toma IS 'Fecha y hora de la próxima toma programada';
COMMENT ON COLUMN pastillero_usuarios.recordatorio_activo IS 'Indica si el recordatorio está activo para este medicamento';
