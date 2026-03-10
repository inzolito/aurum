# Aurum

**Repositorio oficial:** https://github.com/inzolito/aurum.git
**Versión actual:** V13.5 (Aurum OMNI)

---

## 1. Descripción y Propósito del Sistema

El Proyecto Aurum es un sistema de trading algorítmico institucional automatizado (AAS). Su objetivo es operar en los mercados financieros (con foco inicial en XAUUSD y XAGUSD, escalable a Energías, Índices y Acciones) eliminando el sesgo emocional humano.

Utiliza una arquitectura de "Modelo Ensemble" (Votación Heurística). El sistema no depende de un único indicador técnico, sino que calcula una probabilidad de éxito basada en la convergencia de tres dimensiones independientes: Acción del Precio, Flujo de Órdenes Institucional (Order Flow) y Sentimiento Macroeconómico (NLP).

---

## 2. Arquitectura de Hardware y Despliegue (Modelo de Datos 100% Nube)

El sistema ha evolucionado hacia un modelo donde la máquina local es puramente un nodo de ejecución, mientras que la inteligencia y los datos residen en la nube.

**Nodo de Ejecución (Local/Windows):**
- **Hardware:** Máquina local (Surface Pro 5 o similar).
- **Software Core:** MetaTrader 5 (MT5).
- **Procesos:** Los scripts Python (Manager + Obreros) se conectan a la nube para obtener parámetros y contexto antes de ejecutar órdenes en MT5.

**Cerebro de Datos y Control (Google Cloud Platform - GCP):**
- **Hardware:** Instancia e2-micro con PostgreSQL 15.
- **Base de Datos:** Centraliza parámetros, estados, señales y noticias.
- **Ventaja:** Permite el control del bot desde cualquier interfaz (Telegram/Frontend) sin depender de archivos locales.

---

## 3. Topología Lógica del Software (Micro-Procesos Python)

El código debe estructurarse de forma modular. Un fallo en un módulo no debe detener el sistema, solo abortar la operación actual.

### 3.1. Nivel 1: Los "Obreros" (Generadores de Votos)

Scripts independientes que evalúan el mercado en bucle. Su salida siempre debe ser un valor flotante normalizado entre -1.0 (Venta Fuerte) y +1.0 (Compra Fuerte).

**Obrero 1: Tendencia y Price Action (`worker_trend.py`)**
- Input: Consulta la tabla `velas_1m` en PostgreSQL (OHLCV).
- Lógica: Calcula Medias Móviles Exponenciales (ej. EMA Rápida y EMA Lenta). Detecta cruces direccionales. Valida la fuerza del movimiento exigiendo que el volumen de la vela de ruptura sea superior a la media de las últimas N velas.

**Obrero 2: Sistema de Regímenes Macro y Vectorización de Contexto (`worker_nlp.py`)**

El sistema ya no evalúa "noticias" aisladas, sino que opera bajo la influencia de fuerzas macroeconómicas superpuestas. El Obrero NLP consulta la tabla `regimenes_mercado` para calcular un "Vector de Fuerza Combinada" antes de emitir su voto.

**Clasificación de las Fuerzas (Taxonomía):**

| Tipo | Duración | Descripción | Ejemplo |
|---|---|---|---|
| `REGIMEN_MACRO` | Largo plazo (meses/años) | Fuerzas tectónicas de impacto constante y baja intensidad. | Ciclos de recorte de tasas de la FED. |
| `CATALIZADOR` | Con cuenta regresiva | Eventos con fecha exacta que generan expectación semanas antes. | Earnings, Halvings, Elecciones. |
| `CHOQUE_GEOPOLITICO` | Repentino | Eventos violentos de pico inmediato y masivo. | Estallido de guerras. |

**Máquina de Estados del Evento (Ciclo de Vida):**

| Estado | Descripción |
|---|---|
| `FORMANDOSE` | El mercado anticipa el evento (ej. faltan 14 días para Earnings). |
| `ACTIVO` | El evento está ocurriendo y ejerce su máxima fuerza. |
| `POST_CLIMAX` | El evento ya ocurrió. El algoritmo asume reversión temporal ("vender la noticia" / toma de ganancias). |
| `DISIPADO` | El evento ya no afecta al mercado y es ignorado en el cálculo vectorial. |

**Matemática de Superposición (Suma Vectorial):**

Si existen múltiples eventos activos, el Obrero NLP extrae el `impacto_base` de cada uno para el activo específico y los suma:

```
Voto_NLP_Final = Impacto_Regimen + Impacto_Catalizador + Impacto_Choque
```

**Obrero 3: Microestructura / Order Flow (`worker_flow.py`)**
- Input: Extrae el Limit Order Book (Level 2) directamente de la memoria de MT5 (usando la función `mt5.market_book_get()`).
- Lógica: Calcula el "Desequilibrio del Libro" (Order Book Imbalance). Compara el volumen total de órdenes Bid (Compra) vs Ask (Venta) en los X niveles de precio más cercanos. Identifica "Muros de Liquidez" institucionales que actuarán como soporte o resistencia magnética.

### 3.2. Nivel 2: El Gerente (Meta-Algoritmo y Ejecución)

Script principal (`manager_core.py`) que orquesta la toma de decisiones. Opera en un bucle continuo o reacciona a eventos (ticks).

**Fase A: Recopilación y Votación Ponderada**

El Gerente solicita el voto actual de los tres Obreros y realiza el cálculo de Suma Producto utilizando los pesos extraídos de la tabla `parametros_sistema` de PostgreSQL:

```
Veredicto = (Voto_Tendencia × Peso_Tendencia) + (Voto_NLP × Peso_NLP) + (Voto_Flow × Peso_Flow)
```

Si el Veredicto absoluto no supera el parámetro `umbral_disparo` (ej. ≥ +0.65 para compra, ≤ -0.65 para venta), la operación se CANCELA por exceso de "ruido" o falta de consenso, registrando el evento en `registro_senales`.

**Fase B: Filtros de Riesgo Institucional (Macro Regimes)**

Si el Veredicto supera el umbral, el Gerente debe pasar la señal por los filtros de seguridad antes de ejecutar:

- Filtro de Estado Activo: Consulta la tabla `activos`. Si `estado_operativo` es `'PAUSADO'` o `'SOLO_CIERRAR'`, aborta la operación.
- Filtro de Horario: Consulta `horarios_operativos`. Si la hora actual (en la zona horaria definida) está fuera de la ventana operativa del activo, aborta la operación.
- Filtro de Correlación: Consulta las posiciones abiertas en `registro_operaciones`. Si ya existe una exposición máxima permitida para la categoría de ese activo (ej. "Acciones"), reduce el lotaje a la mitad o aborta para evitar sobre-exposición sectorial.
- Filtro de Regímenes Macro: Consulta `regimenes_mercado`. Si existe un evento en estado `ACTIVO` o `POST_CLIMAX` con un `sesgo_proyectado`, el Gerente incorpora el Vector de Fuerza Combinada calculado por el Obrero NLP al Veredicto final, pudiendo confirmar una operación dudosa o cancelar una contraria al sesgo macro.

**Fase C: Ejecución y Gestión de Capital**

Si todos los filtros pasan en verde:

- Cálculo de Lotaje Dinámico: Consulta el saldo de la cuenta de MT5 (`mt5.account_info().balance`) y la variable `riesgo_trade_pct` (ej. 1.5%). Calcula el volumen exacto (lotes) de manera que, si la operación toca el Stop Loss, la pérdida monetaria equivalga exactamente al 1.5% del balance.
- Cálculo de TP/SL: Calcula el Stop Loss técnico basado en la volatilidad reciente (ATR) o en el último muro de Order Flow. Multiplica esa distancia por la variable `ratio_tp` (ej. 2.0) para colocar el Take Profit.
- Disparo: Envía la petición a MT5 usando `mt5.order_send()`. Utiliza tipos de orden `ORDER_FILLING_IOC` (Immediate or Cancel) para garantizar el precio o abortar.
- Auditoría: Registra inmediatamente todos los detalles financieros (Ticket, Lotaje, Valor Nocional, Precio de Entrada, TP, SL, Fee Estimado) en la tabla `registro_operaciones` asociándolo a la `version_id` actual.

---

## 4. Definición del Esquema de Base de Datos y Parámetros

*(Nota: Consultar el esquema SQL V3 proporcionado previamente para la creación de tablas.)*

### 4.1. Diccionario de Parámetros Clave (`parametros_sistema`)

El sistema debe leer estas variables de la BD al iniciar y actualizarse periódicamente sin reiniciar.

| Parámetro | Tipo | Descripción |
|---|---|---|
| `TENDENCIA.ema_rapida` | INT | Periodos EMA corta. |
| `TENDENCIA.ema_lenta` | INT | Periodos EMA larga. |
| `TENDENCIA.peso_voto` | FLOAT | Relevancia en el ensemble [0.0 - 1.0]. |
| `NLP.umbral_positivo` | FLOAT | Score mínimo para NLP alcista. |
| `NLP.peso_voto` | FLOAT | Relevancia en el ensemble [0.0 - 1.0]. |
| `ORDER_FLOW.profundidad` | INT | Niveles del Book a escanear. |
| `ORDER_FLOW.peso_voto` | FLOAT | Relevancia en el ensemble [0.0 - 1.0]. |
| `GERENTE.umbral_disparo` | FLOAT | Valor absoluto mínimo del Veredicto para operar. |
| `GERENTE.riesgo_trade_pct` | FLOAT | % de balance arriesgado por trade. |
| `GERENTE.ratio_tp` | FLOAT | Relación Riesgo/Beneficio esperada (RRR). |

---

## 5. Dashboard Analítico, Métricas y Control de Versiones IA

El Dashboard (Frontend a desarrollar) consumirá Vistas SQL desde PostgreSQL para monitorear el sistema.

### 5.1. Reglas de Negocio para el Dashboard

**Husos Horarios:** La base de datos almacena TODO en UTC (TIMESTAMPTZ). El Dashboard DEBE renderizar los cortes de sesión y consultas diarias transformando el tiempo a `America/Santiago` al vuelo (ej. `AT TIME ZONE 'America/Santiago'`).

**Métricas de Rendimiento (KPIs a calcular por Vista SQL):**

| KPI | Fórmula |
|---|---|
| Win Rate | (Operaciones TP / Operaciones Totales) × 100 |
| Riesgo/Beneficio Realizado | Promedio $ ganado por trade exitoso / Promedio $ perdido por trade fallido |
| ROE % | (PnL Neto de la operación / Saldo de cuenta en el momento de la entrada) × 100 |
| Duración Media | Tiempo entre `tiempo_entrada` y `tiempo_salida` |

**Control de Versiones y Rollback:**
- Todas las operaciones se vinculan a un `version_id` (tabla `versiones_sistema`).
- La tabla `analisis_ia` registra auditorías automatizadas. Si el usuario aprueba una sugerencia, el sistema clona los parámetros actuales, aplica los cambios, genera una nueva versión activa y marca la anterior como obsoleta.
- Rollback: El usuario puede reactivar una versión obsoleta desde el Dashboard. El Gerente Python debe detectar el cambio de versión en la BD y recargar instantáneamente los parámetros antiguos.

**Estado en Vivo:** El Gerente Python debe hacer un UPDATE continuo (ej. cada 3 segundos) en la tabla `estado_bot`, escribiendo un resumen de texto en `pensamiento_actual` (ej. `"Evaluando señal de compra XAUUSD. Veredicto: +0.68. Validando exposición..."`).

### 5.2. Módulos de Transparencia y Auditoría Cognitiva

**Módulo de Auditoría de Noticias (NLP Insights):**

El sistema contará con una interfaz estática dedicada exclusivamente a auditar el "Cerebro NLP". No es un monitor de estado en vivo, sino un registro histórico legible. Mostrará una tabla detallada con:

- El titular exacto procesado y su fuente original.
- El puntaje numérico final asignado (ej. `-0.85`).
- **Razonamiento Cognitivo:** Una justificación textual (generada por el LLM o el módulo NLP) que explica por qué llegó a esa conclusión. Ej: `"Titular clasificado como Choque Geopolítico. La mención de 'cierre de fronteras' detona aversión al riesgo, proyectando un sesgo fuertemente alcista para activos refugio como XAUUSD"`.

Este campo se almacena en la columna `razonamiento_ia` de la tabla `sentimiento_noticias`.

**Módulo de Justificación de Ejecución (Trade Rationale):**

Se elimina el concepto de operaciones de "caja negra". Cada posición que el Gerente abre en el mercado (visible en el Dashboard de posiciones abiertas e historial) debe incluir obligatoriamente una **Justificación Textual de Entrada**.

Al momento de ejecutar la orden vía MetaTrader 5, el Gerente redactará y guardará un párrafo resumiendo el cruce de variables que lo llevó a disparar. Ej:

> `"Compra de 0.5 lotes XAUUSD ejecutada. Veredicto Final: +0.72. Convergencia detectada: Obrero NLP (+0.40 por debilidad del USD post-FED) + Obrero Flujo detectó muro de liquidez en 2025.00 (+0.32). Régimen Macro 'Recortes' aportó sesgo positivo. Riesgo controlado al 1.5% del balance"`.

Este campo se almacena en la columna `justificacion_entrada` de la tabla `registro_operaciones`.

---

## 6. Visualización del Contexto Macro en Dashboard (HUD)

El frontend debe incluir un banner superior persistente (Heads-Up Display) que lea los eventos en estado `FORMANDOSE`, `ACTIVO` o `POST_CLIMAX` desde la tabla `regimenes_mercado`.

**Requisitos del HUD:**
- Icono representativo del tipo de fuerza (`REGIMEN_MACRO`, `CATALIZADOR`, `CHOQUE_GEOPOLITICO`).
- Impacto numérico actual del evento (valor `impacto_base`).
- Días restantes para la `fecha_climax` del evento.
- El banner debe actualizarse en tiempo real junto con el resto del Dashboard.
- Los eventos en estado `DISIPADO` no deben aparecer en el HUD.
