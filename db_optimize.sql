-- Optimizando Noticias (NLP Insights)
CREATE INDEX IF NOT EXISTS idx_noticias_tiempo ON sentimiento_noticias (tiempo DESC);

-- Optimizando Historial y Autopsias
CREATE INDEX IF NOT EXISTS idx_operaciones_tiempo ON registro_operaciones (tiempo_entrada DESC);
CREATE INDEX IF NOT EXISTS idx_autopsias_ticket ON autopsias_perdidas (ticket_mt5);

-- Optimizando Votos y Pulso de Mercado
CREATE INDEX IF NOT EXISTS idx_senales_tiempo ON registro_senales (tiempo DESC);
CREATE INDEX IF NOT EXISTS idx_senales_activo_tiempo ON registro_senales (activo_id, tiempo DESC);
