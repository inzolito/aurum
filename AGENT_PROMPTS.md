# AGENT_PROMPTS — Guía de Prompts para Aurum

Este documento contiene prompts optimizados para que agentes de IA analicen los datos del sistema de forma estructurada y eficiente.

## 🕵️ Análisis Técnico-Cuantitativo (Lab & Producción)
Usa este prompt cuando necesites que un agente analice el archivo `remote_lab_report.md` o datos de auditoría.

**Prompt:**
> "Actúa como un analista cuantitativo (Quanteer) senior. Analiza los datos adjuntos priorizando la estructura técnica sobre el PnL. 
> 
> **Tu misión es auditar:**
> 1. **Filtro Hurst Sniper:** Identifica trades ejecutados con convicción extrema (abs > 0.80) que ignoraron el Hurst. ¿Fue una decisión acertada basada en la aceleración del precio?
> 2. **Contexto AT (EMA/RSI):** Analiza la columna 'Contexto AT'. ¿Se están tomando compras con el RSI sobrecomprado o ventas por debajo de las EMAs rápidas? Detecta divergencias técnicas.
> 3. **Estructura SMC:** Evalúa la efectividad de las señales basadas en CHoCH/BOS vs OB/FVG. ¿Qué tipo de estructura de mercado está entregando los mejores ratios de acierto?
> 4. **Análisis de Justificación (No PnL):** NO resumas la tabla de PnL. Enfócate en si la justificación de la IA capturó correctamente el cambio de estructura antes del movimiento. 
> 5. **Correlación de Volatilidad:** ¿Cómo afecta el ATR/V spread a la precisión del Sniper?
> 
> Presenta tus hallazgos como una 'Auditoría de Ingeniería de Trading' y sugiere ajustes específicos en los umbrales de disparo y pesos de workers."

---

## 🔍 Auditoría de Conexiones
Usa este prompt si sospechas de fallos en la comunicación con GCP.

**Prompt:**
> "Verifica el estado de la conexión remota con `aurum-server`. No intentes conexión directa a la IP externa. Usa el comando `uptime` a través del túnel IAP (`--tunnel-through-iap`) para validar si la instancia responde y cuánto tiempo lleva activa. Si falla, reporta el código de error de `gcloud`."

---

## 📈 Resumen Semanal de PnL
Usa este prompt para generar estadísticas rápidas de rentabilidad.

**Prompt:**
> "Calcula el ROE% acumulado y el PnL Total del archivo `remote_lab_report.md`. Separa los resultados por Laboratorio y por Activo. Identifica el 'Mejor Trade' y el 'Peor Trade' de la semana basándote en el porcentaje de retorno."

---
*Este documento crecerá con nuevos prompts a medida que identifiquemos tareas recurrentes.*
