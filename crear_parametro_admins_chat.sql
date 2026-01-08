-- Crear parámetro para administradores de chat
-- Este parámetro almacena los IDs de terceros que recibirán notificaciones de pedidos

INSERT INTO parametros_sistema (nombre, valor_texto, tipo, descripcion, fecha_actualizacion)
VALUES (
    'admins_chat_notificaciones',
    '16',
    'texto',
    'IDs de administradores que reciben notificaciones de pedidos (separados por comas)',
    CURRENT_TIMESTAMP
)
ON CONFLICT (nombre) DO UPDATE
SET
    valor_texto = '16',
    tipo = 'texto',
    descripcion = 'IDs de administradores que reciben notificaciones de pedidos (separados por comas)',
    fecha_actualizacion = CURRENT_TIMESTAMP;
