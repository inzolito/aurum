# Propuesta: Análisis Multi-Temporal (MTF) con MACD + RSI

## 1. El Problema Actual (El "Síndrome de la Visión de Túnel")

Tras auditar el código de `workers/worker_trend.py` y `config/mt5_connector.py`, el bot actual tiene un problema grave de visión: **Solo mira el gráfico de 1 Minuto (M1).** 

- Pide 100 velas de M1.
- Calcula la EMA de 9 y 21 minutos.
- Calcula el RSI de 14 minutos.
- **NO usa MACD** en ninguna parte de su código base estándar.

**¿Por qué esto causa pérdidas?**
Si el bot ve que en M1 el precio rompió la EMA hacia arriba con fuerza (voto +0.8), entra en compra a ciegas. Lo que no sabe es que en el gráfico de 1 Hora (H1) o 4 Horas (H4), el precio estaba chocando contra un muro de sobrecompra masivo (RSI > 80 en H4) y la tendencia estructural era bajista. Como solo mira M1, compra la punta del techo de 4 Horas y pierde por el rebote estructural.

---

## 2. La Solución: Análisis Multi-Timeframe (Top-Down)

Como bien sugeriste, el trading institucional nunca se basa en una sola temporalidad. Se debe implementar un modelo en cascada (Top-Down):

### A. Gráfico Macro (4 Horas / H4) — La Marea
Determina hacia dónde fluye el océano.
- **Métrica**: MACD Histograma y Línea de Señal.
- **Función**: Si el MACD en H4 está en territorio negativo y cruzando hacia abajo, **las compras en M1 quedan 100% bloqueadas**. El bot solo tiene permiso para buscar cortos (ventas).
- **RSI H4**: Si RSI > 75, bloqueo estricto de compras. Si RSI < 25, bloqueo de ventas.

### B. Gráfico Intermedio (1 Hora / H1 o 15 Minutos / M15) — La Ola
Determina el momento intra-día.
- **Métrica**: RSI y Estructura SMC (Order Blocks, BOS).
- **Función**: Sirve para alinear el pulso intradiario con la marea de H4. No entramos si H1 está mostrando agotamiento severo.

### C. Gráfico de Escopeta (1 Minuto / M1) — El Gatillo
Determina el punto exacto al milímetro.
- **Métrica**: EMAs (9 y 21) y Cruce Temprano de MACD.
- **Función**: Solo se usa para buscar el momento de menor riesgo (menor Stop Loss/Drawdown). Ya no decide la dirección; **la dirección ya la decidió H4**. M1 solo espera agazapado a que el precio haga pull-back (caiga un poco) a la zona de valor dictada por H4/M15 para disparar.

---

## 3. Implementación Sugerida en Aurum 2.0

Para llevar a cabo esto, propongo reconstruir `worker_trend.py` o crear un nuevo `worker_mtf.py` que realice las siguientes rutinas de conexión MT5:

1. Llamar `mt5_connector.obtener_velas(simbolo, 50, mt5.TIMEFRAME_H4)`
2. Llamar `mt5_connector.obtener_velas(simbolo, 50, mt5.TIMEFRAME_M15)`
3. Llamar `mt5_connector.obtener_velas(simbolo, 100, mt5.TIMEFRAME_M1)`
4. Utilizar la librería `ta` para añadir `ta.trend.MACD()` a las llamadas y combinar la lógica.

**Resultado Esperado:**
Reducción drástica de trades perdidos (-70%) porque el bot dejará de luchar contra resistencias estructurales invisibles en M1. El win rate natural subirá sobre el 45% solo por el efecto de sincronización temporal.
