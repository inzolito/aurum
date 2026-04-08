# Criterios de Decisión de Entrada (Aurum Gerente V19.1)

El archivo `core/manager.py` actúa como un "Comité de Sabios", consultando a diferentes "Obreros" (Workers) de forma secuencial y estructurada antes de enviar una orden al broker.

A continuación, la tabla detallada del flujo exacto de análisis que el bot realiza para cada activo:

## 1. Escudo de Seguridad y Conectividad (Bloqueantes)
Si alguna de estas condiciones falla, el análisis se detiene inmediatamente y el activo se descarta para este ciclo.

| Módulo / Filtro | Descripción del Análisis | Decisión / Consecuencia |
| :--- | :--- | :--- |
| **RiskModule** | Verifica exposición de la cuenta: Si flotante negativo > drawdown máximo, o si ya hay una posición abierta para ese activo (Anti-duplicados). | Bloqueo (`BLOQUEO_DRAWDOWN` o `BLOQUEO_EXPOSICION`) |
| **Hibernación** | Protocolo Anti-Loop: Si un activo arrojó error fatal en el broker (ej. 10018), se congela por 60 min. | Bloqueo por tiempo |
| **Market Watch** | Chequea el "Trade Mode" del broker para ver si el mercado está cerrado o deshabilitado temporalmente. | Bloqueo (`FUERA_DE_HORARIO`) |
| **Veto de Volatilidad**| Mide el ATR actual en tiempo real frente al histórico. Si el mercado está estallando (volatilidad actual > 200% de la media temporal). | Bloqueo (`MERCADO_VOLATIL`) |

## 2. El Veredicto Base (La Ecuación Principal)
Si supera los escudos, se piden los votos de los tres pilares fundamentales. Cada voto es un valor entre `-1.0` (Venta Fuerte) y `+1.0` (Compra Fuerte).

| Obrero Principal | Peso Asignado | ¿Qué analiza exactamente? |
| :--- | :--- | :--- |
| **TrendWorker** | **50%** (TENDENCIA) | Analiza Price Action de corto plazo (velas 1M), evaluando el precio frente a cruces de **EMA 9 y EMA 21**, la compresión de medias relativas y el momento en oscilador **RSI (14)**. |
| **NLPWorker** | **30%** (INTELIGENCIA) | Usa IA (Gemini) para procesar las **10 últimas noticias globales** junto a los regímenes macroeconómicos. Genera un análisis semántico del impacto direccional. |
| **StructureWorker** | **20%** (FRANCOTIRADOR)| Busca patrones SMC *(Smart Money Concepts)*: Rompimientos de estructura (BOS), Gaps de valor razonable (FVG) y espera a que el precio testee los "Order Blocks" exactos. |

*Fórmula actual: Veredicto = (Trend × 0.50) + (NLP × 0.30) + (Sniper × 0.20)*

## 3. Ajustes y Penalizaciones Secundarias (Micro-Ajustes)
El `Veredicto` principal es modificado (sumando o restando fuerza) por métricas ambientales del mercado.

| Obrero Secundario | Impacto en el Veredicto | Descripción de la métrica |
| :--- | :--- | :--- |
| **SpreadWorker** | Penalización | Rastrea el spread actual vs el spread normal. Si es excesivo, debilita la fuerza del veredicto empujándolo hacia 0. |
| **VIXWorker** | Penalización | Reduce la agresividad direccional en escenarios donde el índice de miedo bursátil o el ATR porcentual están anormalmente altos. |
| **CrossWorker** | +/- 15% (Ajuste) | Mide divergencias inter-mercado rastreando la fuerza del Dolar Index (DXY). Promueve o penaliza trades Forex según la reacción opuesta del DXY. |
| **MacroWorker** | +/- 20% (Ajuste) | Contexto estructural de muy largo plazo (Regímenes activos). Empuja a favor de las macrotendencias globales. |

## 4. Jueces Supremos y Barreras Finales
Antes de disparar, el veredicto consolidado enfrenta al Tribunal Final que busca atrapar "Falsos Positivos".

| Juez / Evento | Condición para Bloquear | Umbrales de Excepción |
| :--- | :--- | :--- |
| **Juez Divergencia** | Bloqueo absoluto si la orden de Tendencia (+1.0) y de la caja de IA NLP (-1.0) son diametralmente opuestas. | Ninguna, el bloqueo es definitivo (`SEÑALES_DIVIDIDAS`). |
| **Juez Hurst (Ruido)**| Bloquea si el mercado cae en régimen matricial `ANTIPERSISTENTE` (100% de oscilación aleatoria en ruido blanco de alta frecuencia). | Se ignora si el veredicto del motor supera `0.55` (convicción fuerte). |
| **Juez F1 (Agotamiento)**| Bloquea entradas a destiempo en tendencias ya sobre-extendidas (Trend > 0.85) bajo rastro fractal `PERSISTENTE`. | Se ignora si el veredicto es extremadamente claro (`>= 0.60`). |

## 5. El Disparo
Una vez pasado todo esto, si el **Veredicto Final absoluto `(e.g., 0.48)` ** es mayor o igual al parámetro **`GERENTE.umbral_disparo`** (generalmente `0.40` o `0.45` por defecto), el Gerente ordena la ejecución del trade a la API MT5 considerando gestión de riesgo en lote.
*(Nota: Si CrossWorker detecta "Black Swan", el umbral se eleva automáticamente a 0.60).*
