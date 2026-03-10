# AURUM OMNI - ARQUITECTURA DEL SISTEMA (ONTOLOGÍA)

**Repositorio oficial:** https://github.com/inzolito/aurum.git

Esta documentación define la jerarquía y estructura operativa de Aurum, estableciendo una distinción clara entre los módulos de análisis (Obreros) y los instrumentos de mercado (Activos).

## 1. DEFINICIÓN DE OBREROS (The Workers - 8 Unidades)
Los obreros son módulos de lógica y software independientes cuya función es procesar datos específicos para generar un veredicto. **NO SON ACTIVOS.**

| Obrero | Función Principal |
| :--- | :--- |
| **TrendWorker** | Análisis de dirección técnica macro (Tendencias). |
| **NLPWorker** | Análisis de sentimiento de noticias mediante IA (Gemini). |
| **FlowWorker** | Seguimiento de volumen e intención institucional (Order Flow). |
| **SniperWorker** | Ejecución de entradas precisas (SMC / Order Blocks). |
| **HurstWorker** | Filtro de ruido, fractalidad y persistencia del mercado. |
| **VIXWorker** | Análisis de volatilidad y niveles de miedo/pánico. |
| **SpreadWorker** | Control de fricción y costos operativos del broker. |
| **StatesWorker** | Memoria de contextos de largo plazo (IA, Geopolítica, Regímenes). |

## 2. DEFINICIÓN DE ACTIVOS (The Assets - Símbolos)
Los activos son los instrumentos financieros procesados por la cuadrilla de obreros. Estos se dividen en tres categorías principales:

*   **Commodities:** XAUUSD (Oro), XTIUSD (Petróleo).
*   **Índices:** US30 (Dow Jones), US500 (S&P 500), USTEC (Nasdaq).
*   **Forex:** EURUSD, GBPUSD, USDJPY, GBPJPY.

## 3. MATRIZ DE RELACIÓN (Operativa Cuadrilla)
La arquitectura dicta que **cada ACTIVO es analizado por los 8 OBREROS simultáneamente**.

### Reglas de Veredicto:
1.  **Sincronización:** Para que el Gerente tome una decisión, debe recibir los datos de los 8 obreros sobre el activo en cuestión.
2.  **Transparencia de Datos:** La ausencia de datos de un obrero para un activo específico se reporta como **'Dato Faltante'**.
3.  **No Interrupción:** Un 'Dato Faltante' no se considera un error del sistema que deba detener el monitoreo, sino un vacío de información que el Gerente debe ponderar.

---
*Ultima actualización de ontología: 2026-03-08*
