# 🌌 AURUM PRISM: Documento Maestro de Diseño y Planificación

> **Estado:** Borrador de Arquitectura y Estética (Etapa 1)  
> **Concepto:** Claridad Cristalina y Refracción de Datos para el Máximo Rendimiento.

"Prism" representa la capacidad de descomponer la complejidad del mercado en sus componentes fundamentales. Al igual que un prisma refracta la luz blanca en un espectro de colores, AURUM PRISM desglosa los datos del mercado a través de nuestros 8 agentes para ofrecer una visión clara, analítica y accionable.

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

1. **Upper-Deck (La Barra de Poder):** Números en Oro Pulido sobre relieve sutil. Equity y PnL Diario con lógica de color (Verde/Rojo suave sobre base cálida).
2. **Panel de Control:** Selectores atómicos para Versión, Categoría y Tiempo.
3. **Estructura del Historial:** Tabla maestra con Tesis de IA y Análisis Post-Mortem. Insignias visuales de Activo y Dirección.

---

## ✨ III. OPCIÓN A: Identidad "Light Gold Digital"
Se rompe con la tradición de dashboards oscuros para proyectar confianza y transparencia absoluta.

- **Filosofía:** No te escondes en la oscuridad, operas con la luz de la rentabilidad.
- **Base:** Blanco Marfil o Crema de Seda (`bg-stone-50`).
- **Capa de Interacción (Velo de Midas):** Red de partículas doradas (`amber-400` al 20%) que interactúan con el cursor, conectándose como filamentos de oro puro, simulando una estructura cristalina en movimiento.

### Paleta de Colores (Opción A)
| Elemento | Clase Tailwind | Descripción |
| :--- | :--- | :--- |
| Fondo Principal | `bg-stone-50` | Limpio, brillante y premium. |
| Texto Dorado | `text-amber-600` | Para legibilidad en títulos y marcas. |
| Bordes de Lujo | `border-gold-gradient` | Degradado de metal líquido. |

---

## 🏆 IV. OPCIÓN B: Identidad "Oro Líquido Minimalista"
Inmersión total. No es una página con detalles dorados; es entrar en el dominio del metal precioso bajo un prisma de luz.

### 1. Fondo Principal: Lámina de Oro Pulida
Degradado radial que simula una superficie de metal precioso difuminado. Luz cálida, pesada y rica.
- **Tailwind:** `bg-gradient-radial from-amber-300 via-amber-400 to-amber-500`.

### 2. Capa de Interacción: Polvo de Oro en Suspensión
Micro-partículas de luz ámbar flotando como polvo de oro en un rayo de sol.
- **Interacción (Refracción Dinámica):** El cursor actúa como un prisma que concentra las partículas, dibujando filamentos brillantes a su paso.
- **Efecto Login:** Al acercar el mouse al formulario, las partículas se dispersan como luz refractada, despejando la interfaz.

### 3. Interfaz de Login (Contraste Mármol)
Para equilibrar la riqueza del fondo, el contenedor de acceso es un oasis de limpieza.
- **Contenedor:** Blanco Mármol (`from-stone-50 to-stone-100`).
- **Bordes:** Hilo de oro metálico ultra-fino (`border-amber-500/50`).
- **Botón:** "Gold Leaf" con transición de brillo (hover: `brightness-110`).

---

## 🛠️ V. Especificaciones Técnicas Comunes

### Tipografía
- **Títulos:** *Playfair Display* (Serifada elegante). Estilo Maestra/Notarios.
- **Datos Técnicos:** Sans-serif ultra-limpia para máxima legibilidad de números de los obreros.

### Mapa de Degradados Dorados (Tailwind Config)
```javascript
// Configuración para reflejar el espectro PRISM
{
  'gold-metallic': 'linear-gradient(135deg, #FDE68A 0%, #D97706 50%, #B45309 100%)',
  'gold-leaf': 'linear-gradient(to right, #F59E0B, #FBBF24, #F59E0B)',
  'gold-radial-bg': 'radial-gradient(circle, #FCD34D, #F59E0B, #B45309)',
  'champagne-soft': '#F7E7CE'
}
```

---

## 🗄️ VI. Infraestructura de Datos (Prism Backbone)
Para cumplir con la **Regla de Oro**, el dashboard se apoya en una estructura de base de datos relacional (PostgreSQL en GCP) que gestiona la persistencia y el dinamismo total de la interfaz.

### 1. Motor de Autenticación y Preferencias
Las tablas con prefijo `prism_` gestionan la identidad y la estética sin tocar el código:
- **`prism_usuarios`:** Credenciales y roles.
- **`prism_sesiones`:** Persistencia y seguridad JWT.
- **`prism_preferencias`:** Almacena qué opción estética (`LIGHT_GOLD` vs `LIQUID_GOLD`) y qué nivel de refracción de partículas desea el usuario.
- **`prism_log_seguridad`:** Auditoría de accesos.

### 2. Integración con el Motor Aurum
El dashboard actúa como un "Prisma de Lectura" sobre las tablas operativas:
- **`registro_operaciones`:** Fuente primaria para el Upper-Deck y Historial.
- **`parametros_sistema`:** Fuente dinámica para mostrar los pesos de los obreros y umbrales de riesgo.
- **`cache_nlp_impactos`:** Provee el razonamiento de Gemini para la columna de "Pensamiento IA".

---

## 🛡️ Veredicto de Diseño
Maikol, **AURUM PRISM** redefine la vigilancia del mercado. La **Opción A** ofrece una claridad cristalina e institucional, mientras que la **Opción B** sumerge al usuario en la riqueza del oro bajo una luz refractada. Todo sustentado por una base de datos robusta que garantiza que el código permanezca puro y dinámico.

---
*Documento generado por Antigravity para Maikol — 2026-03-12*
