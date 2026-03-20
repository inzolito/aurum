# Documento de Migración de Base de Datos

---

## Migración V18 — Laboratorio de Activos + MacroSensor

**Versión:** V18.0
**Fecha:** 2026-03-20
**Ejecutar en:** `psql -h localhost -U aurum_admin -d aurum_db`
**Descripción:** Tablas para el módulo Laboratorio (simulación de trades sin capital real) y el MacroSensor (regímenes macro globales creados por news_hunter/Gemini).

### Diseño
- Tablas `lab_*` completamente aisladas de producción — `registro_operaciones` y `registro_senales` nunca se tocan.
- `lab_activos.estado` es independiente de `activos.estado_operativo` — cada lab controla sus activos sin afectar producción.
- Workers evalúan la UNIÓN de activos de producción + activos de labs activos.
- `regimenes_macro` es tabla nueva — no modifica `regimenes_mercado` existente.

```sql
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
-- Si un parámetro no existe aquí, el lab usa el valor de producción como fallback.
-- Parámetros válidos:
--   LAB.umbral_disparo, TENDENCIA.peso_voto, NLP.peso_voto, SNIPER.peso_voto, HURST.peso_voto
--   LAB.ratio_tp, LAB.sl_atr_multiplier, LAB.riesgo_trade_pct
--   LAB.spread_pips_default, LAB.usar_filtro_correlacion, LAB.max_posiciones_abiertas
CREATE TABLE IF NOT EXISTS lab_parametros (
    lab_id           INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    nombre_parametro VARCHAR(100) NOT NULL,
    valor            VARCHAR(200) NOT NULL,
    descripcion      TEXT,
    PRIMARY KEY (lab_id, nombre_parametro)
);

-- 4. Señales del laboratorio (misma estructura que registro_senales + lab_id)
-- Retención: job nocturno borra filas con tiempo < NOW() - 30 días
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

-- 5. Operaciones simuladas (misma estructura que registro_operaciones, sin ticket_mt5)
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

-- 6. Snapshots de balance diario por laboratorio (para curva de capital en dashboard)
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
-- Creados automáticamente por news_hunter/Gemini al procesar noticias.
-- Gemini decide INSERT (nuevo régimen) / UPDATE (intensificar existente) / DISIPAR.
-- Nunca duplica conceptos — "Guerra comercial" es siempre UNA fila.
-- Expiran automáticamente: job nocturno UPDATE activo=FALSE WHERE expira_en < NOW().
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
    activos_afectados TEXT,   -- JSON: [{"simbolo":"XAUUSD","dir":"UP"},{"simbolo":"USTEC","dir":"DOWN"}]
    razonamiento     TEXT NOT NULL,   -- explicación Gemini visible en dashboard
    creado_en        TIMESTAMPTZ DEFAULT NOW(),
    expira_en        TIMESTAMPTZ,     -- NULL = indefinido (guerras, regímenes largos)
    activo           BOOLEAN DEFAULT TRUE,
    creado_por       VARCHAR(20) DEFAULT 'AUTO' CHECK (creado_por IN ('AUTO', 'MANUAL')),
    fuente_noticia   TEXT,
    noticia_id       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_regimenes_macro_activo ON regimenes_macro (activo) WHERE activo = TRUE;
CREATE INDEX IF NOT EXISTS idx_regimenes_macro_expira ON regimenes_macro (expira_en) WHERE activo = TRUE;

COMMIT;
```

### Rollback V18
```sql
BEGIN;
DROP TABLE IF EXISTS regimenes_macro CASCADE;
DROP TABLE IF EXISTS lab_balance_diario CASCADE;
DROP TABLE IF EXISTS lab_operaciones CASCADE;
DROP TABLE IF EXISTS lab_senales CASCADE;
DROP TABLE IF EXISTS lab_parametros CASCADE;
DROP TABLE IF EXISTS lab_activos CASCADE;
DROP TABLE IF EXISTS laboratorios CASCADE;
COMMIT;
```

---

**Archivo:** `001_initial_schema.sql`
**Versión del Sistema:** v1.0.0 (Lanzamiento Inicial)
**Descripción:** Definición de la estructura core, activos base, parámetros de riesgo y sistema de auditoría "Caja de Cristal".

---

## Script de Migración (SQL)

```sql
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

CREATE TABLE activos (
    id SMALLSERIAL PRIMARY KEY,
    simbolo VARCHAR(10) UNIQUE NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    categoria VARCHAR(20),
    estado_operativo VARCHAR(15) DEFAULT 'ACTIVO', -- ACTIVO, PAUSADO, SOLO_CIERRAR
    simbolo_broker VARCHAR(20) -- Nombre exacto del símbolo en el broker (ej: XAUUSD_i)
);

INSERT INTO activos (simbolo, nombre, categoria, simbolo_broker) VALUES
('XAUUSD', 'Oro Spot',      'METALES', 'XAUUSD_i'),
('XAGUSD', 'Plata Spot',   'METALES', 'XAGUSD_i'),
('EURUSD', 'Euro vs Dolar','FOREX',   'EURUSD_i');


-- 3. HORARIOS OPERATIVOS
-- Ventanas de tiempo permitidas por activo.
-- Si está vacía para un activo = sin restricción horaria.
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

-- Nota: nombre_parametro es UNIQUE. Los pesos de cada Obrero llevan
-- prefijo de módulo para evitar conflictos.
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
```

---

## Datos de Prueba (seed para desarrollo)

Estos registros no pertenecen al schema base — son datos para validar el `NLPWorker` en entorno local. Ejecutar manualmente en desarrollo:

```sql
INSERT INTO regimenes_mercado (titulo, clasificacion, impacto_base_oro, estado)
VALUES
  ('Tensiones Geopoliticas Oriente Medio', 'CHOQUE_GEOPOLITICO', 0.40, 'ACTIVO'),
  ('Expectativa Recorte Tasas FED',        'REGIMEN_MACRO',      0.25, 'FORMANDOSE');
```

**Voto resultante para XAUUSD** con estos datos:

| Régimen | Estado | Impacto aplicado |
|---|---|---|
| Tensiones Geopoliticas Oriente Medio | ACTIVO | `+0.40` |
| Expectativa Recorte Tasas FED | FORMANDOSE | `+0.12` (0.25 × 50%) |
| **Voto final** | | **`+0.53`** |

---

## Notas de Implementación

- **Integridad Referencial:** Se han definido claves foráneas para asegurar que no existan operaciones de activos inexistentes.

- **Tipos de Datos:** Se utiliza `NUMERIC` en lugar de `FLOAT` para evitar errores de precisión decimal en cálculos financieros.

- **Escalabilidad:** El campo `justificacion_entrada` en la tabla 8 y `razonamiento_ia` en la tabla 5 son la base para el Dashboard de "Caja de Cristal".

- **`simbolo_broker`:** Columna añadida en Fase 3.1 para desacoplar el nombre estándar del activo (`XAUUSD`) del nombre exacto que usa el broker en MT5 (ej. `XAUUSD_i` en Weltrade). La traducción se realiza automáticamente vía `db.obtener_simbolo_broker()`.

- **`nombre_parametro` UNIQUE:** La restricción UNIQUE en `parametros_sistema` exige que los parámetros compartidos entre módulos (ej. `peso_voto`) usen prefijo de módulo — `TENDENCIA.peso_voto`, `NLP.peso_voto`, `ORDER_FLOW.peso_voto` — para evitar conflictos.

- **`log_sistema` y `horarios_operativos`:** Tablas creadas en Fase 2/3.1 vía SSH + `ALTER TABLE`. No estaban en el schema simplificado original; ya están incorporadas en `001_initial_schema.sql`.

- **Order Book (Weltrade):** El broker no expone Level 2 vía MT5. El `OrderFlowWorker` retorna voto neutral (`0.0`) en ese caso sin bloquear al Gerente.

- **`registro_senales` — Glass Box completo:** Las columnas `voto_tendencia`, `voto_nlp` y `voto_order_flow` se añadieron en Fase 3.2 para que cada fila sea una radiografía completa de la decisión. El campo `motivo` contiene la justificación textual generada por el Gerente.
