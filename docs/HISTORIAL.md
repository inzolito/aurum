# AURUM — HISTORIAL

> **Propósito:** Bitácora de Guerra. Registro cronológico de todas las mejoras, bugfixes y cambios realizados. Sirve como memoria a corto y medio plazo para entender la evolución del código y las decisiones tomadas.

Log cronológico de todo lo resuelto. Las entradas más recientes van arriba.

---

## 2026-03-27 (V18.2 — Filtros de Calidad de Señal)

### Contexto: análisis de 94 trades (V17.2 → V18.1, últimas 2 semanas)

Se realizó un análisis completo de los 94 trades ejecutados entre 2026-03-13 y 2026-03-27.
El sistema tenía Win Rate 33% y PnL -$261 en ese período. El análisis identificó 4 patrones
de fallo que concentraban el 88% de las pérdidas.

**Documentos generados:**
- `docs/TRADES_ANALISIS_V172_V181.md` — detalle de los 94 trades con votos, PnL, justificación IA
- `docs/ANALISIS_DEBILIDADES_V172_V181.md` — análisis de debilidades con datos estadísticos
- `docs/SIMULACION_FILTROS_COMBINADOS.md` — simulación retroactiva: 33% WR → 58% WR, -$261 → +$232

### Hallazgos principales

- **Trend≥0.6 + Hurst PERSISTENTE**: 19 trades, 15.8% WR, -$252 PnL (88% del daño total)
- **Fuerza dominante Trend vs NLP**: Trend como fuerza dominante = 29.8% WR; NLP = 40.9% WR
- **Activos problemáticos**: EURUSD (18.2% WR), NZDUSD (11.1%), AUDCAD (11.1%)
- **Horario 17-20h Santiago**: 9 trades, 11.1% WR, -$88 PnL

### Cambios aplicados

#### F1 — Bloqueo Trend sobreextendido (`core/manager.py`)
Nuevo bloque antes del check de umbral. Si `v_trend >= 0.6` AND `h_estado == 'PERSISTENTE'`,
la evaluación retorna `BLOQUEADO_TENDENCIA_PERSISTENTE` sin ejecutar orden.
Por sí solo este filtro habría cambiado el PnL de -$261 a -$8.

#### F2 — Umbral elevado por activo (`core/manager.py` + BD)
Lee `params.get(f"GERENTE.umbral_{simbolo_interno}")` desde `parametros_sistema`.
Si el valor es mayor al umbral base (0.45), lo usa como umbral para ese activo.
Parámetros insertados en BD:
- `GERENTE.umbral_EURUSD = 0.60`
- `GERENTE.umbral_NZDUSD = 0.60`
- `GERENTE.umbral_AUDCAD = 0.60`
Para agregar más activos en el futuro: INSERT en `parametros_sistema` con clave `GERENTE.umbral_SIMBOLO`.

#### F3 — Bloqueo horario 17-20h Santiago (`core/manager.py` + BD)
Nuevo bloque después de que los workers votan (el dashboard sigue viendo los votos) pero
antes de la ejecución. Usa `ZoneInfo('America/Santiago')` para hora local correcta.
Retorna `BLOQUEADO_HORARIO_SANTIAGO`. Configurable desde BD:
- `GERENTE.hora_bloqueo_inicio = 17`
- `GERENTE.hora_bloqueo_fin = 20`

#### F4 — Rebalanceo de pesos NLP/Trend (BD)
| Parámetro | Antes | Ahora |
|---|---|---|
| `TENDENCIA.peso_voto` | 0.50 | 0.35 |
| `NLP.peso_voto` | 0.30 | 0.55 |
| `SNIPER.peso_voto` | 0.20 | 0.20 |

Nueva fórmula: `veredicto = Trend*0.35 + NLP*0.55 + Sniper*0.20`

#### Import añadido
`from zoneinfo import ZoneInfo` en línea 6 de `core/manager.py`

### Resultado simulado con todos los filtros aplicados juntos
| Escenario | Trades | Win Rate | PnL |
|---|---|---|---|
| Sin filtros (V18.1) | 82 | 33% | -$261 |
| F1+F2+F3 | 36 | 55.6% | +$248 |
| F1+F2+F3+F4 | 31 | **58.1%** | **+$232** |

### Versión en BD
`versiones_sistema` id=11, `V18.2`, estado `ACTIVA`. V18.1 marcada `OBSOLETA`.

---

## 2026-03-20 (V18.0 — Laboratorio de Activos + MacroSensor)

### Laboratorio de Activos
Motor de simulación paralelo al bot real. Múltiples modelos (labs) con parámetros propios evalúan los mismos votos de workers que producción, sin abrir órdenes reales. Capital virtual $3,000 por lab. Aislamiento total de producción.

**Nuevas tablas BD:** laboratorios, lab_activos, lab_parametros, lab_senales, lab_operaciones, lab_balance_diario

**Nuevos archivos:**
- core/lab_evaluator.py — evaluador del laboratorio (LabEvaluator)

**Archivos modificados:**
- core/manager.py — _evaluar_internamente() retorna votos individuales; hook _evaluar_laboratorios() al final del ciclo; get_activos_para_evaluar() incluye activos de labs activos
- config/db_connector.py — 12 métodos nuevos para lab y MacroSensor
- core/scheduler.py — limpieza nocturna 03:00 UTC (lab_senales >30d + regimenes vencidos)
- news_hunter.py — _evaluar_regimen_macro() detecta/crea/actualiza regímenes con Gemini
- dashboard/backend/main.py — endpoints GET /api/lab y PUT /api/lab/{id}/estado
- dashboard/frontend/src/pages/Lab.jsx — nueva página de laboratorio
- dashboard/frontend/src/components/MacroBar.jsx — barra macro global en header
- dashboard/frontend/src/App.jsx y SideNav.jsx — rutas y navegación

### MacroSensor
Regímenes macro creados automáticamente por news_hunter al procesar noticias con impacto ≥ 6. Gemini decide INSERT/UPDATE/DISIPAR. Regímenes activos inyectados en prompt de NLPWorker en cada votación. Visible en barra global del header del dashboard.

**Nueva tabla BD:** regimenes_macro

**Primer análisis automatizado (2026-03-20):**
1,950 noticias analizadas. 4 regímenes RISK_OFF detectados e insertados:
- Guerra Irán - Shock Petrolero Estructural (peso 0.95, indefinido)
- Fed Hawkish - No Pivot por Inflación Energética (peso 0.80, expira 30-Abr)
- Recesión Industrial Europea - Shock Energético (peso 0.75, expira 15-Abr)
- Dólar Refugio Hegemónico Absoluto (peso 0.85, indefinido)

---

## 2026-03-12 (V15.6 — Tácticas de Supervivencia: Centinela Cloud y Control Remoto)

### Problema resuelto: Ceguera de caídas y Errores de compatibilidad V15

El sistema adolecía de tres problemas silentes que bloqueaban el control remoto de la aplicación: (1) Telegram generaba un `UnicodeEncodeError`/`ArgumentError` al lanzar el comando `/start` debido a un parámetro de teclado incompatible en su librería. (2) Las consultas de reportes como "Rendimiento Hoy" fallaban porque la tabla `registro_operaciones` actualizó el nombre de varias columnas importantes que el Daemon seguía buscando en versión antigua. (3) No había manera de enterarse si la computadora host (el Windows físico) sufría una desconexión total hasta retornar al equipo presencialmente.

#### Cambios implementados

- **`cloud_sentinel.py` (Dead Man's Switch)** — Nuevo componente *Cloud-Ready*. Evalúa la tabla `estado_bot` cada par de minutos desde un servidor remoto independiente. Si detecta que no hay latidos del Core por más de 5 minutos, automáticamente levanta alertas de emergencia vía Telegram para informar de la avería del equipo raíz (Windows).
- **`telegram_daemon.py`** — Fix crítico y Compatibilidad V15.
  - Se removió `persistent=True` de `ReplyKeyboardMarkup` para reparar el fallo del despliegue del teclado interactivo en `/start`.
  - Consultas actualizadas a la nueva arquitectura SQL: `fecha_apertura` → `tiempo_entrada` y `clave` → `nombre_parametro`.
  - **Nuevo Comando Maestro (`🔄 REINICIAR BOT`):** Permite exterminar de forma forzada toda instancia huérfana y relanzar el entorno limpiamente a control remoto.
- **`restart_all.bat`** — Nuevo *script* de purga para entorno de Windows. Obliga el exterminio (`/F`) de todos los remanentes fantasma cargados como `pythonw.exe` e invoca instantáneamente `start_bot.ps1` reconstruyendo todo el motor a la perfección.

---

## 2026-03-12 (V15.5 — Infraestructura: Reparación de Arranque PS1 y Lanzamiento Dual)

### Problema resuelto: Caídas de fondo sin notificación y error sintáctico

La directriz de la V15 exigía que `heartbeat.py` (SHIELD) fuese el encargado de encender y monitorizar a los bots secundarios (News Hunter y Telegram Daemon). Sin embargo, el script de arranque `start_bot.ps1` lanzaba únicamente a `main.py` y, peor aún, tenía un error de sintaxis que impedía que funcionase, forzando a lanzar el bot manualmente desde consolas que al cerrarse aniquilaban el subproceso de Windows en seco.

#### Cambios implementados

- **`start_bot.ps1`** — Refactorizado para el entorno V15 de Windows:
  - Se subsanó el error del apóstrofe fantasma en la línea final del log.
  - Se migró el intérprete de `python.exe` a `pythonw.exe` para ambos procesos, lo que garantiza inmunidad ante cierres accidentales de ventanas de comandos.
  - **Lanzamiento Dual:** Ahora el script levanta y aísla simultáneamente a `main.py` y a `heartbeat.py`. Una vez vivos en RAM, el SHIELD se hace cargo automáticamente de levantar a Telegram y News Hunter, devolviendo la robustez perdida al ecosistema V15.

---

## 2026-03-11 (V15.4 — Dashboard Diagnóstico: Fin de fallos silenciosos)

### Problema resuelto: "CANCELADO_RIESGO" sin contexto en el admin

El panel de votos de `aurum_admin.py` mostraba todos los bloqueos como
`CANCELADO_RIESGO` sin explicar la causa, haciendo imposible distinguir
un bug de un comportamiento correcto (posición abierta, drawdown, etc.).

#### Cambios implementados

- **`core/manager.py`** — Motivo específico cuando `filtro_seguridad()` bloquea:
  - Consulta MT5 post-bloqueo para determinar la causa real.
  - `"Posición abierta en DJIUSD (1 pos.). Anti-duplicado activo."` si hay posición.
  - `"Límite de pérdida flotante alcanzado (-$X.XX USD)."` si es drawdown.
  - `"Activo bloqueado: estado no operativo o sin mapeo en BD."` en otros casos.

- **`aurum_admin.py`** — Nuevo panel de diagnóstico bajo la tabla de votos:
  - `_fmt_decision()` — Icono + color por tipo de decisión (✅🟢🔴⚪🔒🕐⚡🚫⚠️💥).
  - `_motivo_corto()` — Parser inteligente que convierte el motivo largo en resumen
    legible: "Pos. abierta: DJIUSD", "Umbral no alc. +0.12 < 0.45",
    "Divergencia Trend↔NLP", "Fuera de horario", etc.
  - **Panel 1** (sin cambios): Tabla numérica de votos por obrero.
  - **Panel 2** (nuevo): Tabla de diagnóstico con `Estado | Motivo | NLP/Gemini`.
    El análisis NLP se lee de `cache_nlp_impactos.razonamiento` (solo si existe).
    Texto truncado a 110 caracteres para legibilidad. Si no hay análisis: "Sin análisis IA reciente".

---

## 2026-03-11 (V15.3 — Remapeo de Símbolos Broker Weltrade)

### Problema resuelto: Workers devolvían 0.000 en todos los índices

Los workers de US30, US500, USTEC y GER40 llamaban a `obtener_velas("US30_i")` —
ese símbolo no existe en Weltrade. MT5 devolvía DataFrame vacío y los workers
retornaban silenciosamente `0.000` en todos los ciclos.

**Nomenclatura real de Weltrade:**
- Índices americanos: sin sufijo `_i` → `DJIUSD`, `SPXUSD`, `NDXUSD`
- DAX: `GEREUR`
- FOREX y commodities: mantienen sufijo `_i` (sin cambios)

**Activos fantasma pausados:** AUS200, JP225, UK100, FRA40 no están disponibles
en Weltrade. Cada ciclo el NLP intentaba analizarlos y quemaba quota de Gemini.

#### Cambios implementados

- **`config/db_connector.py`** — `_SIMBOLO_BROKER_MAP` actualizado:
  `US30→DJIUSD`, `US500→SPXUSD`, `USTEC→NDXUSD`, `GER40→GEREUR`.
  Este mapa es el fallback de Survival Mode — la fuente primaria es la BD.

- **BD `activos.simbolo_broker`** — Actualizado para los 4 índices.
  Script: `db/migration_v15_broker_map.sql`

- **BD `activos.estado_operativo`** — AUS200, JP225, UK100, FRA40 → `PAUSADO`.

- **`db/apply_migration.py`** — Nuevo runner Python reutilizable para futuros
  archivos `.sql` de migración.

- **`core/manager.py`** — Se descomentó `notificar_error_market_watch(simbolo_broker)`.
  Ahora si un activo (ej. un índice mal mapeado o cerrado) no responde en el
  Market Watch, el sistema dispara una alerta roja en Telegram en lugar de
  fallar silenciosamente y botar `0.000`.

---

## 2026-03-11 (V15.2 — Process Management: Mutex + SHIELD Rewrite)

### Problema resuelto: Duplicados de procesos y botones Telegram sin respuesta

**Síntoma**: Los botones del bot de Telegram no respondían. La causa era que
`heartbeat.py` relanzaba los daemons sin detectar que ya corrían, generando
conflicto `telegram.error.Conflict` por doble sesión `getUpdates`.

**Causa raíz**: En Windows, `venv/Scripts/pythonw.exe` actúa de LAUNCHER y spawna
el intérprete del sistema como proceso hijo corriendo el mismo script. Cada script
genera 2 procesos OS (launcher + worker), pero son UNA sola instancia. El código
anterior los contaba como duplicados y mataba uno de cada par, rompiendo los scripts.

#### Cambios implementados

- **`telegram_daemon.py`** — Añadido Named Mutex `Global\AurumTelegramDaemonMutex`
  al inicio de `main()`. Segunda instancia detectada atómicamente → `sys.exit(0)`.

- **`news_hunter.py`** — Añadido Named Mutex `Global\AurumNewsHunterMutex` en
  `if __name__ == "__main__":`. Se usó `os._exit(0)` en lugar de `sys.exit(0)`
  porque `sys` no estaba importado en ese bloque.

- **`main.py`** — Eliminadas las llamadas a `_lanzar_telegram_daemon()` y
  `_lanzar_news_hunter()` al arrancar. El SHIELD (`heartbeat.py`) es el único
  responsable de lanzar los daemons. Evita condición de carrera en el arranque.

- **`heartbeat.py` — `get_aurum_processes()` reescrita completamente:**
  Recolecta todos los procesos Python de Aurum con su PPID. En el segundo paso,
  solo cuenta como instancia el proceso RAÍZ de cada cadena (el que no tiene padre
  Aurum del mismo tipo). Así el par launcher+worker cuenta como UNA instancia.

- **`heartbeat.py` — `cleanup_ghost_processes()` reescrita:**
  Para verdaderos duplicados, mata el árbol completo (launcher + todos los hijos)
  usando `p.children(recursive=True)` antes de matar la raíz.

---

## 2026-03-11 (V15.2 — Implementación de Expansión de Portafolio)

### Expansión de Activos en Base de Datos

Se ha completado la integración física de **14 nuevos activos** en la tabla `activos` de la base de datos, configurados inicialmente en estado `PAUSADO` y listos para su activación operativa.

**Activos Incorporados:**
- **Sesión de Tokio:** `AUDUSD`, `AUS200`, `JP225`, `NZDUSD`, `USDCNH`.
- **Sesión de Londres:** `GER40`, `UK100`, `EURGBP`, `FRA40`.
- **Sesión de Nueva York:** `USDCAD`, `USDCHF`, `EURCAD`, `AUDCAD`, `USDMXN`.

**Impacto:** El sistema ahora reconoce estos símbolos para futuras configuraciones de horarios operativos y ejecución. No se han activado para trading real todavía.

---

## 2026-03-11 (V15.1 — Workers Fix: NLP/Volume/Cross cero)

### Diagnóstico: 3 workers sistemáticamente en 0 — Corregidos

**Causa Raíz 1 — Cross=0 (FIX-CROSS-02):**
`worker_cross.py` usaba `"SPXUSD"` (sin sufijo `_i`) como sensor SPX.
`obtener_velas()` no podía suscribirse al símbolo y retornaba DataFrame vacío.
Resultado: `var_spx = 0` en todos los ciclos → ninguna regla se activaba → voto = 0.
- **Fix:** Sensor cambiado a `"SPXUSD_i"`. Se añadió `_obtener_variacion()` con
  lógica de fallback automático: prueba con `_i` y sin `_i` para máxima
  compatibilidad de broker.

**Causa Raíz 2 — Volumen=0 (FIX-VOL-02):**
`worker_volume.py` usaba `tick.last` como precio de referencia para el caché
y para calcular la posición del precio dentro del Volume Profile.
En FOREX, el campo `last` siempre vale `0.0` (solo existe en acciones).
Resultado: `precio_actual = 0` → div. por cero en caché → recalculo perpetuo, y
el cálculo de posición relativa (VAH/VAL) usaba precio 0 → voto = 0 siempre.
- **Fix:** Precio de referencia cambiado a `(bid + ask) / 2` cuando `last == 0`,
  con fallback al último precio del array histórico.

**Causa Raíz 3 — NLP=0 en mayóa (FIX-NLP-02):**
`upsert_nlp_cache()` usaba `INSERT` simple sin `ON CONFLICT DO UPDATE`.
El caché acumulaba filas por activo. `leer_cache_nlp()` filtraba por `hash_contexto`
(que cambia cada 5 min) → siempre retornaba `None` → reintento Gemini → el que
fallaba silenciosamente retornaba fallback `{voto: 0.0}`.
- **Fix:** `upsert_nlp_cache()` ahora usa `ON CONFLICT (simbolo) DO UPDATE` (UPSERT
  real). `leer_cache_nlp()` ahora filtra por TTL (`creado_en >= NOW() - TTL_min`)
  en vez de por hash.
- **Migración requerida:** `db/migration_v15_fixes.sql` — agregar `UNIQUE(simbolo)`
  en `cache_nlp_impactos`. Ejecutar con usuario owner (aurum_admin en GCP).

**Archivos modificados:**
- `workers/worker_cross.py` — sensor SPX y fallback en `_obtener_variacion()`
- `workers/worker_volume.py` — precio de referencia bid/ask en lugar de .last
- `config/db_connector.py` — UPSERT real en `upsert_nlp_cache()`, TTL en `leer_cache_nlp()`
- `db/migration_v15_fixes.sql` — nuevo archivo de migración (ejecutar en GCP)

---

## 2026-03-10 (V15.0 — Telegram Daemon V2.0)

### Reestructuración completa del bot de Telegram

Problema resuelto: `telegram.error.Conflict` causado por múltiples sesiones
de `getUpdates` activas cuando el Core se reiniciaba. El bot corría como
thread bloqueante dentro de `main.py`, haciendo su ciclo de vida dependiente
del Core.

**Solución**: Separación total de procesos. Arquitectura 3-procesos:
```
main.py            — Motor de análisis y trading
news_hunter.py     — Scraping de noticias RSS
telegram_daemon.py — Bot de Telegram (proceso independiente)
heartbeat.py       — SHIELD: vigila los 3 procesos anteriores
```

#### Cambios implementados

- **NUEVO `telegram_daemon.py`** — Proceso independiente con su propio event loop.
  Al iniciar llama a `delete_webhook(drop_pending_updates=True)` para limpiar
  sesiones fantasma de polling. Monitorizado por SHIELD.
- **`main.py`** — Eliminado el `threading.Thread(target=run_telegram_bot)`.
  Reemplazado por `_lanzar_telegram_daemon()` que lanza el daemon como proceso
  independiente (igual que el Hunter). Refactorizado `_lanzar_proceso_daemon()`
  como helper reutilizable para ambos daemons.
- **`heartbeat.py`** — Añadido `daemon` a `get_aurum_processes()`. El SHIELD
  ahora vigila 3 procesos y relanza el daemon si cae. Alerta Telegram:
  "📱 Daemon Telegram recuperado silenciosamente."
- **`config/telegram_bot.py`** — Marcado como DEPRECADO. No se elimina por
  referencia histórica.

#### Nuevas notificaciones (notifier.py)

- **`notificar_noticia_procesada()`** — FASE 2: Se dispara desde `news_hunter.py`
  para noticias con impacto IA >= 5. Formato: título, fuente, fecha publicación,
  barra de impacto visual.
- **`notificar_tp_alcanzado()`** — FASE 4: TP tocado. PnL, ROE, veredicto
  original, si el modelo fue correcto, balance y equity.
- **`notificar_sl_alcanzado()`** — FASE 4: SL tocado con autopsia forense completa
  (tipo de fallo, worker culpable, corrección sugerida) leída de `autopsias_perdidas`.
- **`_build_msg_orden()` refactorizado** — FASE 3: Nuevo formato con tabla de
  votación completa (emojis por dirección), R/R ratio, equity en el footer.

#### Nuevos comandos del daemon

- `/silencio` — Desactiva notificaciones automáticas. Estado persiste en BD.
- `/despertar` — Reactiva notificaciones.
- Botón `📋 MIS POSICIONES` — Posiciones abiertas con PnL flotante de MT5.
- Botón `📊 RENDIMIENTO HOY` — Win rate, trades y PnL neto del día.
- Botón `⚙️ PARAMETROS` — Pesos del ensemble y parámetros del Gerente.
- **Pulso nocturno 02:00 UTC** — Resumen diario automático (trades, noticias,
  próximo evento macro, estado de los 3 procesos).

---

## 2026-03-10 (V14.2 — Ensemble Intelligence Fixes)

### Diagnóstico: 3 obreros sistemáticamente en 0 — Corregidos

- **FIX-NLP-01** `core/manager.py` — Eliminado el gate de convicción técnica que bloqueaba al NLP en un loop circular. El NLP ahora vota **siempre** de forma independiente. La caché de 5 min y el hash SHA256 de contexto mantienen el consumo de tokens Gemini bajo control sin necesitar el bloqueo.
- **FIX-VOL-01** `workers/worker_volume.py` — Zona de Vacío (LVN) ahora emite voto **direccional** (±0.5) en lugar de 0.0. Si el precio está por encima del Value Area → voto alcista (rotura con poco rozamiento). Si está por debajo → voto bajista. Solo retorna 0.0 si la LVN está inexplicablemente dentro del VA.
- **FIX-CROSS-01** `workers/worker_cross.py` — Cobertura extendida de 3 a **todos los activos del portfolio**. Nuevas reglas añadidas:
  - `EURUSD`, `GBPUSD` → correlación inversa con DXY (umbral 0.30%)
  - `USDJPY` → Risk-On/Off via SPX (umbral 0.50%)
  - `XAGUSD` → mismo comportamiento que XAUUSD vs DXY
  - `XTIUSD`, `XBRUSD` → correlación directa con var_oil (umbrales 0.15% y 0.40%)
  - `US500` → añadido junto a USTEC/US30 vs SPX



### Debilidades corregidas (D1 a D5)
- **D1** `core/risk_module.py` — Filtro de sesión activo: ventanas FOREX (07–16 UTC), Índices (14:30–21 UTC), Commodities (07–20 UTC). Bloqueo anti-volatilidad los primeros 20 min de apertura. `db/migration_v14_security.sql` popula `horarios_operativos`.
- **D2** `core/manager.py` + `core/scheduler.py` — Recalibración semanal de pesos cada domingo 17:00 UTC. Ajuste ±0.05 basado en tasa de acierto por obrero (muestra mínima 20 trades, límites [0.10, 0.60]).
- **D3** `core/manager.py` + `config/db_connector.py` — Autopsia de Pérdidas: Gemini analiza cada trade perdedor contrastando la justificación original de entrada con el resultado. Resultado guardado en `autopsias_perdidas`.
- **D4** `core/risk_module.py` — IA-Risk: `_factor_riesgo_noticias()` reduce el lotaje al 50% si hay noticias de alto impacto (Fed, NFP, CPI, FOMC, etc.) publicadas en los últimos 30 minutos.
- **D5** `workers/worker_nlp.py` — Contador diario de llamadas Gemini. Límite configurable `NLP_MAX_CALLS_DAY` (default 200). Se reinicia cada día UTC automáticamente.
- **Nueva tabla BD:** `autopsias_perdidas` (ticket, simbolo, pnl, tipo_fallo, worker_culpable, descripcion, correccion_sugerida).
- **Documentación:** `docs/AUDIT_REPORT_V14_SECURITY.md` con detalle técnico completo y checklist de verificación post-despliegue.

---

## 2026-03-10 (V14 — Motor NLP Upgrade)

### Mejoras implementadas (P-1 a P-3 V14)
- **P-1** `workers/worker_nlp.py` — Modelo actualizado a `gemini-3.1-flash-lite`. Mayor velocidad y menor latencia.
- **P-2** `workers/worker_nlp.py` — `NLP_CACHE_TTL_MIN` reducido de 30 a **5 minutos**. Además: si el hash de contexto macro cambia, se fuerza re-análisis inmediato de Gemini sin esperar TTL ni cooldown (nuevo campo `_ultimo_hash` en `__init__`).
- **P-3** `core/manager.py` — `_UMBRAL_PROXIMIDAD` bajado de 0.38 a **0.15**. La IA ahora participa en el proceso de decisión con señales técnicas débiles (≥ 15% de convicción).

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
