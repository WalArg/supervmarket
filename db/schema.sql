-- SuperVmarket · Esquema Postgres v2 (Promociones Estructuradas + Historial + Alertas)
-- Compatible con Neon / Supabase / Postgres local.

-- Extensiones: búsqueda fuzzy (trigram) e insensibilidad a acentos
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Catálogo unificado (1 fila por producto real, clave = EAN/código de barras)
CREATE TABLE IF NOT EXISTS productos (
    ean                   TEXT PRIMARY KEY,
    nombre                TEXT NOT NULL,
    marca                 TEXT,
    modelo                TEXT,
    tipo                  TEXT,
    imagen                TEXT,
    supermercado_origen   TEXT,
    categorias            TEXT,
    categoria_normalizada TEXT,
    actualizado           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Precios vigentes: 1 fila por (producto, supermercado). Se actualiza en cada corrida.
CREATE TABLE IF NOT EXISTS precios (
    ean               TEXT NOT NULL REFERENCES productos(ean) ON DELETE CASCADE,
    supermercado      TEXT NOT NULL,
    precio_venta      DOUBLE PRECISION NOT NULL, -- Precio unitario real llevando 1 unidad (todo público)
    precio_lista      DOUBLE PRECISION,
    descuento         DOUBLE PRECISION DEFAULT 0,
    promo_etiqueta    TEXT,                      -- Ej: "2do al 70%", "3x2", "40% Comunidad Coto"
    promo_tipo        TEXT,                      -- 'DIRECT', 'NXM', 'BULK_PCT', 'CLUB_PCT'
    promo_min_qty     INTEGER DEFAULT 1,         -- Cantidad mínima para activar la promo (ej: 2 o 3)
    precio_promo_unit DOUBLE PRECISION,          -- Precio efectivo por unidad cumpliendo condición/club
    requiere_club     BOOLEAN DEFAULT FALSE,     -- TRUE si requiere Club DIA / Mi Carrefour / Comunidad Coto / tarjeta
    precio_por_unidad DOUBLE PRECISION,
    unidad_medida     TEXT,
    stock             INTEGER DEFAULT 0,
    internal_id       TEXT,                      -- SKU/itemId de la tienda (para carrito y simulación)
    link              TEXT,
    fecha             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ean, supermercado)
);

-- Columnas de migración segura por si la tabla precios ya existía en v1
ALTER TABLE precios ADD COLUMN IF NOT EXISTS promo_etiqueta TEXT;
ALTER TABLE precios ADD COLUMN IF NOT EXISTS promo_tipo TEXT;
ALTER TABLE precios ADD COLUMN IF NOT EXISTS promo_min_qty INTEGER DEFAULT 1;
ALTER TABLE precios ADD COLUMN IF NOT EXISTS precio_promo_unit DOUBLE PRECISION;
ALTER TABLE precios ADD COLUMN IF NOT EXISTS requiere_club BOOLEAN DEFAULT FALSE;

-- Historial de precios (append-only cuando varía el precio)
CREATE TABLE IF NOT EXISTS historial_precios (
    id           BIGSERIAL PRIMARY KEY,
    ean          TEXT NOT NULL,
    supermercado TEXT NOT NULL,
    precio_venta DOUBLE PRECISION NOT NULL,
    fecha        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices de búsqueda y joins
CREATE INDEX IF NOT EXISTS idx_productos_nombre_trgm
    ON productos USING gin (lower(unaccent(nombre)) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_precios_ean        ON precios (ean);
CREATE INDEX IF NOT EXISTS idx_precios_ean_stock  ON precios (ean, precio_venta) WHERE stock > 0;
CREATE INDEX IF NOT EXISTS idx_precios_super      ON precios (supermercado);
CREATE INDEX IF NOT EXISTS idx_precios_venta      ON precios (precio_venta);
CREATE INDEX IF NOT EXISTS idx_hist_ean_fecha     ON historial_precios (ean, fecha DESC);
