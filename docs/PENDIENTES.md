# AURUM — PENDIENTES

> [!IMPORTANT]
> **INSTRUCCIÓN PARA EL AGENTE:** Toda tarea de este documento que sea marcada como **COMPLETADA** o cualquier cambio técnico realizado en el código **DEBE** ser documentado inmediatamente en el archivo `docs/HISTORIAL.md`. No se considera terminada una tarea hasta que su bitácora de cambios esté registrada cronológicamente en el historial.

> **Propósito:** Hoja de Ruta Inmediata. Registro de tareas activas, planes detallados de implementación y mejoras próximas. Es el documento de trabajo diario para coordinar los siguientes pasos del desarrollo.

**Última actualización:** 2026-03-11

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