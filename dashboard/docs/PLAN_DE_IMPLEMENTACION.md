# 🏗️ AURUM PRISM: Plan de Implementación (Pirámide de Desarrollo)

> **Estado:** Documento de Ejecución Táctica  
> **Regla de Oro:** NADA HARDCOREADO.

Este plan organiza la construcción de **Aurum Prism** desde los cimientos lógicos hasta la interacción de usuario final, asegurando estabilidad y coherencia en cada paso.

---

## 🔝 ÁPICE: Interactividad y Pulido (Nivel 5)
*Toque final que otorga la funcionalidad completa del sistema.*
- [ ] **Optimización UI:** Ajuste de la respuesta visual de la interfaz según el flujo de datos.
- [ ] **Dashboard Técnico:** Consolidación de la vista principal con indicadores de rendimiento en tiempo real.
- [ ] **Auditoría Forense:** Módulos de inspección detallada por trade.

## 🚀 NIVEL CLOUD: Infraestructura en Google Cloud (Online)
*Garantizando disponibilidad total desde cualquier lugar.*
- [ ] **Dockerización de Prism:** Creación del `Dockerfile` optimizado para el entorno de producción.
- [ ] **Cloud Run Deployment:** Despliegue del dashboard en GCP para disponibilidad 24/7.
- [ ] **Punto de Enlace:** Configuración de la URL/IP pública de acceso para Maikol.

## 📊 NIVEL 4: Inteligencia de Datos (Visualización)
*Donde la rentabilidad se vuelve visible.*
- [ ] **The Upper-Deck:** Implementación de la barra de poder (Equity/PnL) conectada a la DB.
- [ ] **Módulo Histórico:** Tabla técnica de trades con lógica de clasificación dinámica de activos.
- [ ] **AI Insights:** Integración del razonamiento de Gemini (`cache_nlp_impactos`) en la tabla.

## 🔑 NIVEL 3: Autenticación y Acceso (La Puerta)
*Primer contacto con el entorno Aurum Prism.*
- [ ] **Portal de Login:** Implementación de la interfaz de acceso protegida.
- [ ] **Controlador de Sesiones:** Gestión de tokens y persistencia basada en la tabla `prism_sesiones`.
- [ ] **Middleware de Protección:** Restricción de acceso a datos de trading para usuarios no autorizados.

## 🎨 NIVEL 2: ADN Visual (Design System)
*La estructura estética que sostiene la Regla de Oro.*
- [ ] **Diseño Base:** Implementación del sistema de componentes técnicos y tipografía funcional.
- [ ] **Librería de Componentes:** Creación de tarjetas y elementos de control estandarizados.
- [ ] **Layout Estructural:** Definición de la estructura de navegación y contenedores de datos.

## 🔌 NIVEL 1: El Puente Lógico (Backend)
*La tubería que alimenta la interfaz.*
- [ ] **Conector de Base de Datos:** Lógica de conexión segura a la DB actual de Aurum en GCP.
- [ ] **Cargador Dinámico:** Sistema de carga de parámetros (evitando hardcoding) desde `parametros_sistema` y `.env`.

## 🪨 NIVEL 0: El Cimiento (DB y Entorno)
*La base irrompible sobre la que se apoya todo.*
- [ ] **Esquema de Datos Prism:** Ejecución del script SQL para crear las tablas `prism_*` (Usuarios, Sesiones, Preferencias).
- [ ] **Variables de Entorno:** Configuración de claves JWT, URIs de base de datos y secretos del servidor.

---

## 🛡️ Estrategia de Avance
Se avanzará de forma estrictamente ascendente (**Nivel 0 → Nivel 5**). No se implementará estética (Nivel 2) si los cimientos de datos (Nivel 0) no están validados. Cada etapa completada debe ser registrada en el `HISTORIAL.md` con su impacto técnico detallado.

---
*Plan de Implementación v1.0 — Aurum Prism*
