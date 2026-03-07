-- ====================================================================
-- MIGRACIÓN 004: AÑADIR VIX Y US30 A ACTIVOS
-- ====================================================================

-- Insertar US30 (Dow Jones) como activo operable
INSERT INTO activos (simbolo, nombre, categoria, estado_operativo, simbolo_broker) 
VALUES ('US30', 'Dow Jones Ind. Ave.', 'INDICES', 'ACTIVO', 'US30_i')
ON CONFLICT (simbolo) DO NOTHING;

-- Insertar VIX (Volality Index) como activo NO operable (solo lectura)
INSERT INTO activos (simbolo, nombre, categoria, estado_operativo, simbolo_broker) 
VALUES ('VIX', 'CBOE Volatility Index', 'INDICES', 'SOLO_LECTURA', 'VIX_i')
ON CONFLICT (simbolo) DO NOTHING;
