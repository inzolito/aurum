-- =============================================================================
-- AURUM V14 — Migración de Base de Datos: Security & Intelligence Upgrades
-- Fecha: 2026-03-10
-- Aplicar en GCP PostgreSQL antes de arrancar el bot con V14.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Tabla: autopsias_perdidas (D3 V14 — Autopsia de Pérdidas)
-- Almacena el análisis de Gemini para cada trade perdedor.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS autopsias_perdidas (
    id                  SERIAL PRIMARY KEY,
    ticket_mt5          INTEGER NOT NULL,
    simbolo             VARCHAR(20) NOT NULL,
    pnl_usd             DECIMAL(10, 2),
    tipo_fallo          VARCHAR(20),          -- TECNICO | MACRO | TIMING | RIESGO
    worker_culpable     VARCHAR(50),          -- TrendWorker | NLPWorker | etc.
    descripcion         TEXT,
    correccion_sugerida TEXT,
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_autopsias_simbolo  ON autopsias_perdidas (simbolo);
CREATE INDEX IF NOT EXISTS idx_autopsias_ticket   ON autopsias_perdidas (ticket_mt5);
CREATE INDEX IF NOT EXISTS idx_autopsias_fallo    ON autopsias_perdidas (tipo_fallo);

-- -----------------------------------------------------------------------------
-- 2. Tabla: horarios_operativos — Poblar con ventanas de sesión (D1 V14)
-- Sólo inserta si el activo aún no tiene horarios definidos.
-- Horarios en UTC.
-- -----------------------------------------------------------------------------

-- FOREX: Sesión Londres + NY overlap (07:00–16:00 UTC)
INSERT INTO horarios_operativos (activo_id, hora_apertura, hora_cierre)
SELECT a.id, '07:00:00'::TIME, '16:00:00'::TIME
FROM activos a
WHERE a.categoria = 'FOREX'
AND NOT EXISTS (
    SELECT 1 FROM horarios_operativos h WHERE h.activo_id = a.id
);

-- ÍNDICES US: Sesión Nueva York (14:30–21:00 UTC)
INSERT INTO horarios_operativos (activo_id, hora_apertura, hora_cierre)
SELECT a.id, '14:30:00'::TIME, '21:00:00'::TIME
FROM activos a
WHERE a.categoria = 'INDICES'
AND NOT EXISTS (
    SELECT 1 FROM horarios_operativos h WHERE h.activo_id = a.id
);

-- COMMODITIES: Sesión Europa + US (07:00–20:00 UTC)
INSERT INTO horarios_operativos (activo_id, hora_apertura, hora_cierre)
SELECT a.id, '07:00:00'::TIME, '20:00:00'::TIME
FROM activos a
WHERE a.categoria = 'COMMODITIES'
AND NOT EXISTS (
    SELECT 1 FROM horarios_operativos h WHERE h.activo_id = a.id
);

-- -----------------------------------------------------------------------------
-- 3. Verificación post-migración
-- -----------------------------------------------------------------------------
SELECT 'autopsias_perdidas' AS tabla, COUNT(*) AS filas FROM autopsias_perdidas
UNION ALL
SELECT 'horarios_operativos', COUNT(*) FROM horarios_operativos;
