# AURUM — HISTORIAL DE CAMBIOS Y MEJORAS

Log cronológico de todo lo resuelto. Las entradas más recientes van arriba.
Para el detalle técnico de cada item ver `AUDIT_REPORT_2026-03-10.md`.

---

## 2026-03-10

### Operaciones en MT5
- **XAUUSD y XAGUSD pausados en DB** (`estado_operativo = 'PAUSADO'`). El bot los ignora desde el siguiente ciclo.
- **Breakeven XAGUSD_i pendiente de aplicar** — mercado cerrado al momento de la solicitud. SL actual: 87.534 | Entrada: 88.272. Aplicar cuando reabra sesión.

### Mejoras implementadas (P-1 a P-6)
- **P-1** `aurum_admin.py` — Panel de administración con menú Rich: tabla de votos Live, estado de procesos, control de activos, parámetros, noticias y reinicio del bot.
- **P-2** Named Mutex de Windows en `main.py` + reescritura de `start_bot.ps1` — elimina race condition que generaba instancias duplicadas.
- **P-3** `workers/worker_spread.py` — SpreadWorker implementado e integrado en Manager. Penaliza veredicto según ratio spread actual/típico.
- **P-4** `workers/worker_vix.py` — VIXWorker implementado e integrado en Manager. Modera convicción según volatilidad ATR/H4 normalizada.
- **P-5** `config/logging_config.py` — Infraestructura de logging unificado. Logger `aurum.*` con archivo rotativo en `logs/aurum.log`. Integrado en `main.py` y `heartbeat.py`.
- **P-6** `tests/test_workers.py` — 17 tests con pytest y mocks. Cubre todos los workers sin requerir MT5 ni DB activos.

### Issues post-auditoría corregidos (N-1 a N-3)
- **N-1** `news_hunter.py` ahora arranca automáticamente con el Core (`main.py`). Tres bare excepts corregidos en el hunter.
- **N-2** FlowWorker con fallback OBI sintético desde presión de velas M1 — ya aporta señal aunque el broker no provea Level 2.
- **N-3** Sistema PID file + cooldown 8 min en heartbeat para evitar loop destructivo de reinicios.

### Auditoría inicial — 26 issues corregidos
- **C-1** Bare exception handlers silenciosos → handlers tipados en 5 archivos.
- **C-2** `cleanup_processes()` mataba procesos del sistema → ahora verifica CWD y cmdline.
- **C-3** Race condition en Survival Mode RAM buffer → `threading.Lock()`.
- **C-4** Blacklist hardcodeada XAUUSD/XAGUSD → control 100% por `estado_operativo` en DB.
- **C-5** Null pointer en precio MT5 → helper `_obtener_precio_seguro()`.
- **C-6** Kill-switch hardcodeado en $1,000 → leído desde `parametros_sistema` en DB.
- **A-1 a A-8** Pesos hardcodeados, timezone erróneo, import dentro de loop, sin validación de input Telegram, umbral de drawdown duplicado, warning si GEMINI_API_KEY vacía, NaN en VolumeWorker, field `data_quality` en HurstWorker.
- **M-2** Thresholds mágicos → constantes de clase `_UMBRAL_*`.
- **M-5** Archivos tmp en repo → `.gitignore` actualizado.
- **B-5/B-6** `news_hunter.py` y `run_news_radar.bat` incorporados al repositorio.
- **B-7** `.env.example` creado con todas las variables documentadas.

### Infraestructura
- Repositorio creado en `https://github.com/inzolito/aurum.git`
- DB GCP reconectada — firewall actualizado a rango `152.174.0.0/16`
- Bot relanzado limpio: 1 instancia Core + 1 News Hunter

---

## Pendiente de aplicar (recordatorio)

| Item | Qué hacer | Cuándo |
|------|-----------|--------|
| Breakeven XAGUSD_i ticket 292354575 | Mover SL a 88.272 | Al reabrir mercado de plata |
