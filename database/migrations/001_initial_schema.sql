-- ====================================================================
-- MIGRACIÓN 001: ESQUEMA INICIAL DEL SISTEMA AURUM
-- ====================================================================

-- 1. CONTROL DE VERSIONES
-- Mantiene el historial de actualizaciones del software para facilitar Rollbacks.
CREATE TABLE versiones_sistema (
    id SERIAL PRIMARY KEY,
    numero_version VARCHAR(20) UNIQUE NOT NULL,
    descripcion TEXT,
    estado VARCHAR(20) DEFAULT 'ACTIVA',
    fecha_despliegue TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO versiones_sistema (numero_version, descripcion) VALUES 
('v1.0.0', 'Lanzamiento Inicial: Arquitectura Ensemble y Caja de Cristal');

-- 2. ACTIVOS OPERABLES
-- Diccionario de instrumentos financieros y sus estados.
CREATE TABLE activos (
    id SMALLSERIAL PRIMARY KEY,
    simbolo VARCHAR(10) UNIQUE NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    categoria VARCHAR(20),
    estado_operativo VARCHAR(15) DEFAULT 'ACTIVO', -- ACTIVO, PAUSADO, SOLO_CIERRAR
    simbolo_broker VARCHAR(20) -- Nombre exacto del símbolo en el broker (ej: XAUUSD_i)
);

INSERT INTO activos (simbolo, nombre, categoria, simbolo_broker) VALUES
('XAUUSD', 'Oro Spot',     'METALES', 'XAUUSD_i'),
('XAGUSD', 'Plata Spot',  'METALES', 'XAGUSD_i'),
('EURUSD', 'Euro vs Dolar','FOREX',  'EURUSD_i');

-- 3. HORARIOS OPERATIVOS
-- Ventanas de tiempo en las que el bot tiene permitido operar cada activo.
-- Si la tabla está vacía para un activo, se interpreta como sin restricción horaria.
CREATE TABLE horarios_operativos (
    id SERIAL PRIMARY KEY,
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    hora_apertura TIME NOT NULL,
    hora_cierre   TIME NOT NULL,
    zona_horaria  VARCHAR(50) DEFAULT 'UTC'
);

-- 3. REGÍMENES DE MERCADO (Contexto Macroeconómico)
-- Almacena las fuerzas de largo plazo analizadas por el Obrero NLP.
CREATE TABLE regimenes_mercado (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(100) NOT NULL, 
    clasificacion VARCHAR(30), -- REGIMEN_MACRO, CATALIZADOR, CHOQUE
    impacto_base_oro NUMERIC(3, 2) DEFAULT 0.00, 
    impacto_base_usd NUMERIC(3, 2) DEFAULT 0.00, 
    impacto_base_acciones NUMERIC(3, 2) DEFAULT 0.00, 
    fecha_inicio TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_climax TIMESTAMPTZ, 
    estado VARCHAR(20) DEFAULT 'ACTIVO', -- FORMANDOSE, ACTIVO, POST_CLIMAX, DISIPADO
    icono_dashboard VARCHAR(50), 
    color_banner VARCHAR(20)     
);

-- 4. HISTORIAL TÉCNICO (Velas 1M)
-- Memoria técnica del mercado para el Obrero de Tendencia.
CREATE TABLE velas_1m (
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    tiempo TIMESTAMPTZ NOT NULL, 
    apertura NUMERIC(10, 4) NOT NULL, 
    maximo NUMERIC(10, 4) NOT NULL,
    minimo NUMERIC(10, 4) NOT NULL,
    cierre NUMERIC(10, 4) NOT NULL,
    volumen NUMERIC(15, 4) NOT NULL,
    PRIMARY KEY (activo_id, tiempo) 
);

-- 5. AUDITORÍA NLP (Caja de Cristal - Noticias)
-- Registro de titulares analizados y el razonamiento de la IA.
CREATE TABLE sentimiento_noticias (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    activo_id SMALLINT REFERENCES activos(id),
    titular TEXT NOT NULL,
    impacto_nlp NUMERIC(3, 2) NOT NULL, -- Rango -1.0 a 1.0
    fuente VARCHAR(50),
    razonamiento_ia TEXT -- Explicación del porqué de la puntuación
);

-- 6. PANEL DE CONTROL (Parámetros Dinámicos)
-- Permite modificar la estrategia en caliente sin reiniciar el código.
CREATE TABLE parametros_sistema (
    id SERIAL PRIMARY KEY,
    modulo VARCHAR(50) NOT NULL, 
    nombre_parametro VARCHAR(50) UNIQUE NOT NULL, 
    valor NUMERIC(10, 4) NOT NULL, 
    descripcion TEXT
);

INSERT INTO parametros_sistema (modulo, nombre_parametro, valor, descripcion) VALUES
('TENDENCIA',  'TENDENCIA.peso_voto',  0.3000, 'Peso del Obrero de Tendencia en la decision'),
('TENDENCIA',  'TENDENCIA.ema_rapida', 9.0000, 'Periodo de la EMA rapida del Obrero de Tendencia'),
('TENDENCIA',  'TENDENCIA.ema_lenta',  21.0000,'Periodo de la EMA lenta del Obrero de Tendencia'),
('NLP',        'NLP.peso_voto',        0.2000, 'Peso del Obrero NLP en la decision'),
('ORDER_FLOW', 'ORDER_FLOW.peso_voto', 0.5000, 'Peso del Obrero de Flujo en la decision'),
('GERENTE',    'riesgo_trade_pct',     1.5000, 'Porcentaje de capital a arriesgar por operacion'),
('GERENTE',    'umbral_disparo',       0.6500, 'Puntuacion minima ponderada para ejecutar'),
('GERENTE',    'ratio_tp',             2.0000, 'Objetivo de ganancia (TP) vs riesgo (SL)');

-- 7. AUDITORÍA DE DECISIONES (Registro de Señales)
-- Guarda cada evaluación del Gerente, se haya operado o no.
-- Incluye los votos individuales de cada Obrero (Caja de Cristal).
CREATE TABLE registro_senales (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    activo_id SMALLINT REFERENCES activos(id),
    voto_tendencia       NUMERIC(4,3), -- Voto del TrendWorker
    voto_nlp             NUMERIC(4,3), -- Voto del NLPWorker
    voto_order_flow      NUMERIC(4,3), -- Voto del OrderFlowWorker
    voto_final_ponderado NUMERIC(4,3), -- Suma ponderada normalizada
    decision_gerente VARCHAR(30),      -- EJECUTADO, IGNORADO, CANCELADO_RIESGO
    motivo TEXT                        -- Justificación textual Glass Box
);

-- 8. DIARIO DE TRADING (Registro de Operaciones)
-- El corazón de la Caja de Cristal para el Dashboard.
CREATE TABLE registro_operaciones (
    id SERIAL PRIMARY KEY,
    version_id INTEGER REFERENCES versiones_sistema(id),
    activo_id SMALLINT REFERENCES activos(id),
    ticket_mt5 BIGINT UNIQUE,
    tiempo_entrada TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    tipo_orden VARCHAR(4), -- BUY o SELL
    volumen_lotes NUMERIC(6, 2),
    precio_entrada NUMERIC(10, 4),
    stop_loss NUMERIC(10, 4),
    take_profit NUMERIC(10, 4),
    justificacion_entrada TEXT, -- Por qué el bot decidió entrar (texto humano)
    estado VARCHAR(10) DEFAULT 'ABIERTA', -- ABIERTA o CERRADA
    pnl_usd NUMERIC(10, 2)
);

-- 9. ESTADO VIVO (Heartbeat)
-- Reporte en tiempo real de lo que el bot está pensando.
CREATE TABLE estado_bot (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    estado_general VARCHAR(20), -- OPERANDO, ESPERANDO, ERROR
    pensamiento_actual TEXT
);

INSERT INTO estado_bot (estado_general, pensamiento_actual)
VALUES ('APAGADO', 'Sistema inicializado. Esperando arranque.');

-- 10. LOGS DEL SISTEMA
-- Registro de eventos, errores y trazas operativas del bot.
CREATE TABLE log_sistema (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nivel VARCHAR(10) CHECK (nivel IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    modulo VARCHAR(50) NOT NULL,
    mensaje TEXT NOT NULL
);

-- ====================================================================
-- FIN DE MIGRACIÓN 001
-- ====================================================================
