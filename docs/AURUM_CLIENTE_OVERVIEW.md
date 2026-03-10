# AURUM — Sistema de Trading Algorítmico
## Guía para el Cliente

---

## ¿Qué es Aurum?

Aurum es un sistema de trading algorítmico completamente automatizado. Opera en los mercados financieros globales (metales preciosos, índices bursátiles, forex y energías) sin intervención humana directa, tomando decisiones de compra y venta basadas en la convergencia de tres tipos de inteligencia: análisis técnico, sentimiento de noticias con IA, y flujo de órdenes institucional.

El sistema elimina el factor emocional del trading. No tiene miedo, no tiene codicia. Sigue reglas matemáticas estrictas.

---

## Arquitectura General: Cómo Funciona

### El Modelo de Votación

Aurum no depende de un único indicador. En cambio, utiliza un **sistema de votación ponderada** (Ensemble Model): múltiples motores de análisis independientes emiten un voto entre -1.0 (venta fuerte) y +1.0 (compra fuerte), y el sistema solo opera cuando hay suficiente consenso.

```
Veredicto Final = (Voto Técnico × 40%) + (Voto IA/Noticias × 30%) + (Voto Flujo × 15%) + (Voto Sniper × 15%)
```

Si el veredicto absoluto no supera el umbral configurado (ej. ±0.65), la operación se cancela. Se prefiere no operar a operar sin convicción.

---

## Los 6 Motores de Análisis (Obreros)

Cada obrero analiza los 9 activos de forma independiente en cada ciclo (cada 60 segundos).

### 1. TrendWorker — Análisis de Tendencia
Estudia la dirección del mercado usando medias móviles exponenciales (EMAs). Detecta cruces de tendencia y valida que el movimiento tenga volumen real detrás (no es una señal falsa). Responde la pregunta: **¿hacia dónde va el mercado en macro?**

### 2. NLPWorker — Inteligencia Artificial sobre Noticias
Es el cerebro macroeconómico del sistema. Usa Google Gemini (IA generativa) para analizar el impacto de eventos del mundo real sobre cada activo. No evalúa noticias aisladas: mantiene un mapa de **regímenes activos** con tres tipos de fuerzas:

| Tipo | Duración | Ejemplo |
|------|----------|---------|
| Régimen Macro | Meses/Años | Ciclo de recortes de tasas de la Fed |
| Catalizador | Días (con cuenta regresiva) | Resultados trimestrales, elecciones |
| Choque Geopolítico | Instantáneo | Conflicto armado, evento inesperado |

Cada evento tiene un **ciclo de vida** (formándose → activo → post-clímax → disipado). El sistema ajusta su sesgo según la fase del evento, no solo si ocurrió o no.

### 3. FlowWorker — Flujo de Órdenes Institucional
Accede en tiempo real al libro de órdenes (Level 2) de MetaTrader 5. Calcula el desequilibrio entre órdenes de compra y venta institucionales. Detecta "muros de liquidez" — zonas donde grandes actores han colocado órdenes masivas que actuarán como soporte o resistencia. Responde: **¿qué están haciendo los institucionales ahora?**

### 4. SniperWorker — Entrada Quirúrgica (Smart Money Concepts)
Una vez que los otros obreros confirman dirección, el Sniper busca el punto de entrada óptimo. Detecta estructuras de mercado como Order Blocks (zonas de acumulación institucional) y Fair Value Gaps (desequilibrios de precio). El objetivo es no entrar "en cualquier punto", sino en el momento más eficiente. Responde: **¿cuál es el precio exacto de entrada?**

### 5. HurstWorker — Filtro de Fractalidad
Calcula el **exponente de Hurst** sobre el historial de precios (1024 velas). Este coeficiente mide si el mercado está en tendencia persistente (H > 0.5), en ruido aleatorio (H ≈ 0.5), o en reversión (H < 0.5). Actúa como filtro de calidad: si el mercado es puro ruido, Aurum reduce su convicción aunque los otros obreros voten fuerte.

### 6. StatesWorker — Memoria de Largo Plazo
Mantiene el contexto de eventos geopolíticos y macroeconómicos activos. Provee al NLPWorker el mapa de regímenes vigentes, asegurando que las decisiones reflejen el estado actual del mundo, no solo el último tick de precio.

---

## Los 9 Activos Monitoreados

| Categoría | Activos |
|-----------|---------|
| Commodities | Oro (XAUUSD), Petróleo WTI (XTIUSD) |
| Índices | Dow Jones (US30), S&P 500 (US500), Nasdaq (USTEC) |
| Forex | EUR/USD, GBP/USD, USD/JPY, GBP/JPY |

---

## El Gerente: La Toma de Decisión

El Gerente es el meta-algoritmo central. Recibe los votos de los 6 obreros y ejecuta el siguiente proceso en cada ciclo:

**Fase 1 — Votación:** Calcula el veredicto ponderado. Si no supera el umbral, cancela y espera al próximo ciclo.

**Fase 2 — Filtros de Riesgo:** Si hay señal, pasa por cuatro filtros de seguridad antes de cualquier ejecución:
- **Filtro de Estado:** ¿Está el activo habilitado para operar?
- **Filtro de Horario:** ¿Estamos dentro de la ventana operativa de este activo?
- **Filtro de Correlación:** ¿Ya tenemos demasiada exposición en este sector?
- **Filtro de Régimen Macro:** ¿El macro confirma o contradice la señal técnica?

**Fase 3 — Ejecución con Gestión de Capital:**
- Calcula el **lotaje exacto** para que una pérdida en el Stop Loss equivalga al % de riesgo configurado (ej. 1.5% del balance).
- Coloca el Stop Loss basado en volatilidad real (ATR) o en el muro de Order Flow más cercano.
- El Take Profit se calcula como múltiplo del Stop Loss (ej. 2.0× = ratio riesgo/beneficio de 1:2).
- Ejecuta la orden en MT5 con tipo `IOC` (Immediate or Cancel): si no se obtiene el precio pedido, la orden se cancela en lugar de ejecutarse a un precio peor.

**Justificación obligatoria:** Cada operación que el Gerente abre queda registrada con un párrafo explicativo generado por IA describiendo exactamente por qué se ejecutó. No hay "caja negra".

---

## Infraestructura Tecnológica

```
[ Máquina Local / Windows ]          [ Google Cloud Platform ]
        |                                       |
  MetaTrader 5 ←─── Motor Aurum ────────── PostgreSQL 15
  (Broker / Ejecución)   |              (Datos, Parámetros, Logs)
                         |
                    Telegram Bot ←──── Tú (Control en tiempo real)
```

- **Ejecución:** Local (Windows + MetaTrader 5), porque las órdenes deben ejecutarse a través del broker.
- **Inteligencia y Datos:** En la nube (GCP), accesible desde cualquier lugar.
- **Control:** A través de Telegram. Puedes consultar el estado, pausar activos, ver posiciones abiertas, y recibir alertas sin tocar la máquina.

---

## Sistemas de Seguridad

### Kill-Switch de Drawdown
Si el balance de la cuenta cae por debajo del umbral configurado, el sistema cierra todas las posiciones automáticamente y entra en modo hibernación hasta el día siguiente. No se puede perder más allá de lo definido.

### Verificación de Cuenta
Al arrancar, Aurum verifica que está conectado a la cuenta MT5 correcta. Si detecta una cuenta diferente a la configurada, se autodestruye antes de ejecutar nada.

### Gatekeeper de Fin de Semana
Los mercados de forex cierran el viernes por la tarde. Aurum detecta automáticamente el fin de semana (viernes 18:00 — domingo 18:00) y entra en modo vigilancia: deja de analizar señales operativas pero sigue monitoreando noticias y el estado del sistema.

### Survival Mode
Si la conexión a la base de datos en la nube falla, el sistema continúa operando con los últimos parámetros conocidos y un buffer local temporal. No se cae por una desconexión temporal de internet.

---

## Control y Monitoreo vía Telegram

El bot de Telegram es la interfaz de control. Desde cualquier dispositivo puedes:

- Ver el estado del sistema en tiempo real (activo, en vigilancia, pausado, error).
- Consultar las posiciones abiertas con su P&L actual.
- Hacer un análisis ("lupa") de cualquier activo específico.
- Recibir alertas automáticas de órdenes ejecutadas, errores críticos, y reportes horarios.
- Pausar o reactivar activos específicos.

---

## Ciclo de Vida de una Operación (Ejemplo)

```
1. [00:00] Ciclo #142 inicia — se analizan los 9 activos

2. [00:01] XAUUSD analizado:
   - TrendWorker: +0.70 (tendencia alcista fuerte, EMA rápida cruzó arriba)
   - NLPWorker:   +0.40 (régimen "Recortes Fed" activo, sesgo pro-oro)
   - FlowWorker:  +0.32 (muro de compras institucional en $2,025)
   - SniperWorker: +0.60 (Order Block identificado en $2,027)
   - HurstWorker: H=0.58 (mercado en tendencia, señal válida)

   Veredicto: +0.72 ✓ (supera umbral de +0.65)

3. Filtros:
   ✓ XAUUSD en estado ACTIVO
   ✓ Hora: 00:01 UTC (dentro de ventana operativa)
   ✓ Exposición en commodities: 0 posiciones abiertas
   ✓ Régimen macro confirma dirección

4. Ejecución:
   Balance: $5,000 | Riesgo: 1.5% = $75
   SL: 15 pips → Lotaje: 0.50 lotes
   TP: 30 pips (ratio 1:2)
   Orden enviada a MT5 → Ticket #4521862

5. Registro:
   - Operación guardada en BD con ticket, precio, SL, TP, lotaje
   - Justificación IA: "Compra 0.50 lotes XAUUSD. Veredicto +0.72.
     NLP aporta +0.40 por régimen Fed dovish activo. Flow detectó
     muro institucional en 2025.00. Riesgo controlado al 1.5%."
   - Notificación Telegram enviada
```

---

## Métricas de Rendimiento que Aurum Rastrea

| KPI | Descripción |
|-----|-------------|
| Win Rate | % de operaciones que alcanzaron Take Profit |
| R/R Realizado | Ganancia promedio / Pérdida promedio |
| ROE % | PnL de la operación / Balance al momento de entrada |
| Duración Media | Tiempo promedio entre apertura y cierre |

Todas las métricas se calculan en tiempo real desde la base de datos en la nube y pueden consultarse por activo, por período, o por versión del sistema.

---

## Control de Versiones y Calibración

Aurum está diseñado para mejorar continuamente sin riesgo. El sistema mantiene un historial de versiones de parámetros:
- Cada conjunto de parámetros (pesos, umbrales, ratios) tiene una versión identificada.
- Todas las operaciones se vinculan a la versión que las tomó.
- Si una nueva calibración tiene peor rendimiento, se puede hacer **rollback instantáneo** a la versión anterior desde Telegram o el Dashboard.

---

## Lo que Aurum NO hace

- No promete rendimientos. Los mercados financieros son intrínsecamente inciertos.
- No opera sin validación de riesgo. Cada operación pasa por cuatro filtros antes de ejecutarse.
- No ignora el contexto macro. Una señal técnica perfecta se cancela si el régimen macroeconómico activo la contradice.
- No opera en fin de semana cuando los mercados están cerrados.

---

*Documentación generada: 2026-03-10 | Versión del sistema: Aurum OMNI V13.5*
