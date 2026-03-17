# AURUM — Reporte de Auditoría V14: Security & Intelligence Upgrades
**Fecha:** 2026-03-10
**Versión:** V14.1
**Auditor:** Claude Sonnet 4.6

---

## Resumen Ejecutivo

Se aplicaron 5 mejoras estructurales derivadas del análisis de debilidades del sistema V13.5.
El objetivo fue convertir vulnerabilidades operacionales conocidas en mecanismos de defensa activos.

| ID | Debilidad | Estado | Archivos Modificados |
|----|-----------|--------|---------------------|
| D1 | Sin filtro de sesión / sin delay de apertura | ✅ Resuelto | `core/risk_module.py` + DB |
| D2 | Pesos de obreros estáticos (sin aprendizaje) | ✅ Resuelto | `core/manager.py`, `core/scheduler.py` |
| D3 | Sin autopsia de pérdidas | ✅ Resuelto | `core/manager.py`, `config/db_connector.py` + DB |
| D4 | Lotaje fijo ante noticias de alto impacto | ✅ Resuelto | `core/risk_module.py` |
| D5 | Sin límite de llamadas Gemini (riesgo de costo) | ✅ Resuelto | `workers/worker_nlp.py` |

**Migración de BD requerida:** `db/migration_v14_security.sql`

---

## Detalle Técnico

---

### D1 — Filtro de Sesión + Anti-Volatilidad de Apertura

**Problema:** El bot operaba 24h en días hábiles sin distinguir sesiones. Durante la sesión asiática (22:00–07:00 UTC) los pares FOREX tienen liquidez baja y spreads altos. Los primeros minutos de apertura de Londres o NY tienen "latigazos" que invalidan el análisis técnico.

**Solución implementada en `core/risk_module.py` (método `filtro_seguridad`):**
- La Verificación 3 ya leía la tabla `horarios_operativos` pero estaba vacía.
- Se pobló la tabla con `db/migration_v14_security.sql`:
  - FOREX: 07:00–16:00 UTC
  - ÍNDICES US: 14:30–21:00 UTC
  - COMMODITIES: 07:00–20:00 UTC
- Se añadió bloqueo adicional: si el activo lleva < 20 minutos dentro de su ventana de apertura, se bloquea la entrada (anti-volatilidad).

**Comportamiento nuevo:**
```
[RISK] BLOQUEO: EURUSD fuera de horario operativo.
[RISK] BLOQUEO: EURUSD en periodo anti-volatilidad de apertura (7/20 min).
```

**Tablas afectadas:** `horarios_operativos` (INSERT por categoría).

---

### D2 — Recalibración de Pesos de Obreros (Manual)

**Problema identificado:** Los pesos estaban fijos. Un obrero con racha de señales incorrectas seguía pesando igual.

**Decisión de diseño:** La recalibración automática semanal fue implementada y luego **desactivada** por decisión del operador. Razones:
- Con pocos trades/semana, una muestra de 7 días no es estadísticamente significativa.
- El ajuste automático puede crear bucles perversos (si NLP baja → más trades sin veto NLP → más pérdidas → NLP baja más).
- Los pesos reflejan intención de diseño deliberada, no deben cambiar por ruido estadístico de corto plazo.

**Qué se implementó:**
- Método `_recalibrar_pesos()` en `core/manager.py` — disponible para uso **manual** cuando haya suficiente evidencia histórica (recomendado: 100+ autopsias acumuladas en D3).
- El scheduler tiene la línea comentada. Para activar manualmente: descomentar en `core/scheduler.py` o llamar desde `aurum_admin.py`.

**Flujo correcto de ajuste de pesos:**
1. Acumular autopsias (D3) durante semanas.
2. Revisar tabla `autopsias_perdidas` — identificar patrón de fallo sistemático en un obrero.
3. Ajustar el peso manualmente en `parametros_sistema` con evidencia suficiente.

**Tablas afectadas:** `parametros_sistema` (solo con ajuste manual).

---

### D3 — Autopsia de Pérdidas (Post-Trade)

**Problema:** Cuando un trade terminaba en pérdida, el sistema actualizaba `resultado_final = 'PERDIDO'` pero no analizaba *por qué* falló ni aprendía de ello. El campo `motivo` en `registro_senales` guardaba la justificación completa de entrada pero nadie la contrastaba con el resultado.

**Solución implementada:**
- `auditar_precision_cierres()` en `core/manager.py` detecta trades cerrados. Se extendió su query SQL para incluir el `simbolo` del activo.
- Cuando `resultado == "PERDIDO"`, busca el último `motivo` de entrada del activo en `registro_senales` y llama a `_autopsia_perdida()`.
- `_autopsia_perdida()`: envía un prompt a Gemini (`gemini-3.1-flash-lite`) con:
  - El activo y la pérdida en USD.
  - La justificación original de entrada (`motivo`).
  - Solicita: tipo de fallo (TECNICO/MACRO/TIMING/RIESGO), worker culpable, descripción y corrección sugerida.
- El resultado se persiste en la nueva tabla `autopsias_perdidas` vía `db_connector.guardar_autopsia()`.

**Nueva tabla:** `autopsias_perdidas` (ver `db/migration_v14_security.sql`).

**Uso futuro:** Las autopsias acumuladas alimentarán directamente la recalibración D2 y permitirán auditorías manuales de patrones de fallo.

---

### D4 — IA-Risk: Reducción de Lotaje ante Noticias de Alto Impacto

**Problema:** `calcular_lotes_dinamicos()` escalaba el lotaje por convicción del veredicto pero no distinguía si había un NFP, una decisión del Fed o un dato de CPI publicado en los últimos 30 minutos.

**Solución implementada en `core/risk_module.py`:**
- Nuevo método `_factor_riesgo_noticias()` que consulta `raw_news_feed`.
- Busca noticias con publicación < 30 minutos y título que contenga palabras clave: `fed, nfp, fomc, cpi, gdp, inflation, powell, employment, jobs, interest rate, rate decision`.
- Si hay al menos 1 coincidencia: retorna `0.5` (reduce lotaje al 50%).
- Si no hay noticias o la DB no está disponible: retorna `1.0` (sin cambio).
- Se aplica como factor multiplicador al final del cálculo de lotaje, respetando siempre el lote mínimo.

**Comportamiento nuevo:**
```
[RISK] Noticias de alto impacto recientes (2). Lotaje reducido al 50%.
```

---

### D5 — Límite Diario de Llamadas a la API de Gemini

**Problema:** Con `_UMBRAL_PROXIMIDAD = 0.15` (bajado en P-3) y TTL de caché de 5 minutos, Gemini podía recibir muchas más llamadas por día con 9+ activos activos, elevando el costo de API sin control.

**Solución implementada en `workers/worker_nlp.py`:**
- Nueva constante `_MAX_CALLS_PER_DAY = 200` (configurable vía `NLP_MAX_CALLS_DAY` en `.env`).
- El contador `_api_calls_today` se incrementa en cada llamada real a Gemini y se reinicia automáticamente al cambiar de día UTC.
- Si el límite diario se alcanza, el método `_llamar_gemini()` retorna el fallback sin llamar a la API. Los análisis siguen ejecutándose con el caché existente.

**Variables de entorno nuevas:**
```
NLP_MAX_CALLS_DAY=200   # Ajustable en .env
```

---

## Migración de Base de Datos

Archivo: `db/migration_v14_security.sql`

Ejecutar en GCP PostgreSQL **antes** de reiniciar el bot:

```bash
psql -h 35.239.183.207 -U aurum_user -d aurum_db -f db/migration_v14_security.sql
```

O desde el panel de GCP → SQL → Cloud Shell:
```sql
\i /path/to/migration_v14_security.sql
```

**Qué crea/modifica:**
1. `CREATE TABLE autopsias_perdidas` — nueva tabla con índices.
2. `INSERT INTO horarios_operativos` — pobla ventanas de sesión por categoría (idempotente, no duplica).

---

## Variables de Entorno Nuevas

Agregar a `.env` si se quiere personalizar:

```env
NLP_MAX_CALLS_DAY=200      # Límite diario de llamadas a Gemini (default: 200)
```

---

## Puntos de Verificación Post-Despliegue

- [ ] Migración SQL ejecutada en GCP (`autopsias_perdidas` existe, `horarios_operativos` tiene filas).
- [ ] Bot arranca sin errores con la nueva versión.
- [ ] En el primer ciclo con activo FOREX fuera de 07:00–16:00 UTC: aparece `[RISK] BLOQUEO: fuera de horario operativo`.
- [ ] Al abrir una sesión (ej. 07:00 UTC), los primeros 20 min aparece `[RISK] BLOQUEO: anti-volatilidad de apertura`.
- [ ] Cuando Gemini llama, aparece `[NLP] Llamada API #X/200 hoy`.
- [ ] Próximo domingo 17:00 UTC: aparece `[SCHEDULER] Ejecutando recalibracion semanal`.
- [ ] En el primer trade perdedor: aparece `[AUTOPSIA] #TICKET SIMBOLO -> Fallo: ...`.

---

## Issues Pendientes para Próxima Auditoría

| ID | Descripción | Prioridad |
|----|-------------|-----------|
| P-4 | Gap & Level Guard — foto de cierre del viernes para detectar gaps del domingo | Alta |
| P-5 | Sentimiento 24/7 — NLP activo durante el fin de semana acumulando contexto | Media |
| F-1 | `_recalibrar_pesos` usa un JOIN sin tiempo exacto (aproximación). Refinar con LATERAL JOIN en V15. | Baja |
| F-2 | `_factor_riesgo_noticias` podría incorporar un calendario económico externo para noticias futuras (no solo publicadas). | Media |
| F-3 | `horarios_operativos` no maneja cambio de horario de verano/invierno en UK/US (diferencia de 1h). Revisar en marzo y noviembre. | Media |

---

*Documento generado automáticamente tras aplicar upgrades V14.1 — 2026-03-10*
