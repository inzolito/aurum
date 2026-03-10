# AURUM — TAREAS PENDIENTES
**Última actualización:** 2026-03-10

---

## ✅ P-1: Script de Administración (`aurum_admin.py`) — COMPLETADO

**Archivo creado:** `aurum_admin.py`

Menú interactivo central para administración diaria:

| Opción | Función |
|--------|---------|
| [1] | 📊 **Tabla de Votos por Obrero** — Live, refresco cada 30s, colores por dirección |
| [2] | 🚦 Estado de Procesos (Core / Hunter / Shield) con RAM y CPU |
| [3] | 🗄️ Estado de Activos — ver y cambiar `ACTIVO / PAUSADO / SOLO_CIERRAR` desde el menú |
| [4] | ⚙️ Parámetros del Sistema — pesos, umbrales, drawdown desde DB |
| [5] | 📰 Últimas Noticias — `raw_news_feed` con nivel de impacto |
| [6] | 🔄 Reiniciar Bot — kill all + relaunch limpio con confirmación |

---

## ✅ P-2: Solucionar duplicados por `start_bot.ps1` — COMPLETADO

**Archivos modificados:** `main.py`, `start_bot.ps1`

- `main.py`: Named Mutex de Windows (`CreateMutexW`) reemplaza la verificación TOCTOU del PID file. La operación es atómica — dos instancias no pueden pasar simultáneamente. El PID file se mantiene como respaldo en plataformas no-Windows.
- `start_bot.ps1`: Reescrito completamente. Ahora verifica el PID file antes de lanzar (no lanza si el proceso sigue vivo), siempre usa el Python del venv, redirige stdout/stderr a `logs/bot.log` y `logs/bot_err.log`.

---

## ✅ P-3: SpreadWorker — COMPLETADO

**Archivo creado:** `workers/worker_spread.py`
**Integrado en:** `core/manager.py`

Compara el spread bid-ask actual contra el spread típico del símbolo (`symbol_info.spread × point`). Clasifica en 5 niveles y aplica un ajuste penalizador al veredicto final:

| Ratio spread actual/típico | Estado | Ajuste |
|---------------------------|--------|--------|
| > 5× | ILIQUIDEZ_EXTREMA | −0.25 |
| > 3× | SPREAD_ALTO | −0.15 |
| > 2× | SPREAD_ELEVADO | −0.08 |
| < 0.5× | SPREAD_COMPRIMIDO | +0.05 |
| Normal | SPREAD_NORMAL | 0.00 |

---

## ✅ P-4: VIXWorker — COMPLETADO

**Archivo creado:** `workers/worker_vix.py`
**Integrado en:** `core/manager.py`

ATR(14) en H4 normalizado contra la media móvil de 50 períodos. Modera la convicción del veredicto según el régimen de volatilidad:

| Ratio ATR actual/media | Nivel | Ajuste |
|------------------------|-------|--------|
| > 3× | EXTREMA | −0.20 |
| > 2× | ALTA | −0.12 |
| > 1.5× | ELEVADA | −0.06 |
| < 0.4× | CALMA | −0.05 |
| Normal | NORMAL | 0.00 |

---

## ✅ P-5: Logging unificado — COMPLETADO (infraestructura)

**Archivo creado:** `config/logging_config.py`
**Integrado en:** `main.py`, `heartbeat.py`, `workers/worker_spread.py`, `workers/worker_vix.py`

- `setup_logging(level)` configura el logger raíz `aurum` con handler de consola + archivo rotativo (`logs/aurum.log`, 10 MB × 5 backups)
- `get_logger(modulo)` retorna `logging.getLogger("aurum.<modulo>")`
- Los módulos existentes (manager.py, workers legacy) siguen usando `print()`. La migración completa es un refactor separado de bajo riesgo.

---

## ✅ P-6: Test suite con pytest — COMPLETADO

**Archivo creado:** `tests/test_workers.py`

Cubre con mocks (sin MT5 ni DB reales):
- `HurstWorker`: estructura del resultado, rango de H, sin datos, sin símbolo broker
- `VolumeWorker`: estructura, fallback sin datos
- `FlowWorker`: fallback de velas cuando no hay Level 2, Level 2 real, sin símbolo broker
- `SpreadWorker`: spread normal, spread alto penaliza, sin datos
- `VIXWorker`: estructura del resultado, sin datos
- `RiskModule`: filtro de seguridad no lanza excepción

**Ejecutar:** `pytest tests/test_workers.py -v`

---

*Todas las tareas completadas. 2026-03-10*
