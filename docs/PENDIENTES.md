# AURUM — TAREAS PENDIENTES
**Última actualización:** 2026-03-10

---

## P-1: Actualización de Motor IA a Gemini 3.1 🟢
- **Tarea:** Cambiar el modelo en `workers/worker_nlp.py`.
- **Nuevo modelo:** `gemini-3.1-flash-lite`.
- **Objetivo:** Mayor velocidad y menor latencia en las respuestas.

## P-2: Optimización de Latencia y Caché NLP ⚡
- **Tarea:** Modificar la lógica de refresco en `workers/worker_nlp.py`.
- **Cambio 1:** Reducir `NLP_CACHE_TTL_MIN` de 30 minutos a **5 minutos**.
- **Cambio 2:** Forzar un análisis inmediato si el hash de noticias detecta **cualquier cambio**, independientemente de su relevancia inicial (eliminar filtros de relevancia previos para el trigger).

## P-3: Ajuste de Sensibilidad de Activación NLP 🚦
- **Tarea:** Modificar el umbral de activación en `core/manager.py`.
- **Cambio:** Bajar la convicción técnica mínima requerida (`_UMBRAL_PROXIMIDAD`) de 0.38 a **0.15**.
- **Objetivo:** Que la IA participe mucho más frecuentemente en el proceso de decisión, incluso con señales técnicas débiles.

---
*Este documento contiene el trabajo activo para la versión V14. Las tareas completadas se mueven a `HISTORIAL.md`.*
