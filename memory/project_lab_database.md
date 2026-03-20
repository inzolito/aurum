---
name: Laboratorio + MacroSensor — Diseño de Base de Datos
description: Esquema SQL completo para el laboratorio de activos (V18) y el MacroSensor. Aislamiento total de producción mediante tablas separadas con estructura idéntica.
type: project
---

## Principio de diseño — Opción C (tablas separadas, estructura idéntica)

Las tablas del laboratorio tienen la **misma estructura** que las de producción más la columna `lab_id`. Las tablas de producción (`registro_senales`, `registro_operaciones`) NUNCA se tocan. Las queries de producción no necesitan ningún filtro extra — cero riesgo de contaminación.

**Regla de oro:** Si una query no referencia explícitamente una tabla `lab_*`, es producción pura.

---

## Bloque 1 — Definición de Laboratorios

```sql
-- Cada fila es un "modelo" de laboratorio con su propia configuración
CREATE TABLE laboratorios (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL,          -- "Modelo Metales Agresivo", "Modelo Índices Conservador"
    categoria       VARCHAR(30),                   -- 'METALES', 'INDICES', 'FOREX', 'ENERGIA', 'MIXTO'
    estado          VARCHAR(20) DEFAULT 'PAUSADO'  -- 'ACTIVO', 'PAUSADO', 'GRADUADO' (promovido a producción)
                    CHECK (estado IN ('ACTIVO', 'PAUSADO', 'GRADUADO')),
    capital_virtual NUMERIC(10,2) DEFAULT 10000.00, -- capital inicial simulado
    balance_virtual NUMERIC(10,2) DEFAULT 10000.00, -- balance actual (se actualiza con cada trade)
    version_id      INTEGER REFERENCES versiones_sistema(id), -- qué versión del bot está corriendo
    creado_en       TIMESTAMPTZ DEFAULT NOW(),
    notas           TEXT                           -- observaciones del operador
);

-- Activos asignados a cada laboratorio (muchos a muchos)
-- estado es INDEPENDIENTE de activos.estado_operativo de producción
-- El lab puede tener XAUUSD=ACTIVO aunque producción lo tenga PAUSADO y viceversa
CREATE TABLE lab_activos (
    lab_id    INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    estado    VARCHAR(20) DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'PAUSADO')),
    PRIMARY KEY (lab_id, activo_id)
);

-- Parámetros propios de cada laboratorio (overrides de parametros_sistema)
-- Si un parámetro no existe aquí, el lab usa el valor de producción como fallback
-- Ejemplos de uso:
--   lab_id=1, nombre_parametro='GERENTE.umbral_disparo', valor='0.40'
--   lab_id=1, nombre_parametro='TENDENCIA.peso_voto', valor='0.70'
--   lab_id=1, nombre_parametro='NLP.peso_voto', valor='0.30'
--   lab_id=1, nombre_parametro='GERENTE.ratio_tp', valor='3.0'
CREATE TABLE lab_parametros (
    lab_id           INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    nombre_parametro VARCHAR(100) NOT NULL,
    valor            VARCHAR(200) NOT NULL,         -- varchar porque puede ser decimal, int o string
    descripcion      TEXT,
    PRIMARY KEY (lab_id, nombre_parametro)
);
```

---

## Bloque 2 — Señales del Laboratorio

Misma estructura que `registro_senales` de producción + `lab_id`. Registra TODAS las evaluaciones del modelo, incluyendo las IGNORADAS — para auditoría completa.

```sql
CREATE TABLE lab_senales (
    id                   SERIAL PRIMARY KEY,
    lab_id               INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    tiempo               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activo_id            SMALLINT REFERENCES activos(id) ON DELETE CASCADE,

    -- Votos de workers (los mismos calculados por producción, reutilizados)
    voto_tendencia       NUMERIC(4,3),
    voto_nlp             NUMERIC(4,3),
    voto_sniper          NUMERIC(4,3),
    voto_hurst           NUMERIC(4,3),
    voto_volume          NUMERIC(4,3),
    voto_cross           NUMERIC(4,3),

    -- Resultado del modelo con SUS parámetros (puede diferir de producción)
    voto_final_ponderado NUMERIC(4,3),
    decision_gerente     VARCHAR(30),               -- EJECUTADO_SIM, IGNORADO, CANCELADO_RIESGO_SIM
    motivo               TEXT,

    -- Parámetros usados en esta evaluación (snapshot para auditoría)
    umbral_usado         NUMERIC(4,3),
    pesos_usados         JSONB                      -- {"trend": 0.70, "nlp": 0.30, "sniper": 0.15}
);
CREATE INDEX idx_lab_senales_lab_tiempo ON lab_senales (lab_id, tiempo DESC);
CREATE INDEX idx_lab_senales_tiempo ON lab_senales (tiempo DESC);
```

---

## Bloque 3 — Operaciones Simuladas del Laboratorio

Misma estructura que `registro_operaciones` de producción + `lab_id`. Sin `ticket_mt5` (no hay orden real). El PnL se calcula virtualmente comparando `precio_salida` vs `precio_entrada` con precio real de mercado.

```sql
CREATE TABLE lab_operaciones (
    id               SERIAL PRIMARY KEY,
    lab_id           INTEGER REFERENCES laboratorios(id) ON DELETE CASCADE,
    activo_id        SMALLINT REFERENCES activos(id) ON DELETE RESTRICT,
    lab_senal_id     INTEGER REFERENCES lab_senales(id),  -- señal que originó el trade

    -- Entrada
    tiempo_entrada   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tipo_orden       VARCHAR(4) CHECK (tipo_orden IN ('BUY', 'SELL')),
    precio_entrada   NUMERIC(10,4) NOT NULL,
    stop_loss        NUMERIC(10,4) NOT NULL,
    take_profit      NUMERIC(10,4) NOT NULL,
    volumen_lotes    NUMERIC(6,2) NOT NULL,
    capital_usado    NUMERIC(15,2),                -- capital virtual comprometido

    -- Salida
    estado           VARCHAR(10) DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA', 'CERRADA')),
    tiempo_salida    TIMESTAMPTZ,
    precio_salida    NUMERIC(10,4),
    resultado        VARCHAR(10) CHECK (resultado IN ('TP', 'SL', 'MANUAL')),

    -- PnL virtual
    pnl_virtual      NUMERIC(10,2),               -- ganancia/pérdida en USD simulado
    roe_pct          NUMERIC(10,2),               -- retorno sobre capital usado

    -- Auditoría
    justificacion_entrada TEXT,                   -- razonamiento del modelo al disparar
    version_id       INTEGER REFERENCES versiones_sistema(id)
);
CREATE INDEX idx_lab_ops_lab_estado ON lab_operaciones (lab_id, estado);
CREATE INDEX idx_lab_ops_tiempo ON lab_operaciones (tiempo_entrada DESC);
```

---

## Bloque 4 — MacroSensor (tabla nueva, reemplaza regimenes_mercado)

La tabla `regimenes_mercado` existente tiene estructura diferente (impacto_base_oro, impacto_base_usd). Se crea `regimenes_macro` como tabla nueva con el diseño del MacroSensor. La antigua no se toca.

```sql
CREATE TABLE regimenes_macro (
    id               SERIAL PRIMARY KEY,

    -- Identidad del régimen
    tipo             VARCHAR(30) NOT NULL
                     CHECK (tipo IN ('MONETARIO', 'GEOPOLITICO', 'CORPORATIVO', 'ECONOMICO', 'MERCADO')),
    nombre           VARCHAR(150) NOT NULL,        -- "Guerra comercial EEUU-China", "NVIDIA Earnings Q1 2026"
    fase             VARCHAR(20) DEFAULT 'ACTIVO'
                     CHECK (fase IN ('RUMOR', 'ACTIVO', 'DATOS', 'POST_CLIMAX', 'DISIPADO')),

    -- Dirección e impacto
    direccion        VARCHAR(10) NOT NULL
                     CHECK (direccion IN ('RISK_ON', 'RISK_OFF', 'VOLATIL')),
    peso             NUMERIC(3,2) DEFAULT 0.5      -- relevancia del régimen (0.0 a 1.0)
                     CHECK (peso >= 0 AND peso <= 1),
    activos_afectados TEXT,                        -- JSON: [{"simbolo":"XAUUSD","dir":"UP"},{"simbolo":"USTEC","dir":"DOWN"}]

    -- Razonamiento de Gemini (el "por qué es relevante")
    razonamiento     TEXT NOT NULL,               -- explicación completa que se muestra en Config

    -- Temporalidad
    creado_en        TIMESTAMPTZ DEFAULT NOW(),
    expira_en        TIMESTAMPTZ,                 -- NULL = indefinido (guerras, regímenes macro largos)
    activo           BOOLEAN DEFAULT TRUE,

    -- Trazabilidad
    creado_por       VARCHAR(20) DEFAULT 'AUTO'   -- 'AUTO' (news_hunter) o 'MANUAL' (operador)
                     CHECK (creado_por IN ('AUTO', 'MANUAL')),
    fuente_noticia   TEXT,                        -- titular o URL de la noticia que lo originó
    noticia_id       INTEGER                      -- referencia a sentimiento_noticias si aplica
);

CREATE INDEX idx_regimenes_macro_activo ON regimenes_macro (activo) WHERE activo = TRUE;
CREATE INDEX idx_regimenes_macro_expira ON regimenes_macro (expira_en) WHERE activo = TRUE;
```

---

## Bloque 5 — Snapshots de Balance por Laboratorio

Para graficar la curva de capital virtual de cada laboratorio en el dashboard, sin recalcular todo el historial.

```sql
CREATE TABLE lab_balance_diario (
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
```

---

## Script de migración completo (ejecutar en GCP)

```sql
-- ============================================================
-- MIGRACIÓN V18 — LABORATORIO + MACROSENSOR
-- Fecha: 2026-03-20
-- Ejecutar en: psql -h localhost -U aurum_admin -d aurum_db
-- ============================================================

BEGIN;

-- 1. Laboratorios
CREATE TABLE IF NOT EXISTS laboratorios (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL,
    categoria       VARCHAR(30),
    estado          VARCHAR(20) DEFAULT 'PAUSADO' CHECK (estado IN ('ACTIVO', 'PAUSADO', 'GRADUADO')),
    capital_virtual NUMERIC(10,2) DEFAULT 10000.00,
    balance_virtual NUMERIC(10,2) DEFAULT 10000.00,
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

-- 3. Parámetros por laboratorio
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

-- 6. Balance diario por laboratorio
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

-- 7. MacroSensor
CREATE TABLE IF NOT EXISTS regimenes_macro (
    id               SERIAL PRIMARY KEY,
    tipo             VARCHAR(30) NOT NULL CHECK (tipo IN ('MONETARIO', 'GEOPOLITICO', 'CORPORATIVO', 'ECONOMICO', 'MERCADO')),
    nombre           VARCHAR(150) NOT NULL,
    fase             VARCHAR(20) DEFAULT 'ACTIVO' CHECK (fase IN ('RUMOR', 'ACTIVO', 'DATOS', 'POST_CLIMAX', 'DISIPADO')),
    direccion        VARCHAR(10) NOT NULL CHECK (direccion IN ('RISK_ON', 'RISK_OFF', 'VOLATIL')),
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

COMMIT;
```

---

## Aislamiento garantizado — resumen

| Tabla producción | Tabla laboratorio | ¿Se tocan? |
|-----------------|-------------------|------------|
| `registro_senales` | `lab_senales` | Nunca |
| `registro_operaciones` | `lab_operaciones` | Nunca |
| `parametros_sistema` | `lab_parametros` | Lab lee producción como fallback, nunca escribe |
| `regimenes_mercado` (antigua) | `regimenes_macro` (nueva) | Nunca |

Las estadísticas de producción (win rate, PnL, autopsia) leen exclusivamente sus tablas. El laboratorio tiene sus propias métricas en sus propias tablas.

## Estado
- Diseñado: 2026-03-20
- Pendiente: ejecutar migración en GCP
- Pendiente: implementar _evaluar_laboratorios() en manager.py
