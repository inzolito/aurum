# 💎 AURUM PRISM — PENDIENTES DEL DASHBOARD

> [!IMPORTANT]
> **INSTRUCCIÓN PARA EL AGENTE:** Toda tarea de este documento que sea marcada como **COMPLETADA** o cualquier cambio técnico realizado en el código **DEBE** ser documentado inmediatamente en el archivo `docs/HISTORIAL.md`. No se considera terminada una tarea hasta que su bitácora de cambios esté registrada cronológicamente en el historial.

> **Propósito:** Hoja de Ruta del Frontend. Registro de tareas activas para la construcción de la interfaz Aurum Prism.

---

## 🏆 LA REGLA DE ORO
> **NADA HARDCOREADO.**
> Queda terminantemente prohibido el uso de valores estáticos dentro del código del dashboard. Todo debe ser dinámico y configurable.

---
**Última actualización:** 2026-03-12

---

## 🗓️ ETAPA 1: INFRAESTRUCTURA Y LOGIN

- [x] **Despliegue de DB Schema:** Crear las tablas `prism_usuarios`, `prism_sesiones`, `prism_preferencias` y `prism_log_seguridad` en la base de datos de GCP.
- [ ] **Configuración de Tailwind (Prism Theme):** Definir el mapa de degradados "Gold Liquid" y "Light Gold Digital" en el archivo de configuración.
- [ ] **Prototipo de Login (Opción B):** Implementar la interfaz de login con el fondo de oro líquido y el efecto de refracción al mover el cursor.
- [ ] **Sistema de Auth:** Implementar el backend de autenticación (JWT o sesiones persistentes) vinculado a las nuevas tablas.

---

## 🗓️ ETAPA 2: PANEL DE CONTROL (PRISM VIEW)

- [ ] **Upper-Deck dinámico:** Conectar los indicadores de Equity y PnL Diario con los datos reales de la cuenta de trading.
- [ ] **Filtros Inteligentes:** Implementar la lógica de filtrado por versión del bot y ventana temporal.
- [ ] **Matriz de Refracción (Tabla Maestra):** Construir la tabla de historial enriquecida con los análisis de los 8 obreros.
- [ ] **Etiquetado Automático:** Desarrollar el parser dinámico para clasificar Activos (Metales, Índices, Forex) automáticamente.

---

## 🗓️ ETAPA 3: INTERACTIVIDAD Y PULIDO

- [ ] **Velo de Midas / Polvo de Oro:** Ajustar la densidad de las partículas según el PnL del día (Dashboard "Vivo").
- [ ] **Análisis Forense UI:** Crear las tarjetas laterales de "Inspeccionar Obreros" para autopsias forenses de trades perdedores.
- [ ] **Modo Supervivencia Visual:** Definir la estética de alerta cuando el bot entra en modo supervivencia.
