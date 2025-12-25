-- Migración: Sistema de Categorías Parametrizables
-- Fecha: 2025-12-23
-- Propósito: Permitir al admin crear categorías personalizadas con imágenes
--            para organizar productos en la tienda

-- Tabla de categorías
CREATE TABLE IF NOT EXISTS categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    imagen VARCHAR(500),  -- URL de la imagen (Cloudinary)
    orden INTEGER DEFAULT 0,  -- Para ordenar las categorías en el selector
    activo BOOLEAN DEFAULT TRUE,
    es_destacada BOOLEAN DEFAULT FALSE,  -- Marca la categoría que se muestra por defecto
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla intermedia: muchos-a-muchos entre medicamentos y categorías
CREATE TABLE IF NOT EXISTS medicamento_categoria (
    id SERIAL PRIMARY KEY,
    medicamento_id INTEGER NOT NULL,
    categoria_id INTEGER NOT NULL,
    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(medicamento_id, categoria_id)  -- Un medicamento no puede estar duplicado en la misma categoría
);

-- Agregar foreign keys después de crear la tabla
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_medicamento_categoria_medicamento'
    ) THEN
        ALTER TABLE medicamento_categoria
        ADD CONSTRAINT fk_medicamento_categoria_medicamento
        FOREIGN KEY (medicamento_id) REFERENCES "MEDICAMENTOS"(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_medicamento_categoria_categoria'
    ) THEN
        ALTER TABLE medicamento_categoria
        ADD CONSTRAINT fk_medicamento_categoria_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_categorias_activo ON categorias(activo);
CREATE INDEX IF NOT EXISTS idx_categorias_orden ON categorias(orden);
CREATE INDEX IF NOT EXISTS idx_medicamento_categoria_medicamento ON medicamento_categoria(medicamento_id);
CREATE INDEX IF NOT EXISTS idx_medicamento_categoria_categoria ON medicamento_categoria(categoria_id);

-- Comentarios para documentación
COMMENT ON TABLE categorias IS 'Categorías personalizables para organizar productos en la tienda';
COMMENT ON COLUMN categorias.nombre IS 'Nombre de la categoría (ej: "Medicamentos", "Dispositivos Médicos")';
COMMENT ON COLUMN categorias.imagen IS 'URL de la imagen de la categoría en Cloudinary';
COMMENT ON COLUMN categorias.orden IS 'Orden de aparición en el selector horizontal (menor = primero)';
COMMENT ON COLUMN categorias.es_destacada IS 'Si es TRUE, esta categoría se muestra por defecto al cargar la tienda';

COMMENT ON TABLE medicamento_categoria IS 'Relaciona medicamentos con sus categorías (relación muchos-a-muchos)';
