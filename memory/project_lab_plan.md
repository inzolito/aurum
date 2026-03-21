---
name: Plan V18 — Laboratorio de Activos
description: Arquitectura Opcion B completa — implementada en V18.0. Estado actual, flujo, labs creados, pendientes.
type: project
---

## Concepto
Multiples "modelos de laboratorio" que corren en paralelo al bot real, cada uno con su propia
configuracion (categoria, pesos, umbral, SL/TP). Simulan trades virtuales sin tocar capital real.
El bot de produccion nunca se toca.

**Why:** El bot actual tiene una sola configuracion para todos los activos. El laboratorio permite
encontrar la configuracion optima por categoria antes de llevarla a produccion.

---

## Arquitectura — Opcion B (mismo proceso, sin RAM extra) — IMPLEMENTADA

**Decisión clave:** NO se crean procesos ni instancias de workers nuevas. Los workers ya corren en
el ciclo del Manager de produccion y producen sus votos. Los modelos de laboratorio reusan esos
votos ya calculados y los re-evaluan con sus propios parametros.

**Flujo por ciclo:**
1. Workers corren UNA sola vez → producen votos (trend, nlp, sniper, etc.) por activo
2. Manager de produccion evalua esos votos con parametros reales → opera real
3. `lab_evaluator.evaluar_todos(votos_por_activo)` → cada lab aplica sus pesos/umbral → simula trades
4. RAM extra ≈ cero (solo dicts de parametros y queries a BD)

---

## Archivos implementados (V18.0)

| Archivo | Cambio |
|---------|--------|
| `core/lab_evaluator.py` | Nuevo — motor de simulacion de labs |
| `core/manager.py` | Hook a lab_evaluator al final del ciclo + votos en resultado |
| `config/db_connector.py` | 12 metodos nuevos: get_labs_activos, guardar_lab_senal, guardar_lab_operacion, cerrar_lab_operacion, get_lab_operaciones_abiertas, get_regimenes_macro_activos, cleanup_lab_senales, expirar_regimenes_macro, guardar_regimen_macro, actualizar_regimen_macro, get_lab_params, get_activos_para_evaluar |
| `core/scheduler.py` | Limpieza nocturna 03:00 UTC: cleanup_lab_senales + expirar_regimenes_macro |
| `news_hunter.py` | _evaluar_regimen_macro() cuando impacto >= 6 + feeds cripto |
| `dashboard/backend/main.py` | GET /api/lab + PUT /api/lab/{id}/estado |
| `dashboard/frontend/src/pages/Lab.jsx` | Tab Lab con metricas, badges, tabla de operaciones |
| `dashboard/frontend/src/components/MacroBar.jsx` | Barra global header con chips de regimenes |

---

## Tablas en BD (GCP) — creadas

```
laboratorios          — definicion de cada modelo
lab_activos           — activos por lab (con estado independiente de produccion)
lab_parametros        — pesos/umbral/riesgo propios por lab
lab_senales           — todas las evaluaciones del lab (incluyendo IGNORADO)
lab_operaciones       — trades simulados con PnL virtual
lab_balance_diario    — snapshot diario para curva de capital
regimenes_macro       — regimenes macro creados por news_hunter/Gemini
```

---

## Labs creados en BD

### Lab Metales (id=6) — PAUSADO
- Activos: XAUUSD (id=1), XAGUSD (id=2)
- Parametros: umbral 0.45, Trend 0.55, NLP 0.30, Sniper 0.15, ratio_tp 2.5, sl_atr 1.5, spread 30, riesgo 1.5%

### Lab Cripto (id=7) — PAUSADO
- Activos: BTCUSD, ETHUSD (verificar IDs en activos tabla)
- Parametros: umbral 0.55, Trend 0.60, NLP 0.25, Sniper 0.15, ratio_tp 4.0, sl_atr 2.0, spread 80, riesgo 1.0%, filtro_correlacion=1
- Ver razonamiento completo: memory/project_crypto_lab_reasoning.md

### Labs pendientes de crear
- Lab Energía (XTIUSD, XBRUSD)
- Lab Indices (US30, US500, USTEC)
- Lab Forex (EURUSD, GBPUSD, USDJPY, GBPJPY)

---

## Regimenes macro activos en BD

| id | nombre | tipo | dir | peso | expira |
|----|--------|------|-----|------|--------|
| 1  | Guerra Iran | GEOPOLITICO | RISK_OFF | 0.95 | indefinido |
| 2  | Dolar Hegemonico | MERCADO | RISK_OFF | 0.85 | indefinido |
| 3  | Fed Hawkish | MONETARIO | RISK_OFF | 0.80 | indefinido |
| 4  | Aranceles Trump | ECONOMICO | RISK_OFF | 0.75 | indefinido |
| 5  | BTC Ciclo Bear Post-Halving 2025-2026 | MERCADO | RISK_OFF | 0.80 | Oct 2026 |

---

## MacroWorker — PENDIENTE DE DECISIÓN

Ver analisis completo en: memory/project_macro_worker.md

Propuesta: worker pasivo que lee regimenes_macro de BD y devuelve voto persistente por activo.
Para BTC en bear market: voto permanente ~-0.60 a -0.80 antes de cualquier analisis tecnico.
Requiere: nuevo workers/macro_worker.py + columna voto_macro en registro_senales + migracion.

---

## Reglas de aislamiento (inmutables)

- Kill-switch y risk_module de produccion NO cuentan posiciones simuladas
- Tablas lab_* NUNCA tocadas por queries de produccion
- Un activo puede estar en multiples labs (no hay colision — capital virtual es independiente)
- Cuando un modelo gana → parametros se promueven a produccion manualmente

## Estado
- Implementado: 2026-03-20
- Version: V18.0 — commiteada
- Pendiente activar: labs pasan de PAUSADO a ACTIVO cuando se verifique BTCUSD/ETHUSD en MT5
