# Documentación de Base de Datos: Proyecto Aurum (Esquema V3 Omni)

## 1. Resumen Ejecutivo de la Arquitectura de Datos

La base de datos PostgreSQL de Aurum está diseñada para ser el "Cerebro Remoto" de un sistema de trading institucional de alta frecuencia. Su diseño prioriza tres pilares:

- **Latencia y Ligereza:** Tablas optimizadas con tipos de datos estrictos (`NUMERIC`, `SMALLINT`) para no saturar servidores en la nube de bajos recursos (ej. instancia e2-micro).
- **Auditoría Absoluta (Zero Black-Box):** El sistema registra cada pensamiento, error, señal rechazada y operación ejecutada. Si el bot pierde dinero, la base de datos dirá exactamente qué módulo falló o qué Obrero votó incorrectamente.
- **Escalabilidad Multi-Activo y Contexto Macro:** Preparada para operar metales, divisas, acciones e índices simultáneamente, integrando fuerzas macroeconómicas superpuestas (tasas de interés, reportes de ganancias, guerras) que afectan las decisiones de los algoritmos.

---

## 2. Diccionario de Datos (Bloques Estructurales)

### Bloque 1: Administración y Configuración Base

Define los usuarios, el control de versiones del algoritmo y las reglas operativas de los mercados.

| Tabla | Descripción |
|---|---|
| `usuarios` | Gestiona el acceso al Dashboard analítico. |
| `versiones_sistema` | Núcleo del control de versiones. Permite que la IA sugiera cambios en los parámetros, creando una nueva versión. Si la rentabilidad cae, el administrador puede ejecutar un Rollback a una versión anterior. |
| `activos` | Diccionario maestro de los pares/instrumentos que el bot conoce. La columna `estado_operativo` actúa como **Kill Switch**: permite apagar temporalmente un activo (`PAUSADO`) o dejar que gestione posiciones abiertas sin abrir nuevas (`SOLO_CIERRAR`), todo sin detener el servidor. |
| `horarios_operativos` | El reloj biológico del bot. Define a qué hora es seguro operar un activo específico para evitar spreads altos o mercados cerrados (fundamental para Acciones e Índices). |

### Bloque 2: Contexto, Memoria y Parámetros

El conocimiento del mercado a corto y largo plazo, junto con el panel de control del Gerente.

| Tabla | Descripción |
|---|---|
| `regimenes_mercado` | **(Crucial)** Almacena el contexto macroeconómico a largo plazo. Clasifica eventos en Regímenes Macro, Catalizadores y Choques Geopolíticos. Los Obreros NLP leen los `impacto_base` de estos eventos para hacer una suma vectorial y entender la dirección global del mercado. |
| `velas_1m` | Historial de la acción del precio en corto plazo (OHLCV). Memoria de trabajo del Obrero de Tendencia. |
| `sentimiento_noticias` | Historial crudo de los titulares financieros procesados, la fuente y el puntaje matemático exacto que la IA les asignó al momento de su publicación. La columna `razonamiento_ia` almacena la justificación en lenguaje natural de por qué la noticia recibió ese puntaje, legible desde el módulo NLP Insights del Dashboard. |
| `parametros_sistema` | Tabla Key-Value. Permite ajustar en vivo (en caliente) el lotaje, el Stop Loss, los periodos de las medias móviles o la autoridad de cada Obrero sin reiniciar el código en Python. |

### Bloque 3: Registro Operativo y Auditoría

El diario de trading del bot y las métricas para alimentar el Dashboard.

| Tabla | Descripción |
|---|---|
| `registro_senales` | Registra todas las decisiones del Gerente, incluso las que no se operaron. Almacena la votación individual de cada Obrero y el motivo exacto por el cual se autorizó o canceló una orden. |
| `registro_operaciones` | El Diario de Trading principal. Guarda los tickets de MetaTrader 5, el apalancamiento, los valores reales en USD (sin apalancar), los fees de comisión, el PnL y el ROE exacto de cada trade. Vinculado siempre a un `version_id`. La columna `justificacion_entrada` almacena el "pensamiento final" del Gerente en el milisegundo exacto en que envió la orden al broker, visible de forma permanente en el Dashboard para auditoría humana y backtesting psicológico. |
| `log_sistema` | Monitoreo de salud. Registra caídas de API, desconexiones de MT5 o errores en la base de datos. |
| `analisis_ia` | El cuaderno de notas del auditor de IA. Guarda las sugerencias de optimización generadas tras analizar el historial de trades, a la espera de aprobación del administrador. |
| `estado_bot` | Un "latido" (heartbeat) del sistema. El código Python actualiza esta tabla constantemente con su `pensamiento_actual` (ej. `"Esperando cierre de vela en Oro"`) para mostrarse en el Dashboard en vivo. |
| `cache_nlp_impactos` | **(V9.0+)** Almacena el resultado del análisis de Gemini para evitar llamadas redundantes. Reduce costos en un 80%. |
| `noticias_notificadas` | **(V12.0+)** Registro de hashes de noticias enviadas a Telegram para evitar spam en el radar de noticias. |
| `balance_sesion` | Snapshots diarios del patrimonio de la cuenta para graficar la curva de crecimiento sin tener que recalcular todo el historial matemático cada vez que se abre el Dashboard. |

---

## 3. Reglas de Negocio Estrictas

- **Gestión de Husos Horarios:** Para evitar corrupción de datos durante los cambios de horario de verano, todos los campos de tiempo se guardan en UTC (`TIMESTAMPTZ`). El frontend del Dashboard es el único responsable de convertir estas fechas al horario local del usuario (`America/Santiago`) para mostrar los cortes de sesión de 00:00 a 23:59.

- **Precisión Financiera:** Se prohíbe el uso de tipos de dato `FLOAT` o `REAL` para el manejo de dinero o precios, ya que generan errores de redondeo. Todo cálculo financiero utiliza `NUMERIC` con precisión estricta (ej. `NUMERIC(10, 4)` para precios de metales, `NUMERIC(10, 2)` para PnL).

- **Cascada de Eliminación Protegida:** Se puede eliminar un activo, lo que borrará en cascada sus velas de 1m (`ON DELETE CASCADE`), pero la base de datos restringirá (`ON DELETE RESTRICT`) la eliminación si ese activo ya tiene operaciones reales registradas en el historial, protegiendo la auditoría fiscal.

---

## 4. Esquema SQL Completo (V3 Omni)

```sql
-- ====================================================================
-- PROYECTO AURUM: maikBotTrade Ensemble (Arquitectura Omni V3)
-- Esquema de Base de Datos Maestro Completo (PostgreSQL)
-- ====================================================================

-- --------------------------------------------------------------------
-- BLOQUE 1: TABLAS BASE Y ADMINISTRACIÓN
-- --------------------------------------------------------------------

-- 1. TABLA DE USUARIOS (Para login del Dashboard)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) DEFAULT 'ADMIN',
    creado_en TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. TABLA DE VERSIONES (El núcleo para hacer Rollbacks)
CREATE TABLE versiones_sistema (
    id SERIAL PRIMARY KEY,
    numero_version VARCHAR(20) UNIQUE NOT NULL,
    descripcion TEXT,
    estado VARCHAR(20) DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'OBSOLETA', 'EN_PRUEBA')),
    fecha_despliegue TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO versiones_sistema (numero_version, descripcion) VALUES ('v1.0.0', 'Lanzamiento Base Aurum Omni');

-- 3. TABLA DE ACTIVOS (Diccionario base con Kill Switches)
CREATE TABLE activos (
    id SMALLSERIAL PRIMARY KEY,
    simbolo VARCHAR(10) UNIQUE NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    categoria VARCHAR(20) CHECK (categoria IN ('METALES', 'FOREX', 'INDICES', 'ACCIONES', 'ENERGIA')),
    estado_operativo VARCHAR(15) DEFAULT 'ACTIVO' CHECK (estado_operativo IN ('ACTIVO', 'PAUSADO', 'SOLO_CIERRAR'))
);
INSERT INTO activos (simbolo, nombre, categoria, estado_operativo) VALUES
('XAUUSD', 'Oro Spot vs Dólar', 'METALES', 'ACTIVO'),
('XAGUSD', 'Plata Spot vs Dólar', 'METALES', 'ACTIVO'),
('XTIUSD', 'Petróleo WTI', 'ENERGIA', 'PAUSADO'),
('NDX100', 'Nasdaq 100', 'INDICES', 'PAUSADO'),
('EURUSD', 'Euro vs Dólar', 'FOREX', 'PAUSADO'),
('NVDA', 'Nvidia Corp', 'ACCIONES', 'PAUSADO');

-- 4. HORARIOS OPERATIVOS (El Reloj del Bot)
CREATE TABLE horarios_operativos (
    id SERIAL PRIMARY KEY,
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    hora_apertura TIME NOT NULL,
    hora_cierre TIME NOT NULL,
    zona_horaria VARCHAR(50) DEFAULT 'America/New_York'
);

-- --------------------------------------------------------------------
-- BLOQUE 2: CONTEXTO, MEMORIA Y PARÁMETROS
-- --------------------------------------------------------------------

-- 5. TABLA DE REGÍMENES Y CATALIZADORES (Fuerzas de Arrastre Macro)
CREATE TABLE regimenes_mercado (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(100) NOT NULL,
    clasificacion VARCHAR(30) CHECK (clasificacion IN ('REGIMEN_MACRO', 'CATALIZADOR', 'CHOQUE_GEOPOLITICO')),
    impacto_base_oro NUMERIC(3, 2) DEFAULT 0.00,
    impacto_base_usd NUMERIC(3, 2) DEFAULT 0.00,
    impacto_base_acciones NUMERIC(3, 2) DEFAULT 0.00,
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_climax TIMESTAMPTZ,
    estado VARCHAR(20) DEFAULT 'ACTIVO' CHECK (estado IN ('FORMANDOSE', 'ACTIVO', 'POST_CLIMAX', 'DISIPADO')),
    icono_dashboard VARCHAR(50),
    color_banner VARCHAR(20)
);
CREATE INDEX idx_regimenes_estado ON regimenes_mercado (estado) WHERE estado != 'DISIPADO';

-- 6. TABLA DE VELAS 1M (Memoria técnica del bot)
CREATE TABLE velas_1m (
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    tiempo TIMESTAMPTZ NOT NULL,
    apertura NUMERIC(10, 4) NOT NULL,
    maximo NUMERIC(10, 4) NOT NULL,
    minimo NUMERIC(10, 4) NOT NULL,
    cierre NUMERIC(10, 4) NOT NULL,
    volumen NUMERIC(15, 4) NOT NULL,
    PRIMARY KEY (activo_id, tiempo)
);
CREATE INDEX idx_velas_tiempo ON velas_1m (activo_id, tiempo DESC);

-- 7. TABLA DE SENTIMIENTO NOTICIAS RAW (Memoria NLP a corto plazo)
CREATE TABLE sentimiento_noticias (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    titular TEXT NOT NULL,
    impacto_nlp NUMERIC(3, 2) NOT NULL CHECK (impacto_nlp >= -1.0 AND impacto_nlp <= 1.0),
    fuente VARCHAR(50),
    razonamiento_ia TEXT  -- Justificación en lenguaje natural del puntaje asignado (NLP Insights)
);
CREATE INDEX idx_noticias_tiempo ON sentimiento_noticias (tiempo DESC);

-- 8. TABLA DE PARÁMETROS (Panel de Control en Caliente)
CREATE TABLE parametros_sistema (
    id SERIAL PRIMARY KEY,
    modulo VARCHAR(50) NOT NULL,
    nombre_parametro VARCHAR(50) UNIQUE NOT NULL,
    valor NUMERIC(10, 4) NOT NULL,
    descripcion TEXT,
    ultima_actualizacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO parametros_sistema (modulo, nombre_parametro, valor, descripcion) VALUES
('TENDENCIA', 'ema_rapida', 9.0000, 'Periodos media movil rapida'),
('TENDENCIA', 'ema_lenta', 21.0000, 'Periodos media movil lenta'),
('TENDENCIA', 'peso_voto', 0.3000, 'Importancia del obrero de tendencia (0 a 1)'),
('NLP', 'peso_voto', 0.2000, 'Importancia del obrero de noticias (0 a 1)'),
('ORDER_FLOW', 'peso_voto', 0.5000, 'Importancia del obrero de flujo (0 a 1)'),
('GERENTE', 'riesgo_trade_pct', 1.5000, 'Porcentaje de capital a arriesgar por trade'),
('GERENTE', 'umbral_disparo', 0.6500, 'Suma ponderada minima para autorizar trade'),
('GERENTE', 'ratio_tp', 2.0000, 'Multiplicador de Take Profit vs Stop Loss');

-- --------------------------------------------------------------------
-- BLOQUE 3: REGISTRO OPERATIVO Y AUDITORÍA
-- --------------------------------------------------------------------

-- 9. TABLA DE REGISTRO DE SEÑALES (Auditoría de decisiones)
CREATE TABLE registro_senales (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activo_id SMALLINT REFERENCES activos(id) ON DELETE CASCADE,
    voto_tendencia NUMERIC(3, 2),
    voto_nlp NUMERIC(3, 2),
    voto_order_flow NUMERIC(3, 2),
    voto_final_ponderado NUMERIC(4, 3),
    decision_gerente VARCHAR(30),
    motivo TEXT
);
CREATE INDEX idx_senales_tiempo ON registro_senales (tiempo DESC);

-- 10. TABLA DE REGISTRO DE OPERACIONES (El Diario de Trading y Dashboard)
CREATE TABLE registro_operaciones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    version_id INTEGER REFERENCES versiones_sistema(id),
    activo_id SMALLINT REFERENCES activos(id) ON DELETE RESTRICT,
    ticket_mt5 BIGINT UNIQUE,
    tiempo_entrada TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tipo_orden VARCHAR(4) CHECK (tipo_orden IN ('BUY', 'SELL')),
    apalancamiento NUMERIC(5, 2) DEFAULT 1.00,
    tamano_real_usd NUMERIC(15, 2) NOT NULL,
    volumen_lotes NUMERIC(6, 2) NOT NULL,
    precio_entrada NUMERIC(10, 4) NOT NULL,
    stop_loss NUMERIC(10, 4) NOT NULL,
    take_profit NUMERIC(10, 4) NOT NULL,
    fee_comision NUMERIC(10, 2) DEFAULT 0.00,
    estado VARCHAR(10) DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA', 'CERRADA')),
    tiempo_salida TIMESTAMPTZ,
    precio_salida NUMERIC(10, 4),
    pnl_usd NUMERIC(10, 2),
    roe_pct NUMERIC(10, 2),
    justificacion_entrada TEXT  -- Resumen narrativo del Gerente en el momento del disparo (Trade Rationale)
);
CREATE INDEX idx_operaciones_tiempo ON registro_operaciones (tiempo_entrada DESC);
CREATE INDEX idx_operaciones_estado ON registro_operaciones (estado);

-- 11. TABLA DE LOGS DEL SISTEMA (Salud y Monitoreo de Errores)
CREATE TABLE log_sistema (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nivel VARCHAR(10) CHECK (nivel IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    modulo VARCHAR(50) NOT NULL,
    mensaje TEXT NOT NULL
);
CREATE INDEX idx_logs_tiempo ON log_sistema (tiempo DESC);

-- 12. TABLA DE ANÁLISIS IA (Auditor de código y estrategia)
CREATE TABLE analisis_ia (
    id SERIAL PRIMARY KEY,
    version_analizada_id INTEGER REFERENCES versiones_sistema(id),
    fecha_analisis TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    sugerencias TEXT,
    bugs_encontrados TEXT,
    analisis_trades TEXT,
    analisis_algoritmo TEXT,
    estado_implementacion VARCHAR(20) DEFAULT 'PENDIENTE' CHECK (estado_implementacion IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')),
    version_resultante_id INTEGER REFERENCES versiones_sistema(id)
);

-- 13. TABLA ESTADO DEL BOT (El "Qué está pensando" en vivo)
CREATE TABLE estado_bot (
    id SERIAL PRIMARY KEY,
    tiempo TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    estado_general VARCHAR(20) CHECK (estado_general IN ('OPERANDO', 'ESPERANDO', 'PAUSADO_POR_RIESGO', 'ERROR')),
    pensamiento_actual TEXT,
    uptime_segundos BIGINT
);

-- 14. TABLA BALANCE Y SESIONES (Snapshots para el Dashboard)
CREATE TABLE balance_sesion (
    id SERIAL PRIMARY KEY,
    fecha_sesion DATE UNIQUE NOT NULL,
    balance_inicial NUMERIC(15, 2) NOT NULL,
    balance_cierre NUMERIC(15, 2),
    pnl_sesion NUMERIC(10, 2)
);
```

---

## 5. Migraciones: Módulo de Auditoría Cognitiva (ALTER TABLE)

Estas sentencias añaden las columnas de transparencia a las tablas existentes en instalaciones que ya corren el esquema V3 base.

```sql
-- 1. Añadir el razonamiento profundo a las noticias
-- Propósito: Almacena la explicación en lenguaje natural de por qué la noticia recibió ese impacto_nlp.
ALTER TABLE sentimiento_noticias
ADD COLUMN razonamiento_ia TEXT;

-- 2. Añadir la justificación de entrada al diario de trading
-- Propósito: Almacena el "pensamiento final" del Gerente en el milisegundo exacto en que envió la orden al broker.
ALTER TABLE registro_operaciones
ADD COLUMN justificacion_entrada TEXT;
```
