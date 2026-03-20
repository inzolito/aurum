---
name: Plan Paper Trading / Modo Simulación
description: Plan para implementar modo paper trading (simulación) en una versión futura
type: project
---

Implementar como módulo independiente. No tocar el motor core.

**Why:** Permite testear nuevos activos (BTC) y estrategias (V18 pullback) sin arriesgar capital real.

**How to apply:** Planificar como versión mayor (V19 o posterior). Requiere diseño cuidadoso antes de codear.

## Arquitectura propuesta

### Nivel 2 — Paper Trading completo

**Nuevo archivo:** `paper_trader.py` — proceso independiente (como news_hunter)

**BD:**
- Nueva tabla `registro_simulaciones` — misma estructura que `registro_operaciones` + columna `motivo_cierre_virtual`
- Flag por activo: `activos.modo_simulacion BOOLEAN DEFAULT false`
- O flag global: `GERENTE.modo_simulacion` en `parametros_sistema`

**Flujo:**
1. Manager detecta señal → si activo tiene `modo_simulacion=true` → NO llama `abrir_orden()` → inserta en `registro_simulaciones`
2. `paper_trader.py` corre loop cada 30s → compara `precio_actual` vs SL/TP virtuales → cierra posición simulada cuando se toca
3. P&L calculado con precio_actual real de MetaAPI
4. Slippage simulado configurable (ej: +0.5 spread al entrar)

**Dashboard:**
- Tab "Simulación" separado con sus propias stats
- Posiciones simuladas en tabla propia (badge "SIM" en lugar de ticket MT5)
- Métricas: win rate simulado, P&L acumulado simulado, comparativa vs real

**Reglas importantes:**
- Kill-switch y risk module NO cuentan posiciones simuladas
- Puede correr real + simulado simultáneamente
- Útil para: BTC, nuevos pares, V18 pullback entry, calibración de parámetros

## Casos de uso
- Activar BTC solo en simulación 2-3 semanas → si números buenos → activar real
- Testear V18 pullback en paralelo con V17 actual → comparar win rate
- Calibrar SL/TP para activos nuevos sin riesgo

## Versión objetivo
V19 o posterior. Primero implementar V18 (pullback entry).
