# AURUM — PENDIENTES

> [!IMPORTANT]
> **INSTRUCCIÓN PARA EL AGENTE:** Toda tarea de este documento que sea marcada como **COMPLETADA** o cualquier cambio técnico realizado en el código **DEBE** ser documentado inmediatamente en el archivo `docs/HISTORIAL.md`. No se considera terminada una tarea hasta que su bitácora de cambios esté registrada cronológicamente en el historial.

> **Propósito:** Hoja de Ruta Inmediata. Registro de tareas activas, planes detallados de implementación y mejoras próximas. Es el documento de trabajo diario para coordinar los siguientes pasos del desarrollo.

**Última actualización:** 2026-03-15

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