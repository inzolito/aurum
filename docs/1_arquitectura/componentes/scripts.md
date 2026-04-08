# Documento de Arquitectura de Software (Backend Python)

**Proyecto:** Aurum Bot (Trading Institucional Multi-Estrategia)  
**Versión de Arquitectura:** V3 (Omni)

---

## 1. Filosofía de Diseño y Patrones

El backend de Aurum está construido bajo el paradigma de **Arquitectura Modular Orientada a Objetos (OOP)**. El sistema está estrictamente desacoplado para garantizar resiliencia: los módulos generadores de señales (Obreros) están aislados de los módulos de ejecución (Broker) y de almacenamiento (Base de Datos).

**Principios Core:**

- **Modelo "Ensemble" (Votación Ponderada):** Las decisiones no recaen en un solo indicador. Se utiliza un consenso matemático de múltiples dimensiones (Tendencia, Order Flow y Contexto Macro).

- **Transparencia Total (Glass Box):** El sistema carece de "cajas negras". Cada evaluación, cálculo matemático y decisión de ejecución debe generar una justificación textual (auditoría cognitiva) que se almacena en la base de datos.

- **Fail-Safe (Falla Segura):** Si un módulo externo falla (ej. desconexión del broker o caída de la API de noticias), el sistema aborta el ciclo de evaluación actual y protege el capital, en lugar de colapsar la aplicación completa.

---

## 2. Topología de Directorios y Módulos

El proyecto se divide lógicamente en cuatro grandes bloques funcionales:

```
aurum_bot/
├── main.py                  # Punto de entrada y motor del sistema
├── config/                  # Capa de Infraestructura (Conexiones)
│   ├── db_connector.py
│   └── mt5_connector.py
├── core/                    # Capa de Lógica de Negocio y Riesgo
│   ├── manager.py
│   └── risk_module.py
└── workers/                 # Capa de Análisis Predictivo (Señales)
    ├── worker_trend.py
    ├── worker_nlp.py
    └── worker_flow.py
```

---

## 3. Especificación Detallada de Componentes

### 3.1. Punto de Entrada (`main.py`)

Es el motor (*Main Loop*) que mantiene el sistema en ejecución continua.

- **Responsabilidad:** Inicializa las conexiones hacia PostgreSQL y MetaTrader 5. Una vez validadas, entra en un bucle infinito donde consulta la base de datos para saber qué activos tienen el interruptor en `ACTIVO`. Por cada activo encendido, invoca un ciclo de evaluación del `manager.py`.

- **Manejo de Estados:** En caso de interrupción manual (apagado del sistema), actualiza la tabla `estado_bot` para que el Dashboard refleje que el sistema está fuera de línea de manera segura.

---

### 3.2. Capa de Infraestructura (`config/`)

Aísla la complejidad de las conexiones externas. Ningún otro módulo debe importar librerías de bases de datos o del broker directamente.

**`db_connector.py`**

Administra la conexión a PostgreSQL en Google Cloud mediante `psycopg2`. Carga credenciales desde `.env`. Métodos implementados:

| Método | Descripción |
|---|---|
| `conectar()` / `desconectar()` | Abre y cierra la conexión de forma limpia |
| `test_conexion()` | Ejecuta `SELECT version()` para verificar conectividad |
| `get_parametros()` | Retorna `dict` con clave `MODULO.nombre` → valor `float` |
| `obtener_simbolo_broker(simbolo)` | Traduce símbolo interno (`XAUUSD`) al nombre del broker (`XAUUSD_i`) |
| `obtener_activos_patrullaje()` | **Principal.** Retorna lista de `dicts` completos (`id`, `simbolo`, `nombre`, `categoria`, `simbolo_broker`) con `estado_operativo = 'ACTIVO'`. Fuente de verdad dinámica para `main.py`. |
| `obtener_activos_encendidos()` | Alias de compatibilidad — retorna solo los símbolos como lista de strings. |
| `obtener_impactos_por_activo(id_activo)` | JOIN entre `impactos_regimen` y `regimenes_mercado`. Retorna impactos ponderados de regímenes `ACTIVO`/`FORMANDOSE` para un activo específico. Fuente de datos del NLPWorker agnóstico. |
| `get_regimenes_activos()` | **Deprecated.** Retorna lista vacía. Reemplazado por `obtener_impactos_por_activo`. |
| `update_estado_bot(estado, pensamiento)` | UPSERT en fila id=1 de `estado_bot` |
| `registrar_log(nivel, modulo, mensaje)` | Inserta evento en `log_sistema` |
| `guardar_senal(...)` | Registro completo de evaluación en `registro_senales` |
| `guardar_operacion(datos)` | Trade con justificación en `registro_operaciones` |

**`mt5_connector.py`**

Puente de comunicación local con la terminal de MetaTrader 5. Métodos implementados:

| Método | Descripción |
|---|---|
| `conectar()` | Inicializa MT5. Usa credenciales del `.env` o sesión abierta |
| `desconectar()` | Llama a `mt5.shutdown()` |
| `obtener_velas(simbolo, cantidad, timeframe)` | DataFrame pandas OHLCV en UTC. Por defecto M1 |
| `obtener_order_book(simbolo)` | Retorna `{bids, asks}` del Level 2 |
| `obtener_precio_actual(simbolo)` | Retorna `{bid, ask, spread}` |
| `enviar_orden(simbolo, direccion, lotes, sl, tp)` | Orden `TRADE_ACTION_DEAL` con `ORDER_FILLING_IOC`. Retorna ticket |

> **Broker Weltrade:** Los símbolos usan sufijo `_i` (ej. `XAUUSD_i`). La traducción se realiza automáticamente vía `obtener_simbolo_broker()` en la BD.

---

### 3.3. Capa de Lógica de Negocio (`core/`)

El cerebro administrativo de Aurum. Coordina a los Obreros y protege la cuenta.

**`risk_module.py` — Gestor de Riesgo**

Filtro de seguridad absoluto. Clase `RiskModule(db, mt5)`.

| Método | Descripción |
|---|---|
| `calcular_lotes(simbolo_interno, sl_precio)` | Fórmula: `Balance × Riesgo% ÷ (Distancia_SL × Valor_punto/lote)`. Valida `vol_min`, `vol_max` y `vol_step` del broker. |
| `filtro_seguridad(simbolo_interno)` | 3 verificaciones: estado `ACTIVO` en BD, sin posición duplicada abierta, ventana horaria (`horarios_operativos`). |

El módulo recupera `simbolo_broker` desde la BD y el balance vía `mt5.account_info()`.

**`manager.py` — El Gerente Ensemble**

Clase `Manager(db, mt5)`. Método principal `evaluar(simbolo_interno, modo_simulacion, id_activo=None) → dict`.

**Ciclo de vida por activo:**

| Paso | Acción |
|---|---|
| 1 | `filtro_seguridad()` — si falla, registra `CANCELADO_RIESGO` y aborta |
| 2 | Lee pesos desde BD y los **normaliza** para que siempre sumen `1.00` |
| 3 | Consulta los 3 Obreros en secuencia |
| 4 | Calcula: `veredicto = (v_trend × w_trend) + (v_nlp × w_nlp) + (v_flow × w_flow)` |
| 5 | Compara `abs(veredicto)` contra `GERENTE.umbral_disparo` (default `0.65`) |
| 6 | Si no supera: registra `IGNORADO` con motivo textual |
| 7 | Si supera: calcula SL/TP, llama a `calcular_lotes()`, imprime o ejecuta la orden |
| 8 | **Siempre** llama a `_guardar_auditoria()` → `registro_senales` |

**Modo `modo_simulacion=True`:** imprime `Simulando ejecucion de [DIRECCIÓN] con [LOTES] lotes` sin enviar orden real al broker.

**Glass Box:** cada fila de `registro_senales` contiene los 3 votos individuales, el veredicto ponderado, la decisión y el motivo textual generado automáticamente.

---

### 3.4. Capa de Análisis Predictivo (`workers/`)

Son micro-algoritmos independientes. Todos comparten la misma interfaz o "contrato": reciben el símbolo del activo, aplican su lógica matemática y devuelven un voto normalizado de **-1.0** (Venta Fuerte) a **+1.0** (Compra Fuerte).

**`worker_trend.py` — Obrero de Acción del Precio**

Clase `TrendWorker(db, mt5)`. Método `analizar(simbolo_interno) → float`.

**Indicadores** (librería `ta`, compatible Python 3.11):
- `EMA rápida` (periodo configurable, default 9) y `EMA lenta` (default 21) vía `TENDENCIA.ema_rapida` / `TENDENCIA.ema_lenta` en `parametros_sistema`.
- `RSI(14)` para medir condiciones de sobrecompra/sobreventa.

**Lógica de votación:**

| Condición | Voto base |
|---|---|
| Precio > EMA9 > EMA21 + RSI < 70 | `+0.8` (alcista con espacio) |
| Precio > EMA9 > EMA21 + RSI < 30 | `+1.0` (rebote en sobreventa) |
| Precio < EMA9 < EMA21 + RSI > 30 | `-0.8` (bajista con espacio) |
| Precio < EMA9 < EMA21 + RSI > 70 | `-1.0` (rechazo en sobrecompra) |
| EMAs comprimidas (`distancia < 0.01%`) | Voto reducido al 20% (rango lateral) |

> **Nota de dependencia:** `pandas_ta` no tiene distribución para Python 3.11. Se usa la librería `ta` con wrappers `_ema()` y `_rsi()` transparentes. Si en el futuro se migra a Python 3.12, se puede volver a `pandas_ta` sin cambiar la lógica del worker.

**`worker_flow.py` — Obrero Institucional**

Clase `OrderFlowWorker(db, mt5)`. Método `analizar(simbolo_interno) → float`.

**Fórmula OBI (Order Book Imbalance):**
```
imbalance = (vol_bids - vol_asks) / (vol_bids + vol_asks)
voto      = clamp(imbalance × 1.5, -1.0, +1.0)
```

- Suma los primeros **10 niveles** de profundidad del libro de órdenes.
- `+1.0` = toda la presión es compradora | `-1.0` = toda presión vendedora.
- **Fail-safe:** Si el broker no expone Level 2 (común en brokers CFD como Weltrade), retorna `0.0` neutral sin bloquear al Gerente.

> **Nota Weltrade:** El broker no expone Order Book vía MT5. El worker opera en modo neutral hasta que se añada una fuente alternativa de Order Flow (ej. velas de volumen, DOM externo).

**`worker_nlp.py` — Obrero de Contexto Macro (Versión Agnóstica)**

Clase `NLPWorker(db)`. Método `analizar(simbolo_interno, id_activo=None) → float`. **No usa MT5.**

**Refactorización crítica (v1.1):** Este módulo fue reescrito para ser completamente agnóstico al activo. Ya **no** usa las columnas `impacto_base_oro`, `impacto_base_usd` ni `impacto_base_acciones`. En su lugar, consulta la tabla many-to-many `impactos_regimen` para obtener el impacto específico definido por activo.

**Flujo de datos:**
1. Si `id_activo` no se pasa, lo resuelve desde la BD buscando el `simbolo_interno` en `activos`.
2. Llama `db.obtener_impactos_por_activo(id_activo)` → hace JOIN `impactos_regimen` + `regimenes_mercado` filtrando por estado `ACTIVO` / `FORMANDOSE`.
3. Suma vectorial de `valor_impacto` por cada régimen activo.

La tabla `impactos_regimen` define el impacto específico de cada régimen para **cada activo individualmente**, permitiendo que el mismo régimen macro (ej. "Recorte FED") tenga un impacto diferente en Oro (+0.40) y en Plata (+0.35).

**Lógica de votación:**

| Condición | Efecto |
|---|---|
| Régimen en estado `ACTIVO` | `100%` del `valor_impacto` |
| Régimen en estado `FORMANDOSE` | `50%` del `valor_impacto` (mercado anticipa, no confirma) |
| Sin impactos registrados para el activo | Retorna `0.0` neutral sin bloquear al Gerente |
| Activo no encontrado en BD | Retorna `0.0` y registra error en consola |

- El voto acumulado se clampea al rango `[-1.0, +1.0]`.
- `EURUSD` u otros activos sin entradas en `impactos_regimen` retornan `0.0` automáticamente.

**Añadir impacto a un activo — sólo SQL:**
```sql
INSERT INTO impactos_regimen (id_regimen, id_activo, valor_impacto)
VALUES (1, 3, -0.30);  -- régimen id=1 afecta EURUSD (id=3) con -0.30
```

---

## 4. Flujo de Ejecución del Ciclo (Life Cycle)

Para auditar el sistema, este es el recorrido exacto de un tick de evaluación:

| Paso | Módulo | Acción |
|---|---|---|
| 1 | `main.py` | Lee `db.obtener_activos_patrullaje()` → lista dinámica de activos `ACTIVO` (con `id` real de BD). |
| 2 | `main.py` | Itera cada activo dict; llama `manager.evaluar(simbolo, modo_simulacion=False, id_activo=id)`. |
| 3 | `risk_module.py` | Valida horario operativo y estado del activo (`ACTIVO` / `PAUSADO`). |
| 4 | `workers/` | Cada Obrero analiza su dimensión. `NLPWorker` recibe `id_activo` y consulta `impactos_regimen`. |
| 5 | `manager.py` | Calcula la suma producto con los pesos de la BD → **Veredicto Final**. |
| 6 | `risk_module.py` | Si el Veredicto supera el umbral, calcula el lotaje al 1.5% de riesgo. |
| 7 | `manager.py` | Redacta justificación textual, dispara la orden vía `mt5_connector` y guarda la auditoría completa. |

> **Escalabilidad:** Para que el bot opere un nuevo activo (ej. Platino `XPTUSD`), basta con insertar una fila en `activos` con `estado_operativo = 'ACTIVO'`. El motor lo detecta **sin reiniciar ni tocar el código**.
