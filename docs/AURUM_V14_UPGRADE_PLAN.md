# AURUM — UPGRADE PLAN

> **Propósito:** Visión Estratégica. Planificación de grandes cambios de versión y objetivos a largo plazo. Define las eras del bot y la dirección general del sistema (Seguridad, IA Forense, etc.).

Este documento detalla el plan estratégico para evolucionar el Ecosistema Aurum de su versión actual V13.5 a la versión V14.0.

---

## 1. Mejoras en la Inteligencia (Cerebro IA)
Integración de razonamiento crítico para transformar la IA de un "analista de sentimiento" a un "estratega de ejecución".

### 1.1 Autopsia de Pérdidas (Post-Trade)
- **Función**: Análisis automático de cada Stop Loss para identificar fallos técnicos o de contexto.
- **Persistencia Crítica**: El sistema **no debe borrar la justificación original de la entrada**. La IA debe contrastar el razonamiento inicial (por qué se entró) contra el resultado final (por qué falló) para identificar sesgos o errores de lógica específicos en el momento de la ejecución.
- **Beneficio**: Evita repetir errores y ajusta los pesos de los obreros dinámicamente basados en evidencia histórica comparativa.

### 1.2 IA-Risk (Riesgo Dinámico)
- **Función**: Ajuste del lotaje y riesgo por trade basado en la volatilidad real y la tensión de noticias.
- **Beneficio**: Protección máxima en mercados inciertos y mayor agresividad en escenarios claros.

---

## 2. Refuerzo de la Arquitectura (Obreros Faltantes)
Completar la visión de la arquitectura "Ensemble" original.

### 2.1 SpreadWorker (Liquidez Institucional)
- **Función**: Monitoreo del spread Bid/Ask en tiempo real.
- **Beneficio**: Detectar cuando los grandes bancos están retirando liquidez para evitar entradas en momentos de alto costo de operación.

### 2.2 VIXWorker (Métrica de Miedo)
- **Función**: Integrar la volatilidad implícita como filtro de seguridad.
- **Beneficio**: Impedir que el bot opere si el mercado está en un estado de pánico que invalida el análisis técnico.

---

## 3. Estabilidad y Operación (Core Fixes)
Mejoras en la estabilidad diaria del sistema.

### 3.1 Unificación de Instancia (Named Mutex)
- **Función**: Implementar un bloqueo atómico a nivel de sistema operativo para evitar que el bot se abra dos veces al mismo tiempo.
- **Beneficio**: Eliminar los conflictos de Telegram y errores de base de datos por procesos duplicados.

### 3.2 Panel Aurum Admin
- **Función**: Creación de una terminal interactiva centralizada.
- **Beneficio**: Control total sin necesidad de abrir el código; ver votos, estados y noticias de un solo vistazo.

---

## 4. Gestión de Datos y Correlación
- **Correlación Cruzada**: La IA evaluará si el Oro, el Dólar y los Índices están alineados antes de autorizar un trade.
- **Filtro de Ruido**: Limpieza del feed de noticias para ignorar rumores de baja calidad ("fake news").

---

## P-3: Ajuste de Sensibilidad de Activación NLP 🚦
- **Tarea:** Modificar el umbral de activación en `core/manager.py`.
- **Cambio:** Bajar la convicción técnica mínima requerida (`_UMBRAL_PROXIMIDAD`) de 0.38 a **0.15**.
- **Objetivo:** Que la IA participe mucho más frecuentemente en el proceso de decisión, incluso con señales técnicas débiles.

## P-4: Módulo de Memoria de Apertura (Gap & Level Guard) 🧠
- **Tarea:** Crear un sistema que capture la "Foto de Cierre" los viernes a las 17:59.
- **Datos a guardar:** Último POC (Volumen), Order Blocks activos (Sniper) y Veredicto NLP residual.
- **Objetivo:** Que el bot detecte GAPs en la apertura del domingo y use los niveles del viernes como puntos de referencia inmediatos.

## P-5: Sentimiento Continuo 24/7 🗞️
- **Tarea:** Asegurar que `news_hunter.py` y el procesamiento de `worker_nlp.py` se mantengan activos durante todo el fin de semana (Modo Vigilancia).
- **Objetivo:** Que el bot llegue a la apertura del domingo con una lectura realista y acumulada del sentimiento global, sin "puntos ciegos".

---

## 7. Control de Tiempo y Ventanas de Liquidez 🕒
Optimizar la ejecución de trades limitando la actividad del bot a horarios de alta probabilidad y reduciendo la exposición al ruido de mercado.

### 7.1 Gestión de Apertura (Anti-Volatilidad)
- **Función**: Implementar un retraso configurable (ej. 20-30 min) tras la apertura de los mercados principales.
- **Beneficio**: Evitar "latigazos" de precios y spreads excesivamente altos que ocurren en el primer contacto con el mercado.

### 7.2 Horarios de Operación (Ventanas de Liquidez)
- **Función**: Definir rangos específicos de trading para sincronizar la actividad con las sesiones de mayor volatilidad y liquidez (Londres/Nueva York).
- **Beneficio**: Concentrar el capital y la atención del bot en momentos donde los movimientos tienen mayor sustento institucional.

---
*Este documento contiene el trabajo activo para la versión V14. Las tareas completadas se mueven a `HISTORIAL.md`.*
