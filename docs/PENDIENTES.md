# AURUM — TAREAS PENDIENTES
**Última actualización:** 2026-03-10

---

## P-1: Script de Administración (`aurum_admin.py`) — ALTA PRIORIDAD

**Descripción:**
Crear un script interactivo centralizado para administrar Aurum desde la terminal. Reemplaza o complementa `aurum_cli.py` con un menú orientado a operación diaria.

**Menú propuesto:**

```
============================================
   AURUM ADMIN — Panel de Administración
============================================
[1] 📊 Tabla de Votos por Obrero (todos los activos)
[2] 🚦 Estado de Procesos (Core / Hunter / Shield)
[3] 🗄️  Estado de Activos (ACTIVO / PAUSADO / SOLO_CIERRAR)
[4] ⚙️  Ver/Editar Parámetros del Sistema (pesos, umbrales)
[5] 📰 Últimas Noticias (raw_news_feed)
[6] 📋 Logs recientes
[7] 🔄 Reiniciar Bot (limpieza + relanzamiento limpio)
[0] ❌ Salir
```

**Detalle de la opción [1] — Tabla de Votos por Obrero:**

La tabla debe mostrar en tiempo real el último voto registrado de cada obrero para cada activo, consultando directamente `registro_senales` en la DB:

| Activo  | Tendencia | NLP   | Flow  | Sniper | Hurst | Volumen | Cross | **Veredicto** | Decisión           | Hace   |
|---------|:---------:|:-----:|:-----:|:------:|:-----:|:-------:|:-----:|:-------------:|--------------------|--------|
| EURUSD  | +0.60     | +0.20 | +0.15 | +0.30  | 0.612 | +0.80   | 0.00  | **+0.42**     | COMPRA_DETECTADA   | 2 min  |
| XAUUSD  | -0.40     | -0.10 | 0.00  | -0.60  | 0.482 | -0.30   | -1.00 | **-0.38**     | IGNORADO           | 5 min  |
| ...     | ...       | ...   | ...   | ...    | ...   | ...     | ...   | ...           | ...                | ...    |

- Columna **Hurst**: sin signo (0.45 = antipersistente, 0.55 = persistente, 0.50 = ruido)
- Columna **Hace**: tiempo desde el último análisis del activo
- **Colores**: verde si voto > 0, rojo si < 0, gris si = 0 (usando `rich`)
- Actualización automática cada 30 segundos (modo Live de rich) o manual con Enter

**Archivos a crear:**
- `aurum_admin.py` — script principal
- Puede reutilizar `DBConnector` y componentes de `aurum_cli.py`

---

## P-2: Solucionar duplicados por `start_bot.ps1` — ALTA PRIORIDAD

**Problema:**
`start_bot.ps1` usa `Start-Process cmd` para lanzar `main.py`, lo que crea una instancia con el Python del sistema (`python.exe`) en lugar del venv. El PID file implementado en N-3 no previene los duplicados cuando dos instancias se inician simultáneamente (race condition TOCTOU en la verificación del archivo).

**Síntomas:**
- Siempre hay 2 instancias de `main.py` corriendo (una con venv Python, una con sistema Python)
- Error de Telegram Conflict persiste

**Solución recomendada:**
1. Modificar `start_bot.ps1` para usar SIEMPRE el Python del venv y verificar PID file antes de lanzar
2. Reemplazar el check TOCTOU del PID file con un **Named Mutex de Windows** (atómico):
   ```python
   import ctypes
   mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "AurumCoreMutex")
   if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
       print("[MAIN] Ya hay una instancia corriendo. Abortando.")
       return
   ```
3. Actualizar `start_bot.ps1` para verificar el PID file antes de llamar a `Start-Process`

---

## P-3: SpreadWorker — MEDIA PRIORIDAD

**Descripción:**
Implementar el `SpreadWorker` (declarado en la arquitectura como "Faltante"). Analiza el spread bid-ask dinámico como proxy de liquidez institucional.

**Lógica propuesta:**
- Si el spread actual > 2× el spread promedio de 24h → mercado ilíquido → voto penalizador (-0.3)
- Si el spread está en niveles normales → neutral (0.0)
- Si el spread se comprime súbitamente → presión institucional → voto positivo (+0.3)

---

## P-4: VIXWorker — MEDIA PRIORIDAD

**Descripción:**
Implementar el `VIXWorker` (declarado en la arquitectura como "Faltante"). Mide volatilidad implícita del mercado.

**Alternativas sin datos externos:**
- ATR normalizado como proxy del VIX (disponible desde MT5)
- Si ATR/ATR_promedio > 1.5 → alta volatilidad → reducir tamaño de posición vía factor multiplicador

---

## P-5: Migrar logging a `logging` estándar — BAJA PRIORIDAD

**Descripción:**
Todos los módulos mezclan `print()` con `registrar_log()`. Migrar a `logging.getLogger(__name__)` para unificar nivel, formato y destino (archivo + consola + DB).

---

## P-6: Test suite con pytest — BAJA PRIORIDAD

**Descripción:**
Los archivos `tmp_*.py` son tests manuales desechables. Crear una suite formal en `/tests/` con pytest para los workers críticos (TrendWorker, NLPWorker, RiskModule).

---

*Documento mantenido por Claude Code — Anthropic. 2026-03-10*
