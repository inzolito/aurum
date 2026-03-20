---
name: Plan V18 — Laboratorio de Activos
description: Plan detallado del módulo Laboratorio — múltiples modelos de simulación con parámetros propios, corriendo dentro del mismo proceso sin RAM extra
type: project
---

## Concepto
Múltiples "modelos de laboratorio" que corren en paralelo al bot real, cada uno con su propia configuración (categoría, pesos, umbral, SL/TP). Simulan trades virtuales sin tocar capital real. El bot de producción nunca se toca.

**Why:** El bot actual tiene una sola configuración para todos los activos. El laboratorio permite encontrar la configuración óptima por categoría (metales, índices, forex) antes de llevarla a producción.

**How to apply:** Al implementar, nunca modificar manager.py ni risk_module.py del core. El lab es completamente paralelo.

---

## Arquitectura — Opción B (mismo proceso, sin RAM extra)

**Decisión clave:** NO se crean procesos ni instancias de workers nuevas. Los workers ya corren en el ciclo del Manager de producción y producen sus votos. Los modelos de laboratorio reusan esos votos ya calculados y los re-evalúan con sus propios parámetros.

**Flujo por ciclo:**
1. Workers corren UNA sola vez → producen votos (trend, nlp, sniper, etc.) por activo
2. Manager de producción evalúa esos votos con parámetros reales → opera real
3. Modelos de laboratorio toman los MISMOS votos ya calculados → cada modelo aplica sus propios pesos/umbral → decide si simular trade → guarda en lab_operaciones
4. RAM extra ≈ cero (solo dicts de parámetros y queries a BD)

---

## Nuevas Tablas en BD

```sql
-- Definición de cada modelo de laboratorio
CREATE TABLE laboratorios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    categoria VARCHAR(50),           -- 'METALES', 'INDICES', 'FOREX', etc.
    estado VARCHAR(20) DEFAULT 'PAUSADO',  -- ACTIVO, PAUSADO
    capital_virtual DECIMAL(10,2) DEFAULT 10000.00,
    balance_virtual DECIMAL(10,2) DEFAULT 10000.00,
    creado_en TIMESTAMP DEFAULT NOW(),
    notas TEXT
);

-- Activos asignados a cada laboratorio (muchos a muchos)
CREATE TABLE lab_activos (
    lab_id INTEGER REFERENCES laboratorios(id),
    activo_id INTEGER REFERENCES activos(id),
    PRIMARY KEY (lab_id, activo_id)
);

-- Parámetros propios por laboratorio (overrides de parametros_sistema)
-- Ej: GERENTE.umbral_disparo=0.40, TENDENCIA.peso_voto=0.70
CREATE TABLE lab_parametros (
    lab_id INTEGER REFERENCES laboratorios(id),
    nombre_parametro VARCHAR(100),
    valor VARCHAR(200),
    PRIMARY KEY (lab_id, nombre_parametro)
);

-- Operaciones simuladas (equivalente a registro_operaciones pero virtual)
CREATE TABLE lab_operaciones (
    id SERIAL PRIMARY KEY,
    lab_id INTEGER REFERENCES laboratorios(id),
    activo_id INTEGER REFERENCES activos(id),
    tiempo_apertura TIMESTAMP,
    tiempo_cierre TIMESTAMP,
    tipo VARCHAR(10),                -- BUY, SELL
    precio_entrada DECIMAL(12,5),
    precio_cierre DECIMAL(12,5),
    sl DECIMAL(12,5),
    tp DECIMAL(12,5),
    lotes DECIMAL(6,2),
    pnl_virtual DECIMAL(10,2),
    resultado VARCHAR(20),           -- TP, SL, MANUAL
    motivo_entrada TEXT
);

-- Señales evaluadas por cada laboratorio
CREATE TABLE lab_senales (
    id SERIAL PRIMARY KEY,
    lab_id INTEGER REFERENCES laboratorios(id),
    activo_id INTEGER REFERENCES activos(id),
    tiempo TIMESTAMP DEFAULT NOW(),
    decision VARCHAR(50),
    voto_final_ponderado DECIMAL(6,4),
    voto_tendencia DECIMAL(6,4),
    voto_nlp DECIMAL(6,4),
    voto_sniper DECIMAL(6,4),
    motivo TEXT
);
```

---

## Implementación

**NO se crean archivos nuevos de workers.** El lab se integra en el ciclo del Manager existente.

**Cambio en manager.py (mínimo):**
- Al final de cada ciclo, después de evaluar producción, llamar `_evaluar_laboratorios(votos_por_activo)`
- `_evaluar_laboratorios` lee laboratorios ACTIVOS de BD, para cada uno que tenga ese activo asignado, aplica sus parámetros propios a los votos ya calculados y simula el trade

**Cierre de posiciones virtuales:**
- En `gestionar_posiciones_abiertas()` del Manager, agregar sección que revisa `lab_operaciones` abiertas y las cierra cuando precio_actual toca SL o TP virtual

---

## Dashboard — Tab "Laboratorio"

- Lista de modelos con estado (ACTIVO/PAUSADO), toggle on/off
- Por modelo: win rate virtual, PnL acumulado, trades simulados
- Tabla de operaciones simuladas recientes (badge "SIM" en lugar de ticket MT5)
- Comparativa entre modelos y vs producción real

---

## Reglas importantes
- Kill-switch y risk_module de producción NO cuentan posiciones simuladas
- Un activo puede estar en múltiples laboratorios simultáneamente (no hay colisión porque no operan real)
- Cuando un modelo encuentra configuración ganadora → se promueve a producción manualmente

## Estado
- Planificado: 2026-03-20
- Versión: V18.0
- A implementar: próxima sesión de desarrollo
