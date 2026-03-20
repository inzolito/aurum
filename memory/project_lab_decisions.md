---
name: Laboratorio — Decisiones de Diseño y Casos Borde
description: Decisiones tomadas sobre casos borde, limitaciones y mejoras del laboratorio. Complementa project_lab_plan.md y project_lab_database.md
type: project
---

## Decisión 1 — Activos en múltiples laboratorios

**Decisión:** Un activo puede pertenecer a múltiples labs simultáneamente, tanto en BD como en código.

**Razonamiento:** XAUUSD puede estar en "Lab Metales" Y en "Lab Refugio" al mismo tiempo. No hay colisión porque el lab no opera real — cada lab simula independientemente con su propio capital virtual y sus propias posiciones en `lab_operaciones`. El resultado de uno no afecta al otro.

**Implementación:**
- BD: `lab_activos` ya permite muchos a muchos — no restringir.
- Código: `_evaluar_laboratorios()` itera todos los labs ACTIVOS que tengan ese activo asignado y evalúa cada uno por separado.
- Futuro: cuando un lab esté GRADUADO y se convierta en bot real con PID propio, AHÍ sí habrá restricción de un motor activo por activo para evitar colisiones reales.

---

## Decisión 2 — Anti-duplicado de posiciones por lab

**Decisión:** Por código, un lab no puede tener más de una posición abierta en el mismo activo simultáneamente. En BD no se restringe (flexible para el futuro).

**Implementación en código:** Antes de simular una entrada, verificar:
```sql
SELECT COUNT(*) FROM lab_operaciones
WHERE lab_id = %s AND activo_id = %s AND estado = 'ABIERTA'
```
Si COUNT > 0 → decision = 'CANCELADO_RIESGO_SIM', motivo = 'Posición ya abierta en este activo'.

---

## Decisión 3 — Simulación de spread (configurable, no hardcodeado)

**Por qué importa:** En el mercado real, comprar cuesta ASK (más alto) y vender entrega BID (más bajo). La diferencia es el spread. Si el lab ignora el spread, sus resultados serán artificialmente mejores que producción real y la comparativa será engañosa.

**Implementación:** Parámetro configurable en `lab_parametros` por lab:
- `LAB.spread_pips` — spread simulado en pips (ej: 3 para EURUSD, 30 para XAUUSD)
- Al simular la entrada: `precio_entrada_real = precio_ask = precio_mid + (spread_pips * punto)`
- Al calcular PnL virtual: se descuenta el spread de entrada y salida

**Por qué configurable:** Cada categoría de activos tiene spread diferente. Un lab de metales necesita spread distinto a uno de forex. El operador define el spread según el broker que usa en producción.

---

## Decisión 4 — Activos independientes por lab (estado propio)

**Decisión:** Cada lab tiene su propio estado por activo en `lab_activos.estado` ('ACTIVO'/'PAUSADO'). Completamente independiente de `activos.estado_operativo` de producción. El lab puede tener XAUUSD=ACTIVO y XAGUSD=PAUSADO sin afectar nada en producción.

**Workers — cómo saben qué evaluar:**
Al inicio de cada ciclo, el motor construye la lista de activos a evaluar como la UNIÓN de producción + todos los labs activos:

```sql
SELECT DISTINCT activo_id FROM (
    SELECT id AS activo_id FROM activos WHERE estado_operativo = 'ACTIVO'
    UNION
    SELECT la.activo_id FROM lab_activos la
    JOIN laboratorios l ON l.id = la.lab_id
    WHERE la.estado = 'ACTIVO' AND l.estado = 'ACTIVO'
) AS todos
```

Workers evalúan cada activo UNA sola vez. Producción toma sus votos, los labs toman los suyos. Sin duplicación, sin complejidad extra.

**Cambio en `lab_activos`:** Agregar columna `estado`:
```sql
ALTER TABLE lab_activos ADD COLUMN estado VARCHAR(20) DEFAULT 'ACTIVO'
CHECK (estado IN ('ACTIVO', 'PAUSADO'));
```

---

## Decisión 5 — Crecimiento de lab_senales (retención de datos)

**Estimación real:** Cada lab trabaja con 3-4 activos por categoría. Con 4 labs × 4 activos × 1440 ciclos/día = ~23,000 filas/día. A ~200 bytes/fila = **~4.6 MB/día**. Con retención 30 días = **~138 MB total**. Completamente manejable.

**Decisión:** Guardar TODAS las señales incluyendo IGNORADO (auditoría completa del modelo). Retención de 30 días — suficiente para auditar cualquier modelo en evaluación.

```sql
-- Job nocturno en news_hunter scheduler (03:00 UTC)
DELETE FROM lab_senales WHERE tiempo < NOW() - INTERVAL '30 days';
```

Las estadísticas históricas (win rate, PnL, drawdown) están pre-calculadas en `lab_balance_diario` — borrar señales antiguas no afecta métricas históricas.

---

## Decisión 6 — MacroSensor: deduplicación de regímenes

**Decisión:** El news_hunter nunca crea dos regímenes del mismo concepto. Antes de insertar, busca si ya existe un régimen activo con nombre similar.

**Implementación:** Al procesar una noticia, Gemini recibe como contexto la lista de regímenes activos actuales y decide:
- ¿Esta noticia crea un régimen NUEVO? → INSERT
- ¿Esta noticia actualiza/intensifica uno EXISTENTE? → UPDATE (fase, peso, razonamiento)
- ¿Esta noticia disipa uno existente? → UPDATE activo=FALSE

Esto garantiza que el concepto "Guerra comercial EEUU-China" es siempre UNA sola fila, no 10.

---

## Decisión 6b — MacroSensor: barra global en el dashboard

**Decisión:** Los regímenes activos aparecen en el HEADER de TODAS las páginas del dashboard como chips de colores. No solo en Config.

**Diseño:**
```
Header: [Monitor] [Config] [Lab]   |  🔴 Guerra comercial  🟡 FOMC mañana  🟢 Fed pausa tasas
```
- Chip 🔴 = RISK_OFF, 🟢 = RISK_ON, 🟡 = VOLATIL
- Hover o clic en el chip → panel con razonamiento completo de Gemini + activos afectados + tiempo de expiración
- Si no hay regímenes activos → barra vacía o "Mercado sin régimen macro relevante"
- Se actualiza cada 15s junto con el polling del Monitor

**Por qué:** El operador necesita saber en TODO momento en qué fase de mercado está operando, sin tener que navegar a Config.

---

## Decisión 7 — Graduación de modelos (fase 1)

**Decisión actual (V18):** Cuando un modelo es rentable, se marca manualmente como `estado = 'GRADUADO'` en la tabla `laboratorios`. El lab deja de simular. El operador analiza los parámetros en `lab_parametros` y los aplica a producción manualmente.

**Decisión futura (cuando se amplíe el servidor):** Cada modelo graduado se convierte en un bot real con su propio proceso (PID), su propio scheduler, y opera con capital real asignado. La infraestructura de múltiples bots se diseña en ese momento.

---

## Decisión 8 — SL/TP configurable por lab

**Decisión:** El lab no hereda ciegamente el ratio TP/SL de producción. Cada lab puede configurar su propio perfil de riesgo.

**Parámetros configurables en `lab_parametros`:**
- `LAB.ratio_tp` — multiplicador TP vs SL (default: 2.0, mismo que producción)
- `LAB.sl_atr_multiplier` — multiplicador ATR para calcular SL (default: 1.5)
- `LAB.riesgo_trade_pct` — % del capital virtual a arriesgar por trade (default: 1.5%)
- `LAB.spread_pips` — spread simulado (default: según activo)

Ejemplo modelo agresivo: `ratio_tp=3.0, sl_atr_multiplier=1.0, riesgo_trade_pct=2.0`
Ejemplo modelo conservador: `ratio_tp=1.5, sl_atr_multiplier=2.0, riesgo_trade_pct=0.5`

---

## Decisión 9 — Métricas completas del laboratorio

**Dashboard del lab — Métricas por modelo:**

### Métricas primarias (siempre visibles)
- **ROE%** — retorno sobre capital (métrica principal, no PnL absoluto)
- **Win Rate** — % trades ganados
- **Profit Factor** — suma ganancias / suma pérdidas (>1.0 = rentable, >1.5 = bueno, >2.0 = excelente)
- **Trades totales** — con badge "Datos insuficientes" si < 30 trades

### Métricas secundarias (panel expandible)
- **Max Drawdown** — mayor caída desde el pico de capital virtual
- **Ganancia promedio** vs **Pérdida promedio** — ratio implícito R:R real
- **Racha ganadora** y **racha perdedora** máximas
- **PnL acumulado** en USD virtual (siempre aclarado como virtual)
- **Curva de capital** — gráfico del balance_virtual a lo largo del tiempo

### Tiempo mínimo para validar un modelo
- < 30 trades → badge amarillo "Datos insuficientes — resultado no confiable"
- 30-100 trades → badge azul "En evaluación"
- > 100 trades → resultado estadísticamente significativo

### Capital inicial estándar
- Todos los labs arrancan con **$3,000 USD virtuales**
- Permite comparación directa entre modelos (mismo punto de partida)
- Período de evaluación: **1 mes completo** para decisión definitiva
- Señal temprana: **1 semana** da buena predicción de la dirección del modelo

---

## Decisión 10 — Impacto en performance con 4-5 labs

**Estimación con 4 labs × 11 activos:**
- 44 evaluaciones adicionales por ciclo de 60s
- Cada evaluación: leer params del cache en memoria + aplicar pesos + comparar umbral + 1-2 inserts en BD
- Tiempo estimado por evaluación: 5-10ms
- **Total extra por ciclo: 220-440ms** sobre un ciclo de 60,000ms
- Impacto: **< 1%** del tiempo del ciclo

**Conclusión:** 4-5 labs es perfectamente viable con Opción B. No requiere threading adicional ni optimización especial. Si en el futuro se superan los 8-10 labs, revisar.

**Monitoreo:** Logear `[LAB] ciclo evaluación: Xms` al finalizar `_evaluar_laboratorios()`. Si supera 2000ms → alerta.

---

## Resumen de parámetros configurables por lab

```
# Evaluación
LAB.umbral_disparo          → umbral propio (override de GERENTE.umbral_disparo)
TENDENCIA.peso_voto         → peso del TrendWorker en este lab
NLP.peso_voto               → peso del NLPWorker en este lab
SNIPER.peso_voto            → peso del SniperWorker en este lab
HURST.peso_voto             → peso del HurstWorker en este lab

# Gestión de riesgo virtual
LAB.ratio_tp                → multiplicador TP vs SL
LAB.sl_atr_multiplier       → multiplicador ATR para SL
LAB.riesgo_trade_pct        → % capital virtual a arriesgar por trade

# Spread simulado
LAB.spread_pips_default     → spread en pips aplicado a TODOS los activos del lab
                               (ej: 20 pips como valor conservador global)
                               Puede refinarse por activo en versiones futuras.
                               Referencia: EURUSD ~2, XAUUSD ~25, US30 ~3

# Filtros
LAB.usar_filtro_correlacion → 1/0 (activar filtro de correlación entre activos)
LAB.max_posiciones_abiertas → máximo simultáneo de posiciones (default: 1 por activo)
```

## Estado
- Decisiones tomadas: 2026-03-20
- Pendiente implementar: todo — estas son las reglas de diseño para la codificación
