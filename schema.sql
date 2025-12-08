-- Sentencias SQL para crear todas las tablas de la base de datos.
-- Si la tabla existe, la elimina y la recrea para asegurar que la estructura esté limpia.

-- ------------------------------------------------
-- TABLAS PRINCIPALES
-- ------------------------------------------------

DROP TABLE IF EXISTS diagnosticos;
CREATE TABLE diagnosticos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion TEXT NOT NULL UNIQUE,
    -- Campos ATC añadidos para categorizar diagnósticos/usos (opcional)
    codigo_atc TEXT,
    fuente TEXT 
);

DROP TABLE IF EXISTS sintomas;
CREATE TABLE sintomas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion TEXT NOT NULL UNIQUE
);

DROP TABLE IF EXISTS fabricantes;
CREATE TABLE fabricantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE
);

DROP TABLE IF EXISTS medicamentos;
CREATE TABLE medicamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    presentacion TEXT,
    concentracion TEXT,
    imagen TEXT,
    
    -- Campos ATC para clasificación técnica del medicamento
    codigo_atc_puro TEXT,
    descripcion_tecnica_atc TEXT,
    fuente_atc TEXT,
    
    -- Los campos de inventario que usa el código mock
    cantidad_inicial INTEGER,
    existencia INTEGER, -- Este campo es redundante si usamos existencias/movimientos, pero lo mantenemos por compatibilidad.
    activo INTEGER DEFAULT 1 -- 1 para activo, 0 para eliminado lógicamente
);

-- ------------------------------------------------
-- TABLAS DE RELACIÓN (MUCHOS A MUCHOS)
-- ------------------------------------------------

DROP TABLE IF EXISTS diagnostico_sintoma;
CREATE TABLE diagnostico_sintoma (
    diagnostico_id INTEGER NOT NULL,
    sintoma_id INTEGER NOT NULL,
    FOREIGN KEY (diagnostico_id) REFERENCES diagnosticos(id) ON DELETE CASCADE,
    FOREIGN KEY (sintoma_id) REFERENCES sintomas(id) ON DELETE CASCADE,
    PRIMARY KEY (diagnostico_id, sintoma_id)
);

DROP TABLE IF EXISTS diagnostico_medicamento;
CREATE TABLE diagnostico_medicamento (
    diagnostico_id INTEGER NOT NULL,
    medicamento_id INTEGER NOT NULL,
    FOREIGN KEY (diagnostico_id) REFERENCES diagnosticos(id) ON DELETE CASCADE,
    FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id) ON DELETE CASCADE,
    PRIMARY KEY (diagnostico_id, medicamento_id)
);

-- ------------------------------------------------
-- TABLA DE INVENTARIO (EXISTENCIAS/MOVIMIENTOS)
-- ------------------------------------------------

DROP TABLE IF EXISTS movimientos_inventario;
CREATE TABLE movimientos_inventario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicamento_id INTEGER NOT NULL,
    fabricante_id INTEGER NOT NULL, -- El fabricante específico del lote de esta entrada/salida
    tipo_movimiento TEXT NOT NULL,  -- 'ENTRADA', 'SALIDA', 'AJUSTE'
    cantidad INTEGER NOT NULL,
    fecha_movimiento TIMESTAMP NOT NULL,
    FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id) ON DELETE CASCADE,
    FOREIGN KEY (fabricante_id) REFERENCES fabricantes(id) ON DELETE NO ACTION
);

-- Renombramos existencias por compatibilidad con código anterior, pero se recomienda usar movimientos_inventario
DROP TABLE IF EXISTS existencias;
CREATE TABLE existencias AS SELECT * FROM movimientos_inventario WHERE 1=0; -- Crea tabla vacía con la misma estructura.