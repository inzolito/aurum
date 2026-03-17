# 🌐 Infraestructura Aurum - Google Cloud Platform

Este documento detalla la arquitectura de red y servidores del ecosistema Aurum para garantizar la continuidad operativa y facilitar el acceso a futuros agentes de desarrollo.

## 🏗️ Resumen de Arquitectura

El sistema está distribuido en múltiples proyectos de Google Cloud para separar la base de datos principal de las aplicaciones web.

---

## 🗄️ Base de Datos Principal (PostgreSQL)

Contrario a la configuración estándar de Cloud SQL, la base de datos de Aurum corre en una **Máquina Virtual (GCE)** para mayor control operacional.

- **Proyecto:** `aurum-489120`
- **Instancia VM:** `aurum-server`
- **IP Externa:** `35.239.183.207`
- **Puerto:** `5432` (TCP)
- **Base de Datos:** `aurum_db`
- **Usuario Admin:** `aurum_admin`

### 🛡️ Configuración de Firewall (Ingreso)
El acceso a la base de datos está restringido por reglas de firewall en el proyecto `aurum-489120`:

| Regla | Propósito | Rango IP Autorizado |
|-------|-----------|----------------------|
| `allow-postgres-aurum` | Acceso para el Bot / Servidores Core | `152.174.0.0/16` |
| `allow-postgres-surface` | Acceso desde la Surface Pro del usuario | `152.174.0.0/16` |
| `allow-postgres-cloudrun` | **Acceso para Dashboard Prism** | `35.199.224.0/19` |

> [!IMPORTANT]
> La regla `allow-postgres-cloudrun` permite que el dashboard en Cloud Run se conecte sin usar un Proxy de Cloud SQL, ya que la DB está en una VM estándar.

---

## 📊 Dashboard Aurum Prism

El Dashboard está construido con arquitectura de microservicios y desplegado en **Cloud Run**.

- **Proyecto:** `maikbottrade`
- **Región:** `us-central1`

### Componentes:
1. **Prism Backend (FastAPI):**
   - **URL:** `https://prism-backend-419965139801.us-central1.run.app`
   - **Responsabilidad:** Gestión de usuarios (`prism_usuarios`), autenticación JWT y puente de datos con la VM de base de datos.
2. **Prism Frontend (React/Vite):**
   - **URL:** `https://prism-frontend-419965139801.us-central1.run.app`
   - **Responsabilidad:** Interfaz de usuario operativa.

---

## 🤖 Otros Servicios

### Analytica System
Antiguo sistema de análisis, también alojado en el proyecto `maikbottrade`.
- **Backend:** `analytica-backend` (Cloud Run)
- **Frontend:** `analytica-frontend` (Cloud Run / VM)
- **DB Analytica:** `analytica-db` (Instancia de Cloud SQL - IP `34.55.159.178`).

---

## 📝 Notas para Agentes
1. **Variables de Entorno:** Siempre revisar el archivo `.env` en la raíz de `c:\www\Aurum` para las credenciales actualizadas (Host: `35.239.183.207`).
2. **Conexión:** Si el Dashboard pierde conexión, verificar que la IP externa de la VM `aurum-server` no haya cambiado (actualmente estática).
3. **Despliegue:** Para actualizar el dashboard, usar los archivos `dashboard/*_cloudbuild.yaml`.

---
*Última actualización: 2026-03-16 por Antigravity*
