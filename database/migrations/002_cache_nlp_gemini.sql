-- ================================================================
-- MIGRACIÓN 002: Cache NLP Gemini
-- Aurum Omni V1.0 — NLPWorker con Análisis Dinámico
-- ================================================================

CREATE TABLE IF NOT EXISTS cache_nlp_impactos (
    id             SERIAL PRIMARY KEY,
    hash_regimenes VARCHAR(64) NOT NULL,
    id_activo      SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    simbolo        VARCHAR(10) NOT NULL,
    voto           NUMERIC(4,2) NOT NULL CHECK (voto BETWEEN -1.0 AND 1.0),
    razonamiento   TEXT,
    creado_en      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (hash_regimenes, id_activo)
);

CREATE INDEX IF NOT EXISTS idx_cache_nlp_hash
    ON cache_nlp_impactos (hash_regimenes, creado_en DESC);

-- Verificar
SELECT 'cache_nlp_impactos creada OK' AS resultado;
