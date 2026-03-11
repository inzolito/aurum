# AURUM — PENDIENTES

> [!IMPORTANT]
> **INSTRUCCIÓN PARA EL AGENTE:** Toda tarea de este documento que sea marcada como **COMPLETADA** o cualquier cambio técnico realizado en el código **DEBE** ser documentado inmediatamente en el archivo `docs/HISTORIAL.md`. No se considera terminada una tarea hasta que su bitácora de cambios esté registrada cronológicamente en el historial.

> **Propósito:** Hoja de Ruta Inmediata. Registro de tareas activas, planes detallados de implementación y mejoras próximas. Es el documento de trabajo diario para coordinar los siguientes pasos del desarrollo.

**Última actualización:** 2026-03-11

---

## 📈 EXPANSIÓN DE ACTIVOS (Nivel V15)

**Objetivo:** Incrementar la diversificación temporal del bot, cubriendo las sesiones asiática (Tokio), europea (Londres) y americana (Nueva York) con activos de alta limpieza técnica.

### 0. Activos Base (Estado de Verificación) 🛡️
*   **XTIUSD** (Petróleo WTI) - [YA EXISTE ✅]
*   **XBRUSD** (Petróleo Brent) - [YA EXISTE ✅]
*   **US30 / DJIUSD** (Dow Jones) - [YA EXISTE ✅]
*   **US500 / SPXUSD** (S&P 500) - [YA EXISTE ✅]

### 1. Sesión Asiática (Tokio / Sídney) 🌏 [PENDIENTE]
*   **AUDUSD** (Dólar Australiano - Materias Primas)
*   **AUS200** (Índice Australia - Minería/Energía)
*   **JP225** (Nikkei 225 - Índice Japón)
*   **NZDUSD** (Dólar Neozelandés - Asia-Pacífico)
*   **USDCNH** (Yuan - Clave para sentimiento en Asia)

### 2. Sesión Europea (Londres) 🇪🇺 [PENDIENTE]
*   **GER40** (DAX Alemán - Industrial)
*   **UK100** (FTSE 100 - Índice Londres)
*   **EURGBP** (Cruce técnico de alta estabilidad)
*   **FRA40** (CAC 40 - Índice Francia)
*   *EURUSD / GBPUSD - [YA EXISTEN ✅]*

### 3. Sesión Americana (Nueva York) 🇺🇸 [PENDIENTE]
*   **USDCAD** (Loonie - Correlación directa con Petróleo)
*   **USDCHF** (Franco Suizo - Refugio seguro)
*   **EURCAD** (Euro vs CAD - Materias primas)
*   **AUDCAD** (AUD vs CAD - Cruce de recursos)
*   **USDMXN** (Peso Mexicano - Emergente alta tasa)
*   *USTEC / NDXUSD - [YA EXISTE ✅]*

---
*Tarea planificada el 2026-03-11 | Pendiente de configuración en base de datos y horarios operativos.*


---

## 🔍 SEGUIMIENTO POST-ACTUALIZACIONES 2026-03-11

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