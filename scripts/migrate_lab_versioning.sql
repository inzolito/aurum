-- Lab Versioning Migration — V18.1
-- Run: sudo -u postgres psql -d aurum_db -f /opt/aurum/scripts/migrate_lab_versioning.sql

ALTER TABLE laboratorios ADD COLUMN IF NOT EXISTS version VARCHAR(20) DEFAULT '1.0.0';

CREATE TABLE IF NOT EXISTS lab_versiones (
    id         SERIAL PRIMARY KEY,
    lab_id     INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    version    VARCHAR(20) NOT NULL,
    parametros JSONB NOT NULL,
    metricas   JSONB,
    notas      TEXT,
    creado_en  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lab_versiones_lab_id ON lab_versiones(lab_id, creado_en DESC);

-- Insertar version inicial para labs existentes
INSERT INTO lab_versiones (lab_id, version, parametros, notas)
SELECT
    l.id,
    '1.0.0',
    COALESCE(
        (SELECT jsonb_object_agg(nombre_parametro, valor)
         FROM lab_parametros WHERE lab_id = l.id),
        '{}'::jsonb
    ),
    'Version inicial — baseline antes del versionado'
FROM laboratorios l;

SELECT id, nombre, version FROM laboratorios;
SELECT lab_id, version, notas, creado_en FROM lab_versiones ORDER BY lab_id;
