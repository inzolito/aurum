# AURUM — Issues Conocidos del Bot

Lista técnica de bugs y problemas identificados. Ordenados por criticidad.

---

## 🔴 CRÍTICOS

### ISS-001 — Instancia duplicada silenciosa (RESUELTO parcialmente)
**Síntoma:** El bot muere en loop 786 veces sin que nadie se entere.
**Causa:** `_verificar_instancia_duplicada()` hacía `return` (exit code 0) en vez de `sys.exit(1)`. systemd no lo marcaba como failed. Sin alerta Telegram.
**Fix aplicado:** sys.exit(1) + notificación Telegram al detectar duplicado.
**Pendiente:** Si el proceso zombie no libera el PID file, el nuevo nunca arranca. Falta auto-cleanup del PID file stale en el SHIELD o en el propio systemd unit (PIDFile= directive).

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

### ISS-012 — PID file zombie bloquea reinicios limpios
**Síntoma:** Si el proceso muere abruptamente (SIGKILL), el PID file queda. El siguiente arranque detecta el PID como "proceso existente" aunque no lo sea.
**Causa:** `psutil.pid_exists()` puede retornar True para PIDs reutilizados por el OS.
**Fix parcial:** Se limpia manualmente con `rm aurum_core.pid`.
**Pendiente:** Usar `fcntl.flock()` (file lock) en vez de PID file para detección atómica en Linux.

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
*Para atacar: empezar por ISS-001 (PID lock robusto), ISS-002 (kill-switch a BD) e ISS-003 (null pointer).*
