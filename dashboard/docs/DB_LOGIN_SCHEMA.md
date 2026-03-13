# 🗄️ Esquema de Base de Datos: Dashboard AURUM PRISM

Este documento define la estructura de las tablas necesarias para el sistema de autenticación y gestión del dashboard, integradas en la base de datos actual de Aurum.

---

## 🔐 1. Tabla: `prism_usuarios`
Almacena las credenciales y perfiles de acceso.

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | SERIAL (PK) | Identificador único del usuario. |
| `usuario` | VARCHAR(50) | Nombre de usuario (Unique). |
| `password_hash` | TEXT | Hash de la contraseña (Bcrypt/Argon2). |
| `email` | VARCHAR(100) | Correo electrónico para recuperación/alertas. |
| `rol` | VARCHAR(20) | Nivel de acceso (`SUPER_ADMIN`, `AUDITOR`). |
| `creado_en` | TIMESTAMP | Fecha de registro. |
| `ultimo_acceso` | TIMESTAMP | Registro del último login exitoso. |
| `estado` | BOOLEAN | `TRUE` para activo, `FALSE` para bloqueo. |

---

## 🎟️ 2. Tabla: `prism_sesiones`
Gestión de tokens y persistencia de sesión para evitar reconexiones constantes.

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Identificador único de sesión. |
| `usuario_id` | INTEGER (FK) | Relación con `prism_usuarios`. |
| `token` | TEXT | Token de sesión JWT o persistente. |
| `ip_origen` | VARCHAR(45) | IP desde donde se conectó. |
| `user_agent` | TEXT | Dispositivo/Navegador del usuario. |
| `creado_en` | TIMESTAMP | Inicio de la sesión. |
| `expira_en` | TIMESTAMP | Tiempo de vida de la sesión (ej. 24h). |

---

## 🎨 3. Tabla: `prism_preferencias`
Almacena la configuración estética personalizada de Maikol.

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `usuario_id` | INTEGER (FK) | Relación con `prism_usuarios`. |
| `tema_visual` | VARCHAR(20) | `LIGHT_GOLD` (Opción A) o `LIQUID_GOLD` (Opción B). |
| `efecto_velo` | BOOLEAN | Activar/Desactivar partículas Velo de Midas / Polvo de Oro. |
| `densidad_particulas` | FLOAT | Ajuste de sensibilidad del efecto visual (refacción). |
| `activos_favoritos` | TEXT[] | Lista de símbolos que se muestran por defecto en el dashboard. |

---

## 🚨 4. Tabla: `prism_log_seguridad`
Auditoría de intentos de acceso para detectar fuerza bruta.

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | SERIAL (PK) | ID del evento. |
| `usuario_intento` | VARCHAR(50) | Nombre de usuario ingresado. |
| `evento` | VARCHAR(50) | `LOGIN_EXITOSO`, `LOGIN_FALLIDO`, `LOGOUT`. |
| `ip_origen` | VARCHAR(45) | IP del evento. |
| `fecha_hora` | TIMESTAMP | Momento exacto del evento. |

---

## 🛠️ Notas de Implementación
1. **Seguridad:** No se almacenarán contraseñas en texto plano por normativas de seguridad de Aurum Prism. Se usará un hash robusto.
2. **Integración:** Estas tablas vivirán en la base de datos `aurum_db` coexistiendo con el motor de trading actual.
3. **Escalabilidad:** El prefijo `prism_` asegura que no haya colisiones con tablas futuras del bot principal.

---
*Documento de Planificación — 2026-03-12*
