# 🏗️ AURUM PRISM: Plan de Implementación (Pirámide de Desarrollo)

> **Estado:** Documento de Ejecución Táctica  
> **Regla de Oro:** NADA HARDCOREADO.

Este plan organiza la construcción de **Aurum Prism** desde los cimientos lógicos hasta la interacción estética de alto nivel, asegurando estabilidad y coherencia en cada paso.

---

## 🔝 ÁPICE: Interactividad y Pulido (Nivel 5)
*Toque final que otorga el prestigio "Prism".*
- [ ] **Capa "Polvo de Oro":** Implementación de la refracción dinámica de partículas.
- [ ] **Dashboard Vivo:** Lógica para que la densidad de partículas responda al PnL del día en tiempo real.
- [ ] **Auditoría Forense:** Modales de inspección detallada por trade (Autopsia de obreros).

## 📊 NIVEL 4: Inteligencia de Datos (Visualización)
*Donde la rentabilidad se vuelve visible.*
- [ ] **The Upper-Deck:** Implementación de la barra de poder (Equity/PnL) conectada a la DB.
- [ ] **La Matriz de Refracción:** Tabla maestra de trades con lógica de clasificación dinámica de activos.
- [ ] **AI Insights:** Integración del razonamiento de Gemini (`cache_nlp_impactos`) en la tabla.

## 🔑 NIVEL 3: Autenticación y Acceso (La Puerta)
*Primer contacto con el entorno Aurum Prism.*
- [ ] **Portal de Login:** Construcción de la interfaz bajo la **Opción B (Oro Líquido)**.
- [ ] **Controlador de Sesiones:** Gestión de tokens JWT y persistencia basada en la tabla `prism_sesiones`.
- [ ] **Middleware de Protección:** Solo usuarios autenticados acceden a los datos de trading.

## 🎨 NIVEL 2: ADN Visual (Design System)
*La estructura estética que sostiene la Regla de Oro.*
- [ ] **Configuración de Tailwind Prism:** Definición del mapa de degradados metálicos y colores institucionales.
- [ ] **Librería de Componentes:** Creación de tarjetas (Cards), botones "Gold Leaf" y tipografía *Playfair Display*.
- [ ] **Layout Base:** El lienzo `bg-stone-50` y la estructura de navegación minimalista.

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
