# Análisis de Debilidades — V17.2 a V18.1
## Período: 2026-03-13 al 2026-03-27 | 94 trades | 82 cerrados

---

## Resumen Ejecutivo

El sistema opera con un **Win Rate de 33%** sobre un ratio riesgo/recompensa teórico de 2:1.
El punto de equilibrio matemático con RR 2:1 es exactamente 33.3%. El bot está operando
**en el umbral del breakeven pero con PnL negativo** (-$261.11), lo que indica que las pérdidas
tienen SL más grande en promedio que las ganancias tienen TP. El problema no es el R:R ni el
umbral de disparo — es **la calidad de las condiciones en que se entra**, filtradas incorrectamente.

**Diagnóstico central:** El `TrendWorker` en estado `PERSISTENTE` está generando falsas señales
de alta confianza que el sistema acepta sin los filtros correctos. Los trades con Trend fuerte
(≥0.6) tienen peor rendimiento que los de Trend moderado o débil.

---

## 1. El Problema del TrendWorker — Paradoja de Inversión

### Datos

| Rango de voto Trend | Trades | Ganados | Win Rate | PnL |
|---|---|---|---|---|
| Negativo (<0) | 6 | 0 | 0.0% | -$70.84 |
| Débil (0–0.3) | 8 | 4 | **50.0%** | +$27.94 |
| Moderado (0.3–0.6) | 23 | 10 | **43.5%** | +$47.97 |
| **Fuerte (≥0.6)** | **45** | **13** | **28.9%** | **-$234.38** |

### Diagnóstico

El `TrendWorker` con voto alto (0.6–0.8) es el estado más frecuente (55% de los trades) y
el **más destructivo**. Cuando el Trend vota 0.8 — que es el valor que aparece en la
práctica totalidad de los trades perdidos — el sistema interpreta que hay una tendencia
sólida y dispara con alta confianza. Pero ese `0.8` es el **techo del worker**: significa
que la EMA rápida cruzó la lenta con momentum, no que la tendencia esté en fase de inicio.

**El bot está entrando al final de los movimientos, no al principio.**

Un Trend `0.8` fijo en casi todos los trades indica que el worker no está discriminando
fases de la tendencia (inicio vs extensión vs sobrecompra). Un voto moderado (0.3–0.5)
tiene mucho mejor win rate porque suele capturar entradas en consolidaciones tempranas.

### Corrección sugerida

- **Añadir un filtro de "edad de la tendencia"**: si la EMA rápida lleva X velas consecutivas
  por encima de la lenta, reducir el peso del voto Trend en la ponderación (la tendencia es
  vieja, no fresca).
- **Penalizar Trend ≥ 0.75 cuando Hurst = PERSISTENTE** (ver sección 2): combinación
  extremadamente peligrosa.

---

## 2. Hurst PERSISTENTE — El Mayor Destructor de Valor

### Datos

| Estado Hurst | Trades | Ganados | Win Rate | PnL |
|---|---|---|---|---|
| **PERSISTENTE** | **43** | **11** | **25.6%** | **-$292.50** |
| RUIDO | 27 | 10 | 37.0% | -$7.78 |
| **ANTIPERSISTENTE** | **12** | **6** | **50.0%** | **+$70.97** |

### Diagnóstico

El estado `PERSISTENTE` de Hurst (H > 0.5) indica que la serie de precios tiene memoria
a largo plazo — la tendencia tiene inercia. En teoría, es favorable para seguir tendencia.
**En la práctica, el sistema lo está interpretando mal o en el timeframe equivocado.**

Con H persistente se ejecutó el **52% de los trades** (43 de 82) y aportaron **-$292.50 de PnL**,
básicamente la totalidad de las pérdidas. El estado `ANTIPERSISTENTE` (H < 0.5, reversión a la
media) tiene **50% win rate y PnL positivo** con solo 12 trades.

Hipótesis más probable: el Hurst se está calculando sobre velas de 1 minuto. En ese timeframe,
`PERSISTENTE` en Forex intradía significa que el precio ya ha corrido y está en fase de extensión
— exactamente el momento equivocado para entrar a favor de tendencia.

**El sistema actualmente ignora Hurst en la ponderación del veredicto final** (peso_voto=0
o solo penaliza si es RUIDO con -0.15). El estado ANTIPERSISTENTE debería ser una señal
positiva fuerte, no neutral.

### Corrección sugerida

- **Cambiar el tratamiento del HurstWorker:**
  - `ANTIPERSISTENTE`: bonus +0.10 al veredicto (condición de reversión hacia dirección del trade)
  - `RUIDO`: sin cambio (neutro)
  - `PERSISTENTE`: penalizar -0.20 (la tendencia ya corrió, entrada tardía)
- **O alternativamente:** bloquear trades con Hurst PERSISTENTE + Trend ≥ 0.6
  (la peor combinación documentada: 12.5% win rate, -$104.59)

---

## 3. Matriz de Combinaciones de Workers — Las Mejores y Peores

| Combinación | Trades | Ganados | Win Rate | PnL |
|---|---|---|---|---|
| T+ N+ S- H:ANTIPERSISTENTE | 3 | 2 | **66.7%** | +$42.90 |
| T- N+ S+ H:ANTIPERSISTENTE | 6 | 3 | **50.0%** | +$40.74 |
| T- N+ S- H:PERSISTENTE | 5 | 3 | **60.0%** | +$29.66 |
| T- N+ S+ H:RUIDO | 3 | 2 | **66.7%** | +$18.38 |
| T+ N+ S+ H:RUIDO | 19 | 7 | 36.8% | +$6.92 |
| T+ N+ S+ H:ANTIPERSISTENTE | 3 | 1 | 33.3% | -$12.67 |
| T- N+ S+ H:PERSISTENTE | 11 | 3 | 27.3% | -$38.72 |
| T- N- S- H:PERSISTENTE | 3 | 0 | **0.0%** | -$49.13 |
| **T+ N+ S+ H:PERSISTENTE** | **8** | **1** | **12.5%** | **-$104.59** |
| **T+ N+ S- H:PERSISTENTE** | **10** | **2** | **20.0%** | **-$127.28** |

*T = Trend ≥0.5 / N = NLP ≥0.5 / S = Sniper ≥0.5 / H = Hurst*

### Hallazgos clave

1. **La peor combinación documentada: T+ N+ S- con Hurst PERSISTENTE** (10 trades, 20% WR, -$127.28)
   — Trend fuerte + NLP fuerte + Sniper ausente + mercado en extensión. El Sniper está
   señalando que no hay estructura de entrada válida (FVG/OB), pero el sistema dispara igual.

2. **La mejor combinación: NLP dominante con Hurst no-persistente**. Cuando NLP lidera y
   Hurst no es persistente, el win rate es consistentemente > 50%.

3. **T+ N+ S+ con Hurst PERSISTENTE: 12.5% WR** — 8 trades, 1 ganado. Las 3 condiciones
   técnicas se ven "perfectas" pero el Hurst dice que el mercado está sobreextendido. Esta
   combinación debería ser bloqueada completamente.

---

## 4. Fuerza Dominante — El NLP supera al Trend

| Fuerza Dominante | Trades | Ganados | Win Rate | PnL |
|---|---|---|---|---|
| **NLP** | **22** | **9** | **40.9%** | **+$47.34** |
| Sniper | 3 | 1 | 33.3% | -$0.35 |
| **Trend** | **57** | **17** | **29.8%** | **-$276.30** |

### Diagnóstico

El 69% de los trades tienen al `TrendWorker` como fuerza dominante. Cuando NLP domina,
el win rate sube a 40.9% y el PnL es positivo. Cuando Trend domina, el sistema pierde.

Esto confirma que el contexto macroeconómico/fundamental (NLP) es un mejor predictor de
dirección a corto plazo que la señal técnica pura del TrendWorker en las condiciones actuales
del mercado (alta volatilidad macroeconómica, aranceles, FED, geopolítica).

**Los pesos actuales (Trend 40–50%, NLP 40–50%) deberían invertirse o equipararse más
hacia NLP en mercados de alta volatilidad macro.**

---

## 5. Performance por Activo — Activos Rentables vs Destructores

### Activos con pérdidas (ordenado por PnL)

| Activo | Trades | Win Rate | PnL |
|---|---|---|---|
| EURUSD | 11 | 18.2% | -$105.52 |
| NZDUSD | 9 | 11.1% | -$97.36 |
| AUDCAD | 9 | 11.1% | -$89.59 |
| AUDNZD | 7 | 14.3% | -$64.84 |
| US30 | 2 | 0.0% | -$45.35 |
| EURGBP | 1 | 0.0% | -$32.69 |
| USTEC | 1 | 0.0% | -$23.78 |
| GBPJPY | 1 | 0.0% | -$18.48 |
| AUDJPY | 5 | 40.0% | +$1.24 |

### Activos rentables

| Activo | Trades | Win Rate | PnL |
|---|---|---|---|
| USDCAD | 11 | **54.5%** | **+$104.64** |
| USDJPY | 5 | **60.0%** | **+$49.85** |
| EURJPY | 5 | 40.0% | +$39.48 |
| EURCAD | 5 | **60.0%** | **+$35.78** |
| USDCNH | 10 | **60.0%** | **+$17.31** |

### Diagnóstico

**Patrón claro**: los activos con **USD como divisa base** (USDCAD, USDJPY, USDCNH) tienen
consistentemente los mejores resultados. Los activos **cross europeos y del Pacífico** (EURUSD,
NZDUSD, AUDCAD, AUDNZD) están destruyendo valor.

En el período analizado (últimas 2 semanas), el dólar estadounidense fue la fuerza dominante
del mercado (aranceles Trump, expectativas FED hawkish). El NLP captura esto bien, pero el
TrendWorker no sabe distinguir entre una tendencia en EUR/USD que refleja el dólar vs una
que refleja el euro. El sistema opera todos los activos con la misma lógica, sin ponderar
la "moneda motor" del par.

**EURUSD tiene 11 trades con solo 18.2% de win rate** — es el activo que más capital consumió
en pérdidas. Sería el primer candidato para pausar temporalmente o elevar su umbral de disparo.

---

## 6. Tamaño del SL — El Bot Asume Más Riesgo Cuando las Condiciones Son Peores

| Resultado | RR Promedio | SL como % del precio | Trades |
|---|---|---|---|
| GANADO | 2.01 | **0.18%** | 27 |
| PERDIDO | 2.00 | **0.31%** | 55 |

### Diagnóstico

El R:R se cumple correctamente (2:1 en ambos casos). Sin embargo, **los trades perdidos
tienen un SL un 70% más grande en términos relativos al precio**. Esto no es aleatorio:
el bot está entrando con estructuras de mercado más amplias (rangos ATR mayores) cuando
las condiciones son menos favorables, y eso amplifica las pérdidas en términos absolutos.

Los trades ganados tienen SL compactos (0.18%) lo que indica entradas de alta precisión con
estructura clara. Los perdidos entran con SL amplio porque la estructura de soporte/resistencia
es más lejana — señal de entrada en zona "intermedia", no en borde de estructura.

---

## 7. Performance por Hora (Santiago) — Ventanas de Trading

### Horas con PnL positivo

| Hora | Trades | Win Rate | PnL |
|---|---|---|---|
| 02:00 | 2 | 100% | +$36.74 |
| 22:00 | 3 | 66.7% | +$65.39 ⭐ |
| 15:00 | 3 | 66.7% | +$46.59 |
| 06:00 | 3 | 66.7% | +$40.74 |
| 08:00 | 6 | 33.3% | +$21.30 |

### Horas destructivas

| Hora | Trades | Win Rate | PnL |
|---|---|---|---|
| 18:00 | 4 | **0.0%** | -$47.78 |
| 19:00 | 2 | **0.0%** | -$44.23 |
| 17:00 | 5 | 20.0% | -$45.32 |
| 20:00 | 2 | **0.0%** | -$33.69 |
| 01:00 | 3 | **0.0%** | -$48.14 |
| 05:00 | 2 | **0.0%** | -$36.36 |

### Diagnóstico

Las horas 17:00–20:00 Santiago (equivale a 20:00–23:00 UTC / apertura tarde NY y overlap
tarde) son consistentemente las peores: 13 trades, win rate bajísimo, -$125 de PnL.
Esta es la sesión donde los datos económicos de cierre americano y el flujo institucional
generan movimientos erráticos que el TrendWorker interpreta como tendencias pero son
simplemente volatilidad de cierre de sesión.

La hora 22:00 Santiago (madrugada Europa, Asia abriendo) es la mejor: 66.7% WR, +$65.39.
La lógica: apertura Asia tiene momentum direccional limpio que el NLP interpreta bien.

---

## 8. Condición "Filtro de Oro" — Trades que Habrían Sido Exitosos

Combinando los hallazgos anteriores, los trades que pasan todos los filtros óptimos:

**Condición ganadora identificada:**
- NLP ≥ 0.5 (contexto macro alineado)
- Hurst ≠ PERSISTENTE (mercado no sobreextendido)
- Trend moderado o NLP como fuerza dominante
- Horario 02–10 o 22–23 Santiago

**Resultado con ese filtro aplicado retroactivamente:**

Con solo el filtro `Trend < 0.6 + NLP ≥ 0.5 + Hurst ≠ PERSISTENTE`:
→ 28 trades calificados, 11 ganados, **39.3% WR, +$23.56 PnL**

Extrapolando: si se aplicaran todos los filtros óptimos, el universo se reduciría a
~25–30 trades de los 82 cerrados (70% menos señales), pero con WR estimado > 45% y
PnL claramente positivo.

---

## 9. Resumen de Cambios Recomendados

### Cambios de alta prioridad (mayor impacto)

| # | Cambio | Impacto estimado |
|---|---|---|
| 1 | **Bloquear trades con Trend ≥ 0.6 + Hurst PERSISTENTE** | Elimina -$231.87 de pérdidas (18 trades, 16% WR) |
| 2 | **Penalizar Hurst PERSISTENTE en veredicto (-0.15 adicional)** | Reduce entradas tardías en tendencias extendidas |
| 3 | **Elevar umbral de EURUSD, NZDUSD, AUDCAD a 0.60** | Activos con <20% WR necesitan señales más fuertes |
| 4 | **Bloquear nuevas entradas en horario 17–20 Santiago** | -$125 PnL en 13 trades, 0–20% WR consistente |
| 5 | **Rebalancear NLP vs Trend: NLP 55%, Trend 35%** | NLP como fuerza dominante = +40.9% WR vs Trend 29.8% |

### Cambios de mediana prioridad

| # | Cambio | Impacto estimado |
|---|---|---|
| 6 | **Dar bonus +0.10 al veredicto cuando Hurst = ANTIPERSISTENTE** | Solo 12 trades pero 50% WR, deberían ejecutarse más |
| 7 | **Requerir Sniper ≥ 0.5 cuando Hurst = PERSISTENTE** | Obliga estructura clara en condiciones extendidas |
| 8 | **Escalar SL más ajustado (0.8x ATR en vez de 1.0x) para pares AUD/NZD** | Sus SL amplios magnifican pérdidas |

---

## 10. ¿Habrían Funcionado los Trades Perdidos Con Otros Parámetros?

### Análisis de los 10 mayores perdedores

| ID | Activo | PnL | Hurst | Trend | NLP | ¿Por qué falló? | ¿Cómo se habría ganado? |
|---|---|---|---|---|---|---|---|
| 103 | EURGBP | -$32.69 | PERSISTENTE | 0.80 | 0.88 | Tendencia ya extendida, Sniper=0 (sin estructura) | Bloqueado por filtro Hurst PERSISTENTE + Trend≥0.6 |
| 107 | AUDCAD | -$24.18 | PERSISTENTE | 0.80 | 0.60 | Mismo problema. Activo con mal historial | Umbral más alto + filtro Hurst |
| 105 | USTEC | -$23.78 | PERSISTENTE | 0.80 | 0.97 | Entrada en rally extendido de índice | Filtro Hurst. NLP alto pero tendencia vieja |
| 102 | US30 | -$23.69 | PERSISTENTE | 0.80 | 0.98 | Ídem USTEC | Filtro Hurst |
| 164 | EURCAD | -$23.04 | PERSISTENTE | 0.80 | 0.80 | Trend+NLP+Sniper perfectos pero Hurst PERSISTENTE | Bloqueado. Entrar cuando Hurst=RUIDO/ANTI |
| 152 | AUDNZD | -$22.73 | PERSISTENTE | 0.80 | 0.60 | Cross débil + tendencia extendida | Umbral elevado + filtro Hurst |
| 106 | US30 | -$21.66 | PERSISTENTE | 0.80 | 0.96 | 2do trade seguido en mismo activo bajista | Filtro de sesión: no reentrar si activo marcó SL |
| 163 | EURUSD | -$21.42 | PERSISTENTE | 0.80 | 0.80 | EURUSD en tendencia bajista extendida del USD | Activo pausado o umbral 0.60 |
| 161 | EURUSD | -$21.00 | RUIDO | 0.80 | 0.90 | Trend saturado en RUIDO | Requerir Trend ≤ 0.6 cuando Hurst=RUIDO |
| 134 | NZDUSD | -$21.00 | RUIDO | 0.80 | 0.85 | Mismo patrón NZDUSD | Umbral elevado para NZDUSD |

**Conclusión:** El 80% de las pérdidas grandes tienen el mismo ADN: **Trend = 0.80 + Hurst PERSISTENTE**.
Con un solo filtro — bloquear esta combinación — se habría evitado la mayoría del daño.

---

*Generado: 2026-03-27 | Basado en 94 trades del sistema Aurum V17.2–V18.1*
