# AURUM — Issues Conocidos del Bot

Lista técnica de bugs y problemas identificados. Ordenados por criticidad.

---

## 🔴 CRÍTICOS

### ISS-001 — Loop de instancias duplicadas infinito (RESUELTO)
**Síntoma:** El bot entraba en loop de restarts enviando cientos de alertas "instancia duplicada" a Telegram. Reiniciar el servicio no lo cortaba.
**Causa raíz (3 bugs encadenados):**
1. `heartbeat.py` usaba `aurum_core.pid` para detectar si el core estaba vivo. `main.py` ya no escribía ese archivo (migrado a fcntl.flock), así que heartbeat siempre creía que el core estaba muerto y lo relanzaba — mientras systemd también lo relanzaba. Ambos competían.
2. `open(_LOCK_FILE, 'w')` en `main.py` truncaba el archivo de lock **antes** de intentar adquirir el flock. Cada proceso nuevo borraba el PID del anterior antes de fallar, dejando el archivo vacío.
3. `cleanup_ghost_processes()` en heartbeat clasificaba `dashboard/backend/main.py` como proceso "core" (contiene "main.py" en el cmdline) → veía 2 instancias → mataba la real cada 2 minutos (ciclo del SHIELD).
**Fix aplicado:**
- `heartbeat.py`: `get_core_pid_from_file()` reemplazado por `_core_tiene_lock()` (intenta adquirir fcntl.flock en modo no-bloqueante — si falla, el core está vivo).
- `core_vivo = len(procesos["core"]) > 0 or _core_tiene_lock()` — psutil Y flock deben coincidir en "muerto" antes de reiniciar.
- Guard extra antes del Popen: `if not core_vivo and not _core_tiene_lock()`.
- `main.py`: `open(_LOCK_FILE, 'a')` en vez de `'w'` — no trunca el archivo en la carrera.
- Detección de core excluye paths con `"dashboard"`: `and "dashboard" not in cmd_str`.

### ISS-002 — Kill-switch hardcodeado en $1,000
**Síntoma:** Si el balance cae a $1,000 el bot se detiene, sin importar configuración.
**Causa:** Valor hardcodeado en `core/risk_module.py`, no lee de BD.
**Impacto:** No configurable sin tocar código. Si el capital crece o cambia, el umbral queda mal.

### ISS-003 — Null pointer en Manager.evaluar() sobre ['ask']
**Síntoma:** Posible crash silencioso al intentar abrir posición si el tick es None.
**Causa:** Se accede a `tick['ask']` sin verificar que `tick` no sea None.
**Impacto:** Orden nunca ejecutada, sin log de error claro.

---

## 🟡 IMPORTANTES

### ISS-004 — SL/TP no se sincronizaban en registro_operaciones (RESUELTO)
**Síntoma:** La barra de precio en el dashboard mostraba el SL original aunque el bot ya lo había movido a breakeven.
**Causa:** `registro_operaciones.sl` y `.tp` solo se escribían al abrir la posición.
**Fix aplicado:** Ahora se actualizan junto con `precio_actual` en cada ciclo.

### ISS-005 — precio_actual NULL en posiciones en breakeven (RESUELTO)
**Síntoma:** La barra de precio no se pintaba en el dashboard.
**Causa:** El update de `precio_actual` estaba después del `continue` del guard de breakeven. Las posiciones ya en BE eran saltadas antes del UPDATE.
**Fix aplicado:** Movido antes del guard.

### ISS-006 — pnl_flotante siempre 0 (RESUELTO)
**Síntoma:** El dashboard mostraba PnL flotante = 0 siempre.
**Causa:** `estado_bot.pnl_flotante` nunca es escrito por el bot. Se leía ese campo.
**Fix aplicado:** `pnl_flotante = equity - balance` calculado en el backend.

### ISS-007 — Pesos del ensemble hardcodeados en manager.py
**Síntoma:** La tabla `parametros_sistema` tiene pesos configurables pero el Manager los ignora.
**Causa:** Pesos definidos como constantes en el código: `Trend*0.50 + NLP*0.50 + Sniper*0.15`.
**Impacto:** Cambios de pesos en BD no tienen efecto sin redesplegar.

### ISS-008 — Noticias relevantes nunca clasificadas (RESUELTO)
**Síntoma:** El filtro "Relevantes" mostraba 0 noticias aunque habían con Impacto 8/10 y 9/10.
**Causa:** `int("8/10")` lanza ValueError. Se necesitaba `int("8/10".split("/")[0])`.
**Fix aplicado:** Parsing corregido.

### ISS-009 — symbol_info_tick() no confiable en MetaAPI
**Síntoma:** Precio actual puede ser None aunque la posición esté abierta.
**Causa:** MetaAPI no siempre retorna tick data vía `symbol_info_tick()`.
**Fix aplicado:** Se usa `pos.price_current` (nativo MetaAPI) como fuente primaria con fallback a tick.
**Pendiente:** Validar que `price_current` siempre esté disponible en el objeto de posición de MetaAPI.

---

## 🟠 ESTABILIDAD

### ISS-010 — Survival Mode sin locks de threading
**Síntoma:** Race condition posible en el RAM buffer cuando DB está caída.
**Causa:** El buffer en memoria no usa `threading.Lock()`.
**Impacto:** Posible corrupción de datos en modo supervivencia bajo carga concurrente.

### ISS-011 — cleanup_processes() en aurum_cli.py mata todos los Python del sistema
**Síntoma:** Al ejecutar cleanup, se matan procesos Python no relacionados con Aurum.
**Causa:** La función hace `pkill python` o similar sin filtrar por nombre/PID específico.
**Impacto:** Puede matar procesos del sistema operativo o de otras apps.

### ISS-012 — PID file zombie bloquea reinicios limpios (RESUELTO)
**Síntoma:** Si el proceso moría abruptamente (SIGKILL), el PID file quedaba y bloqueaba el siguiente arranque.
**Causa:** `psutil.pid_exists()` puede retornar True para PIDs reutilizados por el OS.
**Fix aplicado:** `main.py` usa `fcntl.flock(LOCK_EX|LOCK_NB)` — el OS libera el lock automáticamente al morir el proceso, incluso con SIGKILL. Se eliminaron `_escribir_pid()`, `_borrar_pid()` y `_verificar_instancia_duplicada()`. Ver también ISS-001.

---

## 🔵 MENORES / TÉCNICOS

### ISS-013 — Workers VIX y Spread declarados en ontología pero no existen
**Síntoma:** AURUM_ARCHITECTURE.md menciona VIXWorker y SpreadWorker como workers activos.
**Causa:** Documentación desactualizada. Los workers nunca fueron implementados.

### ISS-014 — Cache MT5 de 30s (RESUELTO)
**Síntoma:** Balance/equity en dashboard tardaba hasta 30s en refrescarse.
**Fix aplicado:** TTL reducido a 5s. Dato real cambia cada ~60s (ciclo del bot).

### ISS-015 — Versiones del sistema todas en estado INACTIVA (RESUELTO)
**Síntoma:** Columna "versión" vacía en historial de trades.
**Causa:** Registros en `versiones_sistema` con `estado = 'INACTIVA'`.
**Fix aplicado:** UPDATE manual a ACTIVA para V17.1.

---

*Última actualización: 2026-03-20*
*Para atacar: ISS-002 (kill-switch a BD), ISS-003 (null pointer en tick['ask']).*
