-- ====================================================================
-- MIGRACIÓN V18 — Laboratorio de Activos + MacroSensor
-- ====================================================================
-- Versión: V18.0
-- Fecha: 2026-03-20
-- Ejecutar en: psql -h localhost -U aurum_admin -d aurum_db
-- Descripción: Tablas para el módulo Laboratorio (simulación de trades
--   sin capital real) y el MacroSensor (regímenes macro globales).
--
-- Instrucciones SSH:
--   gcloud compute ssh aurum-server --project=aurum-489120 --zone=us-central1-a
--   psql -h localhost -U aurum_admin -d aurum_db -f /opt/aurum/scripts/migrate_v18.sql
-- ====================================================================

BEGIN;

-- 1. Laboratorios — definición de cada modelo
CREATE TABLE IF NOT EXISTS laboratorios (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL,
    categoria       VARCHAR(30),
    estado          VARCHAR(20) DEFAULT 'PAUSADO' CHECK (estado IN ('ACTIVO', 'PAUSADO', 'GRADUADO')),
    capital_virtual NUMERIC(10,2) DEFAULT 3000.00,
    balance_virtual NUMERIC(10,2) DEFAULT 3000.00,
    version_id      INTEGER REFERENCES versiones_sistema(id),
    creado_en       TIMESTAMPTZ DEFAULT NOW(),
    notas           TEXT
);

-- 2. Activos por laboratorio (estado independiente de producción)
CREATE TABLE IF NOT EXISTS lab_activos (
    lab_id    INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    estado    VARCHAR(20) DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'PAUSADO')),
    PRIMARY KEY (lab_id, activo_id)
);

-- 3. Parámetros propios por laboratorio (overrides de parametros_sistema)
CREATE TABLE IF NOT EXISTS lab_parametros (
    lab_id           INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    nombre_parametro VARCHAR(100) NOT NULL,
    valor            VARCHAR(200) NOT NULL,
    descripcion      TEXT,
    PRIMARY KEY (lab_id, nombre_parametro)
);

-- 4. Señales del laboratorio
CREATE TABLE IF NOT EXISTS lab_senales (
    id                   SERIAL PRIMARY KEY,
    lab_id               INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    tiempo               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activo_id            SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    voto_tendencia       NUMERIC(4,3),
    voto_nlp             NUMERIC(4,3),
    voto_sniper          NUMERIC(4,3),
    voto_hurst           NUMERIC(4,3),
    voto_volume          NUMERIC(4,3),
    voto_cross           NUMERIC(4,3),
    voto_final_ponderado NUMERIC(4,3),
    decision_gerente     VARCHAR(30),
    motivo               TEXT,
    umbral_usado         NUMERIC(4,3),
    pesos_usados         JSONB
);
CREATE INDEX IF NOT EXISTS idx_lab_senales_lab_tiempo ON lab_senales (lab_id, tiempo DESC);
CREATE INDEX IF NOT EXISTS idx_lab_senales_tiempo ON lab_senales (tiempo DESC);

-- 5. Operaciones simuladas
CREATE TABLE IF NOT EXISTS lab_operaciones (
    id               SERIAL PRIMARY KEY,
    lab_id           INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    activo_id        SMALLINT REFERENCES activos(id) ON DELETE RESTRICT,
    lab_senal_id     INTEGER REFERENCES lab_senales(id),
    tiempo_entrada   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tipo_orden       VARCHAR(4) CHECK (tipo_orden IN ('BUY', 'SELL')),
    precio_entrada   NUMERIC(10,4) NOT NULL,
    stop_loss        NUMERIC(10,4) NOT NULL,
    take_profit      NUMERIC(10,4) NOT NULL,
    volumen_lotes    NUMERIC(6,2) NOT NULL,
    capital_usado    NUMERIC(15,2),
    estado           VARCHAR(10) DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA', 'CERRADA')),
    tiempo_salida    TIMESTAMPTZ,
    precio_salida    NUMERIC(10,4),
    resultado        VARCHAR(10) CHECK (resultado IN ('TP', 'SL', 'MANUAL')),
    pnl_virtual      NUMERIC(10,2),
    roe_pct          NUMERIC(10,2),
    justificacion_entrada TEXT,
    version_id       INTEGER REFERENCES versiones_sistema(id)
);
CREATE INDEX IF NOT EXISTS idx_lab_ops_lab_estado ON lab_operaciones (lab_id, estado);
CREATE INDEX IF NOT EXISTS idx_lab_ops_tiempo ON lab_operaciones (tiempo_entrada DESC);

-- 6. Snapshots de balance diario por laboratorio
CREATE TABLE IF NOT EXISTS lab_balance_diario (
    id              SERIAL PRIMARY KEY,
    lab_id          INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    balance_inicio  NUMERIC(10,2) NOT NULL,
    balance_cierre  NUMERIC(10,2),
    pnl_dia         NUMERIC(10,2),
    trades_dia      INTEGER DEFAULT 0,
    ganados         INTEGER DEFAULT 0,
    perdidos        INTEGER DEFAULT 0,
    UNIQUE (lab_id, fecha)
);

-- 7. MacroSensor — regímenes macro globales
CREATE TABLE IF NOT EXISTS regimenes_macro (
    id               SERIAL PRIMARY KEY,
    tipo             VARCHAR(30) NOT NULL
                     CHECK (tipo IN ('MONETARIO', 'GEOPOLITICO', 'CORPORATIVO', 'ECONOMICO', 'MERCADO')),
    nombre           VARCHAR(150) NOT NULL,
    fase             VARCHAR(20) DEFAULT 'ACTIVO'
                     CHECK (fase IN ('RUMOR', 'ACTIVO', 'DATOS', 'POST_CLIMAX', 'DISIPADO')),
    direccion        VARCHAR(10) NOT NULL
                     CHECK (direccion IN ('RISK_ON', 'RISK_OFF', 'VOLATIL')),
    peso             NUMERIC(3,2) DEFAULT 0.5 CHECK (peso >= 0 AND peso <= 1),
    activos_afectados TEXT,
    razonamiento     TEXT NOT NULL,
    creado_en        TIMESTAMPTZ DEFAULT NOW(),
    expira_en        TIMESTAMPTZ,
    activo           BOOLEAN DEFAULT TRUE,
    creado_por       VARCHAR(20) DEFAULT 'AUTO' CHECK (creado_por IN ('AUTO', 'MANUAL')),
    fuente_noticia   TEXT,
    noticia_id       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_regimenes_macro_activo ON regimenes_macro (activo) WHERE activo = TRUE;
CREATE INDEX IF NOT EXISTS idx_regimenes_macro_expira ON regimenes_macro (expira_en) WHERE activo = TRUE;

-- Insertar versión V18.0 si no existe
INSERT INTO versiones_sistema (numero_version, descripcion)
VALUES ('V18.0', 'Laboratorio de Activos + MacroSensor')
ON CONFLICT (numero_version) DO NOTHING;

COMMIT;

-- ====================================================================
-- ROLLBACK V18 (ejecutar solo si es necesario revertir)
-- ====================================================================
-- BEGIN;
-- DROP TABLE IF EXISTS regimenes_macro CASCADE;
-- DROP TABLE IF EXISTS lab_balance_diario CASCADE;
-- DROP TABLE IF EXISTS lab_operaciones CASCADE;
-- DROP TABLE IF EXISTS lab_senales CASCADE;
-- DROP TABLE IF EXISTS lab_parametros CASCADE;
-- DROP TABLE IF EXISTS lab_activos CASCADE;
-- DROP TABLE IF EXISTS laboratorios CASCADE;
-- COMMIT;
