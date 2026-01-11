-- Migración: Agregar columnas para sistema de carrito sincronizado
-- Fecha: 2026-01-01
-- Descripción: Agrega columnas precio_unitario, precio_total y estado a la tabla existencias

-- Agregar columna precio_unitario (puede ser NULL para registros antiguos)
ALTER TABLE existencias ADD COLUMN IF NOT EXISTS precio_unitario DECIMAL(10,2);

-- Agregar columna precio_total (puede ser NULL para registros antiguos)
ALTER TABLE existencias ADD COLUMN IF NOT EXISTS precio_total DECIMAL(10,2);

-- Agregar columna estado (NULL = registros antiguos, 'carrito_temporal' = carrito, 'pendiente' = pedido confirmado)
ALTER TABLE existencias ADD COLUMN IF NOT EXISTS estado VARCHAR(20);

-- Crear índice para búsquedas rápidas del carrito
CREATE INDEX IF NOT EXISTS idx_existencias_carrito ON existencias(id_tercero, estado) WHERE estado = 'carrito_temporal';

-- Comentarios
COMMENT ON COLUMN existencias.precio_unitario IS 'Precio unitario del producto al momento de agregar al carrito/pedido';
COMMENT ON COLUMN existencias.precio_total IS 'Precio total (precio_unitario * cantidad)';
COMMENT ON COLUMN existencias.estado IS 'Estado: NULL=compra a proveedor, carrito_temporal=en carrito, pendiente=pedido confirmado';
