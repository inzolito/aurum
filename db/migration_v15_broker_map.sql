-- ============================================================
-- MIGRACIÓN V15.3 — Remapeo de Símbolos Broker (Weltrade)
-- Fecha: 2026-03-11
-- Propósito: Corregir simbolo_broker para índices americanos y DAX.
--            Los workers recibían DataFrames vacíos porque los nombres
--            no coincidían con los del broker (ej. US30 vs DJIUSD).
--            También pausa activos fantasma no disponibles en Weltrade.
-- ============================================================

-- 1. Corregir índices americanos (Weltrade usa símbolos sin sufijo _i)
UPDATE activos SET simbolo_broker = 'DJIUSD' WHERE simbolo = 'US30';
UPDATE activos SET simbolo_broker = 'SPXUSD' WHERE simbolo = 'US500';
UPDATE activos SET simbolo_broker = 'NDXUSD' WHERE simbolo = 'USTEC';

-- 2. Corregir DAX alemán
UPDATE activos SET simbolo_broker = 'GEREUR' WHERE simbolo = 'GER40';

-- 3. Pausar activos fantasma — no disponibles en Weltrade.
--    Evita ciclos Gemini desperdiciados en símbolos sin datos.
UPDATE activos SET estado_operativo = 'PAUSADO' WHERE simbolo IN ('AUS200', 'JP225', 'UK100', 'FRA40');

-- Verificación post-migración
SELECT simbolo, simbolo_broker, estado_operativo
FROM activos
WHERE simbolo IN ('US30','US500','USTEC','GER40','AUS200','JP225','UK100','FRA40')
ORDER BY simbolo;
