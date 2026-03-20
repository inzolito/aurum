# AURUM — PENDIENTES

> [!IMPORTANT]
> **INSTRUCCIÓN PARA EL AGENTE:** Toda tarea de este documento que sea marcada como **COMPLETADA** o cualquier cambio técnico realizado en el código **DEBE** ser documentado inmediatamente en el archivo `docs/HISTORIAL.md`. No se considera terminada una tarea hasta que su bitácora de cambios esté registrada cronológicamente en el historial.

> **Propósito:** Hoja de Ruta Inmediata. Registro de tareas activas, planes detallados de implementación y mejoras próximas. Es el documento de trabajo diario para coordinar los siguientes pasos del desarrollo.

**Última actualización:** 2026-03-20

---

## 🔴 MEJORAS ESTRATÉGICAS — CALIDAD DE SEÑAL (2026-03-20)

> **Contexto:** Análisis post-mortem tras 87 trades en producción. Win rate del 27.5%, Profit Factor de 0.20, sesgo COMP del 94%. Los problemas identificados son estratégicos (calidad de señal) no técnicos. Requieren diseño cuidadoso antes de implementar.

---

### MEJORA-01 — Filtro de Correlación entre Activos

**Problema observado:** El bot abrió 5 posiciones en 2 minutos el 20-Mar-2026 (08:08–08:10):
- US30 + US500 + USTEC → los 3 son el mismo mercado USA (correlación >95%)
- EURUSD + GBPUSD → ambos son USD-dependientes (correlación ~85%)

Si el mercado cae en ese momento, los 3 índices caen juntos y las pérdidas se triplican. Es equivalente a operar con 3x el tamaño de posición en un solo activo.

**Solución propuesta:**
Definir grupos de correlación en `parametros_sistema` o en el código. Máximo 1 posición abierta por grupo simultáneamente.

```
Grupo USA_INDICES:  US30, US500, USTEC
Grupo FOREX_USD:    EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF
Grupo METALES:      XAUUSD, XAGUSD
Grupo PETROLEO:     XTIUSD, XBRUSD
Grupo JPY:          USDJPY, GBPJPY, EURJPY, AUDJPY
```

Implementar en `risk_module.py`: antes de abrir una posición, verificar si ya hay una posición abierta en el mismo grupo de correlación. Si la hay → CANCELADO_RIESGO.

**Prioridad:** Alta. Impacto directo en drawdown.

---

### MEJORA-02 — Corrección del Sesgo COMP (Long Bias)

**Problema observado:** De 87 trades totales, **82 son COMP y solo 5 son VENT (94% long)**. El bot casi nunca vende. Si el mercado tiene una tendencia bajista sostenida, el bot pierde sistemáticamente.

**Causas probables a investigar:**
1. `TrendWorker`: las EMAs cortas (EMA9/EMA21) en timeframes M1-M5 en mercados con tendencia macro alcista siempre apuntan arriba aunque haya correcciones.
2. `NLPWorker`: si el feed de noticias tiene sesgo positivo (más noticias bullish que bearish), los scores NLP serán consistentemente positivos.
3. `CrossWorker`: si DXY y SPX están en tendencia alcista, el ajuste Cross puede ser siempre positivo.

**Solución propuesta:**
- Agregar log diario del ratio COMP/VENT en `estado_bot` o en un reporte semanal.
- Revisar si `TrendWorker` puede generar votos negativos con la misma frecuencia que positivos. Analizar distribución histórica de `veredicto_apertura` en `registro_senales`.
- Considerar un umbral de balance: si >70% de los últimos 20 trades son COMP, exigir veredicto más alto (>0.60) para nuevas compras.

**Prioridad:** Alta. Es el factor que más contribuye al win rate bajo.

---

### MEJORA-03 — Ajuste de Risk/Reward (R:R)

**Problema observado:** Estadísticas actuales:
- Ganancia promedio: **+$14.50**
- Pérdida promedio: **-$27.17**
- Ratio R:R implícito: **0.53** (necesitarías 65%+ win rate para break-even; el bot está en 27.5%)

Con R:R < 1, el sistema es matemáticamente negativo salvo que el win rate sea muy alto.

**Causas:** El TP está a ~2× la distancia del SL en la mayoría de trades (correcto), pero el precio no llega al TP antes de regresar al SL. Esto sugiere que las entradas son en momentos de agotamiento de impulso, no de inicio de tendencia.

**Solución propuesta (V18):**
- Entrar en pullbacks a soporte (EMA21, FVG) en lugar de en el punto de máximo impulso. Ya está planificado en `memory/project_v18_plan.md`.
- Evaluar relación TP/SL por activo: si XAUUSD históricamente alcanza el TP antes que el SL el 40% del tiempo, el TP actual está demasiado lejos o el SL demasiado cerca.
- Considerar salida parcial al 50% del recorrido TP (take profit escalonado).

**Prioridad:** Media. Requiere datos históricos para calibrar por activo.

---

### MEJORA-04 — Corrección de Autopsia: FlowWorker Culpable Falso

**Problema observado:** `autopsias_perdidas` acusa a `FlowWorker` en **71% de todos los fallos** (44 de 62). Sin embargo, FlowWorker tiene `peso_voto = 0%` en la fórmula del veredicto — es imposible que sea el responsable de las entradas.

**Causa:** El algoritmo de autopsia en `manager.py` probablemente busca "el worker que más contradice el resultado" o usa algún criterio que no filtra por peso. Está produciendo diagnósticos incorrectos que ocultan los verdaderos responsables (TrendWorker y NLPWorker).

**Solución propuesta:**
- Revisar `auditar_precision_cierres()` en `manager.py`: la lógica de `worker_culpable` debe excluir workers con `peso_voto = 0`.
- El culpable real debería ser el worker con mayor peso que votó en la dirección perdedora.
- Agregar log del voto individual de cada worker al momento del fallo para diagnóstico real.

**Prioridad:** Media. No afecta trading directo pero hace inútil el diagnóstico de fallos.

---

### MEJORA-05 — Ventana de Enfriamiento por Sesión

**Problema observado:** 5 posiciones abiertas en 2 minutos el 20-Mar-2026. Aunque MEJORA-01 limita la correlación, sigue siendo posible abrir muchas posiciones no correlacionadas en un período muy corto ante un evento de mercado.

**Solución propuesta:**
Agregar en `risk_module.py` un límite de máximo N trades por ventana de tiempo:
- Máx. 2 nuevas posiciones por hora (configurable en BD: `GERENTE.max_trades_por_hora`)
- Si se supera → CANCELADO_RIESGO hasta que pase la ventana

**Prioridad:** Baja. La correlación (MEJORA-01) ya mitiga el caso más grave.

---

### MEJORA-06 — FlowWorker: Reemplazar Fallback por Indicador Útil

**Problema observado:** MetaAPI no provee datos de Level 2 (order book). FlowWorker **siempre** usa el fallback de "presión de velas M1 en 4h". Este fallback mide momentum pasado con tick volume (no volumen real), es un indicador rezagado y poco fiable con MetaAPI.

Con peso=0% en el veredicto, FlowWorker actualmente no aporta ni perjudica las entradas, pero contamina el diagnóstico de autopsias y consume recursos en cada ciclo.

**Opciones:**
1. **Desactivar FlowWorker** hasta que tengamos un broker con Level 2 real (OANDA sí lo provee).
2. **Reemplazar el fallback** por un indicador más útil que sí funcione con MetaAPI: CVD (Cumulative Volume Delta) en M5, o simplemente el spread bid/ask como proxy de liquidez.
3. **Subir su peso** solo si se migra a OANDA (que sí provee order book real).

**Prioridad:** Baja. No afecta resultados actuales (peso=0%), pero limpia el código y el diagnóstico.

---

## 🌐 MIGRACIÓN A OANDA REST API v20 (2026-03-15)

> **Contexto:** El broker actual (Weltrade MT5) se reemplazará por OANDA en un servidor Linux. OANDA ofrece una REST API v20 nativa que no requiere MT5 ni Wine, lo que elimina la dependencia de Windows. La lógica de votación, workers y BD no cambia — solo se reemplaza la capa de conexión al broker.
> **Prerequisito bloqueante:** Obtener el **API Token** desde el panel web de OANDA (My Account → Manage API Access). Sin él no se puede arrancar.

---

### ETAPA A — Conector OANDA (`config/oanda_connector.py`)

Crear el archivo `oanda_connector.py` implementando la misma interfaz pública que `mt5_connector.py`. Todos los workers y el manager llaman estos métodos — si la firma es idéntica, nada más cambia.

- [ ] **`obtener_velas(simbolo, cantidad, timeframe)`** — `GET /v3/accounts/{id}/instruments/{instrument}/candles`. Convertir respuesta JSON al mismo DataFrame (`apertura`, `maximo`, `minimo`, `cierre`, `volumen`) que usa el sistema hoy.
- [ ] **`obtener_atr(simbolo, periodo, timeframe)`** — Calcular ATR localmente sobre las velas obtenidas (OANDA no lo devuelve directo).
- [ ] **`obtener_order_book(simbolo)`** — `GET /v3/instruments/{instrument}/orderBook`. Mapear `shortCountPercent`/`longCountPercent` al formato `{bids, asks}` que espera el FlowWorker.
- [ ] **`symbol_info_tick(simbolo)`** — `GET /v3/accounts/{id}/pricing?instruments=`. Devolver objeto con `.ask` y `.bid`.
- [ ] **`symbol_info(simbolo)`** — `GET /v3/instruments/{instrument}`. Devolver objeto con `.spread`, `.point`, `trade_stops_level=0` (OANDA no tiene stop level mínimo fijo).
- [ ] **`positions_get(symbol)`** — `GET /v3/accounts/{id}/positions/{instrument}`. Retornar lista vacía si no hay posición.
- [ ] **`account_info()`** — `GET /v3/accounts/{id}/summary`. Devolver objeto con `.balance`, `.equity`, `.profit`, `.login`.
- [ ] **`enviar_orden(simbolo, direccion, lotes, sl, tp)`** — `POST /v3/accounts/{id}/orders`. Convertir lotes → unidades OANDA (`lotes × tamaño_contrato`). Manejar respuesta y retornar `{status, ticket, retcode}`.
- [ ] **`conectar()` / `desconectar()`** — Verificar token con `GET /v3/accounts/{id}`. Sin estado persistente (REST es stateless).

---

### ETAPA B — Mapa de Símbolos OANDA

OANDA usa formato `XAU_USD` en vez de `XAUUSD`. Crear tabla de traducción en la BD o en variables de entorno.

- [ ] Actualizar columna `simbolo_broker` en tabla `activos` con los nombres OANDA para los 11 activos activos (`XAU_USD`, `XAG_USD`, `BCO_USD`, `WTICO_USD`, `US30_USD`, `SPX500_USD`, `NAS100_USD`, `EUR_USD`, `GBP_USD`, `USD_JPY`, `GBP_JPY`).
- [ ] Verificar cuáles están disponibles en la cuenta OANDA demo antes de activarlos.

---

### ETAPA C — Limpiar llamadas directas a `mt5.*` en el Core

El `manager.py` y `risk_module.py` llaman al módulo `MetaTrader5` directamente en ~15 puntos. Redirigirlos al nuevo conector.

- [ ] `manager.py` — Reemplazar `mt5.positions_get()`, `mt5.symbol_info()`, `mt5.account_info()`, `mt5.symbol_info_tick()`, `mt5.symbol_select()` por llamadas a `self.mt5.*` (el conector inyectado).
- [ ] `risk_module.py` — Mismo patrón: `mt5_lib.positions_get()`, `mt5_lib.account_info()`, `mt5_lib.symbol_info()`, `mt5_lib.symbol_info_tick()`.
- [ ] Eliminar `import MetaTrader5 as mt5` de todos los archivos del core una vez redirigidos.

---

### ETAPA D — Variables de Entorno y Arranque en Linux

- [ ] Nuevas variables de entorno requeridas: `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`, `OANDA_ENV` (`practice` o `live`). Reemplaza `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`.
- [ ] Actualizar `heartbeat.py` — el check de proceso MT5 ya no aplica. Reemplazar por ping al endpoint `/v3/accounts/{id}`.
- [ ] Crear `run_aurum_linux.sh` — script de arranque equivalente al `.bat` actual.
- [ ] Verificar compatibilidad de todas las dependencias Python en Linux (`ta`, `pandas`, `psycopg2`, `python-telegram-bot`, `google-generativeai`). El único que cae es `MetaTrader5` — se elimina del `requirements.txt`.

---

### ETAPA E — Conversión de Lotaje → Unidades OANDA

OANDA no usa lotes. Usa **unidades** por instrumento.

- [ ] Definir tabla de conversión por activo (ej: 1 lote XAU_USD = 100 unidades, 1 lote EUR_USD = 100,000 unidades). Guardar en `parametros_sistema` o en el conector.
- [ ] Actualizar `risk_module.calcular_lotes_dinamicos()` para que devuelva unidades cuando el conector es OANDA, o hacer la conversión en `enviar_orden()`.

---

## 🚀 NUEVOS PENDIENTES (2026-03-12)

- [ ] **Guardado de `version_id` en Trades:** Actualmente el sistema no está guardando con qué versión del bot se realizó cada trade. La columna `version_id` existe en la tabla `registro_operaciones`, pero llega como NULL. Aplicar solución para guardar la versión ACTIVA.
- [ ] **Evitar Ejecuciones Dobles / Caída a Modo Supervivencia:** Interrupciones abruptas dejan procesos del bot ("zombies") corriendo en segundo plano. Esto ocasiona colisiones severas en la API de Telegram y satura el pool de PostgreSQL, provocando que el sistema asuma una caída de BD y dispare el **Modo Supervivencia** (dejando al bot aislado, usando RAM y parámetros hardcodeados). **Contexto de resolución:** Se debe implementar un mecanismo estricto de *Single Instance Lock* (ej. archivo PID, lock SO o registro en BD) en `Main.py` que garantice una única instancia en ejecución y sea capaz de terminar/purgar procesos huérfanos antes de iniciar.

---

## 🔍 SEGUIMIENTO POST-ACTUALIZACIONES 2026-03-11

---

**Fecha de planificación:** 2026-03-11
**Contexto:** Tras aplicar FIX-NLP-02, FIX-VOL-02, FIX-CROSS-02 y los ajustes de TrendWorker (v*0.5 + voto respaldo ±0.20), el PF cayó de 1.95 a 0.05. Los cambios del 11-Mar deberían corregirlo, pero requiere monitoreo.

### Puntos a vigilar mañana

1. **PF del día** — ¿Recuperó la tendencia alcista? Objetivo: PF > 1.20 en las primeras 20 operaciones.

2. **NLP como único motor** — Verificar si el TrendWorker ahora aporta votos en más activos (antes era 0.000 en 9/11). Si el Trend sigue en 0 para la mayoría, el problema es de mercado (EMAs comprimidas) no de código.

3. **Umbral de disparo** — Si NLP sigue siendo el motor principal y el PF no mejora, bajar `NLP.peso_voto` de 0.5 → 0.35 y subir `TENDENCIA.peso_voto` de 0.5 → 0.65 en `parametros_sistema`. Requiere mercado activo para validar.

4. **FlowWorker** — Confirmar que el fix uint64 eliminó los OBI anómalos (`+152,687,139,517,850`). Los logs deben mostrar valores entre -1.0 y +1.0.

5. **CrossWorker (SPXUSD)** — Verificar que el sensor SPXUSD (sin `_i`) devuelve datos reales y que el voto Cross ya no es 0.000 para los índices.

6. **Tabla `votos_detalle`** — Pendiente de implementar para habilitar la autopsia forense completa en el Telegram Daemon (actualmente `justificacion_entrada` existe pero no el detalle por obrero).

### Acción si el PF sigue bajo mañana

```
UPDATE parametros_sistema SET valor = '0.35' WHERE clave = 'NLP.peso_voto';
UPDATE parametros_sistema SET valor = '0.65' WHERE clave = 'TENDENCIA.peso_voto';
```

*Seguimiento planificado el 2026-03-11*