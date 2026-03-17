-- 003_errores_broker.sql
-- Migracion para registrar todos los rechazos del broker MT5

CREATE TABLE IF NOT EXISTS errores_ejecucion (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    simbolo VARCHAR(20) NOT NULL,
    retcode INTEGER NOT NULL,
    mensaje_error TEXT NOT NULL,
    decision_intentada VARCHAR(20) NOT NULL, -- COMPRA o VENTA
    lotes NUMERIC(10,2) NOT NULL,
    contexto_bot TEXT -- Para guardar los Votos o estado interno en el fallo
);
