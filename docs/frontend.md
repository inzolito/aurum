# Documento de Especificación de Interfaz y Experiencia de Usuario (UI/UX)

**Módulo:** Frontend / Dashboard Analítico  
**Proyecto:** Aurum Bot (Trading Institucional Multi-Estrategia)  
**Versión:** V3 (Omni - Glass Box)

---

## 1. Arquitectura Base y Reglas de Renderizado

Antes de definir las pantallas, el equipo de desarrollo del Frontend debe adherirse a estas reglas estrictas de procesamiento de datos:

- **Gestión Universal de Husos Horarios:** La base de datos PostgreSQL sirve absolutamente todos los timestamps en formato UTC. Es responsabilidad exclusiva del Frontend interceptar estos datos y transformarlos a la zona horaria `America/Santiago` (Hora de Chile) antes de renderizarlos en cualquier tabla o gráfico.

- **Cortes de Sesión Dinámicos:** El cálculo de "Ganancias de Hoy" (PnL de Sesión) no se basa en el cierre de Wall Street. El Frontend calculará la sesión estrictamente desde las `00:00:00` hasta las `23:59:59` (Hora de Chile).

- **Reactividad en Tiempo Real:** El Dashboard no debe requerir que el usuario presione F5 (refrescar). Utilizará WebSockets o Long Polling para escuchar cambios en la tabla `estado_bot` y `registro_operaciones`, actualizando los widgets en milisegundos.

- **Diseño "Dark Mode" Nativo:** Al ser una herramienta de monitoreo prolongado, la paleta de colores por defecto debe ser oscura. Paleta base:

| Uso | Color |
|---|---|
| Fondo | Grises profundos |
| Información neutra / UI | Cian |
| Ganancias / Compras | Verde esmeralda |
| Pérdidas / Ventas | Rojo carmesí |

---

## 2. Topología de Pantallas (Navegación Principal)

El Dashboard estará dividido en **5 vistas** accesibles desde un menú lateral colapsable:

| # | Vista | Función Principal |
|---|---|---|
| 1 | **Panel Central (El HUD)** | Resumen ejecutivo, estado del bot y contexto macroeconómico. |
| 2 | **Auditoría de Operaciones (Caja de Cristal)** | Diario de trading detallado con justificaciones textuales. |
| 3 | **Radar Macroeconómico (NLP)** | Historial de noticias y razonamiento de la IA. |
| 4 | **Gestión de Riesgo y Activos** | Control de interruptores y mapas de calor. |
| 5 | **Laboratorio de IA y Versiones** | Análisis automático, sugerencias y Rollbacks. |

---

## 3. Especificación de Vistas

### Vista 1: Panel Central (Heads-Up Display — HUD)

Pantalla de inicio. Condensa la salud financiera de la cuenta y la dirección global del mercado en un solo vistazo.

**A. Banner Superior Persistente (Contexto Macro)**

- **Ubicación:** Pegado a la parte superior (Sticky Header).
- **Función:** Muestra los `regimenes_mercado` en estado `FORMANDOSE`, `ACTIVO` o `POST_CLIMAX`.
- **Visualización:** Carrusel o fila de "Píldoras" (Badges). Cada píldora muestra:
  - Icono representativo (ej. globo terráqueo para geopolítica, calendario para Earnings).
  - Título del evento (ej. `"Ciclo Recortes FED"`).
  - Impacto vectorial (ej. `"Oro: +0.20 | USD: -0.15"`).
  - Cuenta regresiva si es un evento futuro (ej. `"Faltan X días"`).

**B. Monitor de Estado y Pensamiento en Vivo**

- **Ubicación:** Esquina superior derecha del área de contenido.
- **Función:** Lee la tabla `estado_bot`.
- **Visualización:**
  - Indicador LED parpadeante (🟢 `OPERANDO` / 🟡 `ESPERANDO` o `PAUSADO` / 🔴 `ERROR`).
  - Caja de texto estilo "Terminal" que renderiza el campo `pensamiento_actual` (ej. `"Evaluando señal de compra XAUUSD. Validando volumen..."`).
  - Contador de Uptime (tiempo del bot encendido sin interrupciones).

**C. Tarjetas de Resumen Financiero (KPIs de Sesión)**

Fila de 4 tarjetas grandes actualizadas en tiempo real:

| Tarjeta | Métrica |
|---|---|
| Balance Total Cuenta | Saldo actual disponible. |
| PnL Sesión Actual (Local) | Ganancia o pérdida neta del día en curso en USD. |
| Win Rate Sesión | % de operaciones ganadoras hoy. |
| Exposición Actual | Dinero total arriesgado en operaciones abiertas en este momento. |

---

### Vista 2: Auditoría de Operaciones (La Caja de Cristal)

Reemplaza al historial ciego de MetaTrader. El usuario puede interrogar al algoritmo sobre cada decisión.

**A. Tabla de Posiciones Abiertas (Live Positions)**

- **Columnas:** Ticket | Símbolo | Tipo (L/S) | Lotaje | Precio Entrada | Stop Loss | Take Profit | PnL Flotante USD | ROE %.
- **Fila Expandible (Accordion):** Al hacer clic en cualquier operación, la fila se despliega revelando la `justificacion_entrada`. Ejemplo:
  > *"🤖 Razonamiento del Gerente: Compra ejecutada por convergencia fuerte (+0.75). Obrero NLP detectó pánico alcista (+0.40). Obrero Flow detectó muro institucional en 2030.00. Lotaje reducido por filtro de correlación macro."*

**B. Tabla de Historial (Closed Trades)**

- **Columnas:** Fecha/Hora (Local) | Símbolo | L/S | PnL Final USD | Comisiones (Fee) | Duración del Trade.
- **Funcionalidades:** Filtros por fecha y por activo. Botón de exportación a CSV para fines fiscales. Cada fila guarda su `justificacion_entrada` original para *Backtesting Psicológico*.

---

### Vista 3: Radar Macroeconómico (Auditoría NLP)

Pantalla exclusiva para auditar lo que "lee y entiende" el Obrero de Noticias.

**A. Feed Histórico de Titulares (`sentimiento_noticias`)**

Lista cronológica de cada noticia financiera procesada por el bot.

| Campo | Descripción |
|---|---|
| Timestamp | Hora exacta de publicación (en hora local). |
| Fuente & Titular | Ej. `"Bloomberg — Israel cierra espacio aéreo"`. |
| Score NLP Asignado | Medidor visual de `-1.0` a `+1.0` (rojo oscuro → verde brillante). |
| Razonamiento IA (`razonamiento_ia`) | Explicación textual de la deducción. Permite al administrador detectar si el NLP está interpretando mal el sarcasmo financiero o "alucinando". |

---

### Vista 4: Gestión de Riesgo y Activos (Panel de Control)

El puente de mando manual. Permite intervenir la estrategia sin tocar una línea de código Python.

**A. Matriz de Interruptores (Kill Switches)**

Cuadrícula con todos los activos de la tabla `activos`. Cada activo tiene un Toggle Group con 3 estados:

| Estado | Significado |
|---|---|
| 🟢 `ACTIVO` | Operación normal. |
| 🟡 `SOLO_CIERRAR` | El bot mantiene operaciones actuales y ajusta Stop Loss, pero no abre nuevas (ideal para pre-Earnings o NFP). |
| 🔴 `PAUSADO` | El bot ignora completamente este activo. |

**B. Monitor de Correlación (Heatmap)**

Gráfico de barras apiladas o gráfico de dona que muestra la concentración de capital por categoría. Si el 80% del capital arriesgado está en una sola categoría (ej. `ACCIONES`), el gráfico se torna naranja/rojo para alertar sobre sobre-exposición sectorial.

**C. Ajuste de Parámetros en Caliente**

Formulario que lee y escribe directamente en la tabla `parametros_sistema`. Incluye:
- Slider para `GERENTE.riesgo_trade_pct` (ej. reducir de 1.5% a 0.5% en días volátiles).
- Sliders para modificar el `peso_voto` de cada Obrero en tiempo real.

---

### Vista 5: Laboratorio de IA y Control de Versiones

El módulo de evolución del algoritmo.

**A. Panel de Análisis Automático**

- **Botón de acción principal:** `"Ejecutar Auditoría IA"`.
- Al presionarlo, el sistema procesa los últimos 100 trades de `registro_operaciones` y genera un reporte en `analisis_ia` que incluye:
  - **Fugas de Capital:** Ej. `"Estás perdiendo el 70% de las veces que operas XAGUSD durante la sesión asiática."`.
  - **Sugerencias de Optimización:** Ej. `"Propongo subir el peso del Obrero NLP a 0.40 para Oro."`.

**B. Gestor de Versiones (Time Machine)**

- Lista histórica de las `versiones_sistema` (v1.0.0, v1.1.0, etc.) con el PnL y Win Rate que logró cada versión mientras estuvo activa.
- **El Botón de Pánico (Rollback):** Cada versión antigua tiene un botón de *"Restaurar"*. Al presionarlo, el Frontend hace un `UPDATE` en la base de datos convirtiendo esa versión en la activa, obligando al Gerente Python a recargar esos parámetros instantáneamente.
