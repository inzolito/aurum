# 🌌 AURUM PRISM: Documento Maestro de Arquitectura y Planificación

> **Estado:** Borrador de Arquitectura (Etapa 1)  
> **Concepto:** Consolidación de datos y gestión operativa mediante una interfaz técnica funcional.

AURUM PRISM es el centro de control diseñado para centralizar la información de los 8 agentes operativos, permitiendo una supervisión técnica precisa de la cuenta de trading.

---

## 🏆 LA REGLA DE ORO (IRROMPIBLE)
> **NADA HARDCOREADO.**
> Todo dato, parámetro, umbral, dirección de servidor o configuración estética debe provenir de una fuente dinámica (Base de Datos, Variables de Entorno o Configuración de Usuario). El código debe ser una estructura pura que se alimenta de datos, nunca un contenedor de valores estáticos.

---

## 🏛️ I. Visión Estratégica
El dashboard abre por defecto en **"AURUM PRISM: Hoy"**. Su objetivo principal es permitir la verificación inmediata del impacto de parches operativos y la salud del capital en tiempo real, eliminando la "ceguera" de los logs de consola mediante una interfaz de alta fidelidad.

---

## 🏗️ II. Arquitectura Funcional
*Aplicable a todas las rutas estéticas:*

1. **Upper-Deck (Panel de Indicadores):** Visualización en tiempo real de Equity y PnL Diario.
2. **Filtros Operativos:** Selectores para Versión, Categoría y Tiempo.
3. **Estructura del Historial:** Tabla técnica de operaciones con integración de análisis de IA.

---

## 🏗️ III. Interfaz de Acceso y Seguridad
El sistema implementa un portal de autenticación centralizado gestionado por el backend de Aurum.

### 1. Sistema de Autenticación
- **Control de Acceso:** Gestión de usuarios mediante tabla `prism_usuarios`.
- **Persistencia:** Uso de tokens para mantener la sesión activa según parámetros de seguridad.
- **Validación:** Middleware encargado de verificar la identidad antes de exponer datos sensibles del trading.

---

## 🛠️ V. Especificaciones Técnicas Comunes

### Tipografía y Estilo Base
- **Fuentes:** Se utilizarán fuentes estándar de alta legibilidad para datos numéricos y técnicos.
- **Layout:** Estructura limpia enfocada en la densidad de información y respuesta inmediata.

---

## 🗄️ VI. Infraestructura de Datos (Prism Backbone)
Para cumplir con la **Regla de Oro**, el dashboard se apoya en una estructura de base de datos relacional (PostgreSQL en GCP) que gestiona la persistencia y el dinamismo total de la interfaz.

### 1. Motor de Autenticación y Preferencias
Las tablas con prefijo `prism_` gestionan la identidad y la estética sin tocar el código:
- **`prism_usuarios`:** Credenciales y roles.
- **`prism_sesiones`:** Persistencia y seguridad JWT.
- **`prism_preferencias`:** Almacena la configuración técnica y parámetros de visualización del usuario.
- **`prism_log_seguridad`:** Auditoría de accesos.

### 2. Integración con el Motor Aurum
El dashboard actúa como un "Prisma de Lectura" sobre las tablas operativas:
- **`registro_operaciones`:** Fuente primaria para el Upper-Deck y Historial.
- **`parametros_sistema`:** Fuente dinámica para mostrar los pesos de los obreros y umbrales de riesgo.
- **`cache_nlp_impactos`:** Provee el razonamiento de Gemini para la columna de "Pensamiento IA".

---

## 🛡️ Veredicto de Diseño
Maikol, **AURUM PRISM** redefine la vigilancia del mercado mediante una arquitectura técnica robusta. Todo el sistema está diseñado para que el código permanezca puro y dinámico, proporcionando una herramienta analítica de alto nivel sin distracciones accesorias.

---
*Documento generado por Antigravity para Maikol — 2026-03-12*
