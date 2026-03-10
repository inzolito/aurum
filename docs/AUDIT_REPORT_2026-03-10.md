# AURUM — REPORTE DE AUDITORÍA TÉCNICA
**Fecha:** 2026-03-10
**Versión auditada:** V13.5
**Archivos revisados:** main.py, heartbeat.py, aurum_cli.py, core/manager.py, core/risk_module.py, config/db_connector.py, config/mt5_connector.py, config/telegram_bot.py, config/notifier.py, workers/ (todos)

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad |
|-----------|----------|
| CRÍTICOS (riesgo operativo/seguridad) | 6 |
| ALTOS (lógica y manejo de errores) | 9 |
| MEDIOS (calidad de código) | 5 |
| BAJOS (estilo y documentación) | 10 |
| **Total** | **30** |

---

## CRÍTICOS

### C-1: Bare Exception Handlers — Errores silenciosos
**Archivos:** `aurum_cli.py` (líneas 51, 246, 292), `heartbeat.py` (líneas 49, 55, 106), `workers/worker_nlp.py` (líneas 422, 453)
**Problema:** Bloques `except:` o `except Exception: pass` sin tipo específico devoran todas las excepciones, incluyendo `KeyboardInterrupt` y `SystemExit`. Cuando el sistema falla en estos puntos, no queda rastro alguno en logs.
**Impacto:** Imposible depurar fallos en producción. Un crash silencioso puede ejecutar una orden sin registrarla.
**Corrección:** Reemplazar por `except (psycopg2.OperationalError, ConnectionError) as e: logger.error(...)` con el tipo concreto esperado.

---

### C-2: cleanup_processes() mata procesos del sistema
**Archivo:** `aurum_cli.py` (líneas 86-99)
**Problema:** La función itera todos los procesos Python del sistema y los termina si su PID no coincide con el propio. No verifica que el proceso pertenezca a Aurum (por cmdline, nombre de script, o PID registrado).
```python
for proc in psutil.process_iter(['pid', 'name']):
    if "python" in proc.info['name'].lower() and proc.info['pid'] != current_pid:
        proc.terminate()  # Mata IDEs, tests, otros bots, herramientas del SO
```
**Impacto:** ALTO — En una máquina de desarrollo puede matar el IDE, un test runner, o procesos críticos del sistema operativo.
**Corrección:** Usar un archivo PID (`aurum.pid`) escrito al arrancar; el shutdown solo debe matar el PID registrado en ese archivo.

---

### C-3: Race condition en Survival Mode (RAM Buffer sin locks)
**Archivo:** `config/db_connector.py` (líneas 56-123)
**Problema:** El buffer de supervivencia (`self.RAM_BUFFER = defaultdict(lambda: deque(maxlen=200))`) es accedido desde el hilo principal y el hilo de Telegram sin sincronización. Bajo Python, las operaciones sobre `deque` no son atómicas en todos los contextos.
**Además:** El buffer de 200 entradas descarta silenciosamente datos al llenarse. Las operaciones ejecutadas en Survival Mode nunca se replican a la BD al reconectarse.
**Impacto:** MEDIO — Pérdida de datos de auditoría, posibles operaciones sin registro.
**Corrección:** Agregar `threading.Lock()` alrededor de escrituras al buffer. Implementar protocolo de flush al reconectar. Considerar SQLite local como buffer persistente.

---

### C-4: Null pointer en evaluación de precio (Manager.evaluar)
**Archivo:** `core/manager.py` (línea ~383)
**Problema:** El código accede a `['ask']` sobre el resultado de `obtener_precio_actual()` sin verificar que no sea `None`. MT5 puede devolver `None` si el símbolo no tiene cotización en ese momento (mercado cerrado, error de conexión).
```python
precio = self.mt5.obtener_precio_actual(...)['ask']  # KeyError si retorna None
```
**Impacto:** ALTO — Excepción no manejada en el corazón del motor de decisión. El ciclo entero del activo falla.
**Corrección:**
```python
tick = self.mt5.obtener_precio_actual(...)
if not tick:
    return {"decision": "ERROR_BROKER", "motivo": "Sin cotización MT5"}
precio = tick['ask']
```

---

### C-5: Kill-Switch con umbral inconsistente entre módulos
**Archivos:** `main.py` (línea 155), `core/risk_module.py` (línea ~163), `config/notifier.py` (línea ~182)
**Problema:** El umbral de drawdown máximo está hardcodeado en tres archivos con valores distintos ($1,000 en main.py y risk_module.py, pero el notifier menciona $2,850). Un TODO en main.py indica que fue "bajado temporalmente" pero nunca se restauró.
**Impacto:** ALTO — Inconsistencia en el circuit breaker principal. Si risk_module corta a $1,000 pero notifier notifica a $2,850, las alertas son incorrectas.
**Corrección:** Crear parámetro `GERENTE.max_drawdown_usd` en tabla `parametros_sistema` de BD y leerlo desde allí en ambos módulos.

---

### C-6: Pesos del ensemble hardcodeados (ignoran la BD)
**Archivo:** `core/manager.py` (líneas ~227-228)
**Problema:** Los pesos de votación están fijados en código:
```python
p_trend, p_nlp, p_flow, p_sniper = 0.40, 0.30, 0.15, 0.15
```
La tabla `parametros_sistema` contiene `TENDENCIA.peso_voto`, `NLP.peso_voto`, etc., pero el Manager los carga sin usarlos para el cálculo del veredicto. Cualquier cambio en BD no tiene efecto.
**Impacto:** ALTO — El sistema no puede calibrarse sin modificar código. Viola el principio de control externo que documenta la arquitectura.
**Corrección:** Leer los pesos desde `params` (ya disponible en el Manager):
```python
p_trend = float(params.get("TENDENCIA.peso_voto", 0.40))
```

---

## ALTOS

### A-1: Validación de input de usuario en Telegram Bot
**Archivo:** `config/telegram_bot.py` (líneas 51-69)
**Problema:** El símbolo ingresado por el usuario se pasa directamente a `lupa_activo()` con solo `.upper()`:
```python
await lupa_activo(update, context, text.upper())
```
No se valida contra la lista de símbolos permitidos. Cualquier string puede llegar a consultas de BD.
**Corrección:** Validar contra `SIMBOLOS_PERMITIDOS` antes de procesar.

---

### A-2: API Key de Gemini sin validación al arrancar
**Archivo:** `workers/worker_nlp.py` (líneas 28-31)
**Problema:** `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")` se acepta como string vacío sin advertencia. El worker falla silenciosamente en runtime con un error genérico, sin indicar que el problema es la clave ausente.
**Corrección:** Validar en el constructor de NLPWorker y registrar error crítico si la clave es vacía.

---

### A-3: Cálculo de Hurst con datos insuficientes sin advertencia
**Archivo:** `workers/worker_hurst.py` (líneas 88-95)
**Problema:** Acepta tan solo 100 velas (cuando requiere 1024) y calcula Hurst de todas formas. El resultado de Hurst con <512 muestras no es estadísticamente válido, pero el Manager lo recibe sin indicador de calidad.
**Corrección:** Incluir campo `data_quality: "LOW"` en el resultado cuando se opera con datos insuficientes. El Manager debe descontar el peso de Hurst en ese caso.

---

### A-4: Valores NaN no detectados en VolumeWorker
**Archivo:** `workers/worker_volume.py` (líneas 59-60)
**Problema:** Solo verifica array vacío o todo-ceros. Arrays con NaN pasan a `np.histogram()` y producen resultados incorrectos o excepciones.
**Corrección:** Agregar `if np.isnan(precios).any(): return self._datos_vacios()`

---

### A-5: Blacklist de activos hardcodeada en DBConnector
**Archivo:** `config/db_connector.py` (líneas ~221, 241-252)
**Problema:** XAUUSD y XAGUSD están excluidos por código, no por datos. La lista de fallback hardcodeada de activos (líneas 241-252) está desactualizada respecto a la ontología actual (9 activos).
**Corrección:** Mover la exclusión a un campo `estado_operativo = 'EXCLUIDO'` en la tabla `activos`. La lista de fallback debe sincronizarse con la ontología o eliminarse.

---

### A-6: Import de MetaTrader5 dentro del loop principal
**Archivo:** `main.py` (líneas 151, 184)
**Problema:** `import MetaTrader5 as mt5_api` y `import MetaTrader5 as mt5_lib` ocurren dentro del `while self.running:` en cada iteración del ciclo. Python cachea imports, pero es una mala práctica y agrega overhead de búsqueda en tabla de módulos en cada ciclo.
**Corrección:** Mover todos los imports al tope del archivo.

---

### A-7: Sin graceful shutdown para hilo de Telegram
**Archivo:** `main.py` (líneas 96-99)
**Problema:** El hilo de Telegram se inicia como `daemon=True`. Al invocar `engine.stop()`, el hilo se mata abruptamente sin que el bot de Telegram pueda terminar sus handlers en curso o enviar un mensaje de "sistema apagado".
**Corrección:** Implementar un `threading.Event` de parada que el bot de Telegram monitoree para cerrarse limpiamente.

---

### A-8: Horario de Gatekeeper usa hora local sin timezone explícita
**Archivo:** `main.py` (líneas 118-126)
**Problema:** `datetime.now()` retorna la hora local de la máquina. Si el servidor se ejecuta en un VPS con timezone UTC (o diferente a América/Santiago), el Gatekeeper de fin de semana se activará en horas incorrectas.
**Corrección:** Usar `datetime.now(tz=pytz.timezone('America/Santiago'))` de forma explícita.

---

### A-9: SpreadWorker y VIXWorker no están en el código fuente
**Arquitectura:** `AURUM_ARCHITECTURE.md` declara 8 obreros, pero los archivos `worker_vix.py` y `worker_spread.py` no existen en el directorio `workers/`.
**Impacto:** El Manager recibe "Dato Faltante" para esos dos obreros en cada ciclo. La matriz 8x9 declarada en la ontología no está implementada.
**Corrección:** Implementar ambos workers o actualizar la ontología para reflejar los 6 workers reales.

---

## MEDIOS

### M-1: Dos definiciones del decorador `survival_shield`
**Archivo:** `config/db_connector.py` (líneas ~12-36 y ~65-91)
El decorador existe a nivel de módulo Y como método de clase con el mismo nombre. Esto es confuso y el decorador de clase-método no puede envolver métodos de instancia correctamente.
**Corrección:** Eliminar la definición a nivel de módulo y usar solo la de clase.

---

### M-2: Thresholds mágicos repetidos en Manager
**Archivo:** `core/manager.py` (líneas ~195, 311, 323)
Los valores `0.38`, `0.45` y `0.30` aparecen múltiples veces sin constantes nombradas. Si se ajusta un umbral, hay que buscar todas las ocurrencias.
**Corrección:**
```python
UMBRAL_PROXIMIDAD  = 0.38
UMBRAL_OPORTUNIDAD = 0.30
UMBRAL_ZONA_GRIS   = 0.45
```

---

### M-3: Mezcla de `print()` y `registrar_log()` sin logging unificado
**Archivos:** Todos los módulos
El sistema usa `print()` para salida de consola y `self.db.registrar_log()` para persistencia en BD, pero no hay un nivel de severidad uniforme. Algunos prints importantes (errores de precio) nunca llegan a la BD.
**Corrección:** Adoptar `logging` estándar de Python con handlers: consola + BD.

---

### M-4: DataFrames grandes sin cleanup explícito
**Archivo:** `config/mt5_connector.py`
Se crean DataFrames de 1000+ filas en cada ciclo de análisis sin `del df` o liberación explícita. En un sistema 24/7 con 9 activos esto puede acumular presión de memoria.
**Corrección:** Agregar `del df` después de extraer los datos necesarios, o usar slices directamente sin materializar el DataFrame completo.

---

### M-5: Archivos temporales de debugging en el repositorio
**Root del proyecto:** `tmp_debug_nlp_raw.py`, `tmp_final_table.py`, `tmp_force_nlp.py`, `fix_db.py`, `fix_db2.py`, `fix_db3.py`, `fix_db_real.py`, `audit_*.py`, `check_*.py`, etc.
El repositorio contiene ~20 scripts temporales de diagnóstico mezclados con el código de producción. Esto dificulta la navegación y puede exponer lógica de acceso a BD en texto plano.
**Corrección:** Mover a `tools/` o `scripts/dev/` y excluir del `main` branch. Agregar a `.gitignore` el prefijo `tmp_*` y `fix_*`.

---

## BAJOS

### B-1: README.md desactualizado
Describe la arquitectura de 3 obreros (V3) cuando el sistema tiene 6 implementados (V13.5) y documenta 2 más no implementados (VIX, Spread). Los pesos documentados no coinciden con el código.

### B-2: AURUM_ARCHITECTURE.md incompleto
El documento es de 35 líneas y no cubre el Scheduler, el protocolo de Survival Mode, el esquema de BD actual, ni la integración Telegram.

### B-3: Mensajes de error con formato inconsistente
Coexisten `[DB] ERROR:`, `[GERENTE] ERROR:`, `[RISK] BLOQUEO:` con y sin emoji. Dificulta el parsing de logs y la creación de alertas automáticas.

### B-4: Sin type hints en return de workers
Varios workers no tienen `-> Dict[str, Any]` en sus métodos `analizar()`, dificultando el autocompletado y la detección de errores de integración.

### B-5: `news_hunter.py` sin revisar en esta auditoría
El archivo existe (confirmado en git status) y es referenciado en el ciclo principal, pero su lógica interna no fue auditada. Se recomienda auditoría específica.

### B-6: `run_news_radar.bat` no versionado correctamente
Archivo de lanzamiento de Windows en estado `??` (untracked), lo que indica que no está bajo control de versiones aunque es parte del flujo operativo.

### B-7: Sin `.env.example`
Las variables de entorno requeridas (`MT5_LOGIN`, `GEMINI_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `DB_*`) no están documentadas en ningún archivo de referencia. Un nuevo deploy falla silenciosamente.

### B-8: `ciclos_hora` y `ordenes_hora` sin uso efectivo
**Archivo:** `main.py` (líneas 106-107, 179-182)
Se acumulan contadores por hora pero se reinician sin ninguna acción ni log. El código es inerte.

### B-9: Reconexión MT5 sin backoff
**Archivo:** `main.py` (líneas 184-193)
Si MT5 falla, se reintenta en el siguiente ciclo (60s). No hay backoff exponencial ni límite de reintentos antes de notificar por Telegram.

### B-10: Sin tests automatizados para workers críticos
Los archivos `test_*.py` existen pero son scripts manuales, no suites pytest. No hay CI/CD que ejecute regresiones antes de deployar cambios al motor de producción.

---

## PRIORIDAD DE CORRECCIÓN SUGERIDA

### Semana 1 (Antes de siguiente sesión de trading)
1. C-4: Agregar null-check en precio MT5
2. C-2: Reemplazar cleanup_processes() con PID file
3. C-5: Unificar umbral de drawdown en BD
4. C-3: Agregar lock al RAM buffer de Survival Mode
5. A-6: Mover imports de MT5 fuera del loop

### Semana 2
6. C-6: Leer pesos del ensemble desde BD
7. A-8: Corregir timezone en Gatekeeper
8. A-9: Implementar VIXWorker y SpreadWorker (o actualizar ontología)
9. M-5: Limpiar archivos temporales del repo
10. B-7: Crear `.env.example` documentado

### Mes 1
11. Migrar a `logging` estándar con handler a BD
12. Refactorizar umbrales mágicos a constantes
13. Implementar graceful shutdown para Telegram
14. Actualizar README y ARCHITECTURE al estado real V13.5
15. Agregar suite de tests pytest para workers críticos

---

*Auditoría realizada con Claude Code — Anthropic. Revisión manual recomendada para news_hunter.py y módulos de ejecución en MetaTrader5.*
