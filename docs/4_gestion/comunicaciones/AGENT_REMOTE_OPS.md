# AGENT_REMOTE_OPS — Aurum Infrastructure Reference

Este documento sirve como guía para que futuros agentes de IA operen sobre la infraestructura de Aurum de forma eficiente.

## 🚀 Conexión Rápida (GCP)
- **Proyecto:** `aurum-489120`
- **VM:** `aurum-server` (us-central1-a)
- **Túnel IAP:** Indispensable debido al firewall.
  ```powershell
  gcloud compute ssh aurum-server --project=aurum-489120 --zone=us-central1-a --quiet --tunnel-through-iap --command="[COMMAND]"
  ```

## 🛠️ Operaciones Comunes
1. **Ejecutar Python (Venv):**
   - El entorno virtual está en `/opt/aurum/venv`.
   - Comando: `/opt/aurum/venv/bin/python3 /path/to/script.py`
2. **Base de Datos:**
   - Host: `localhost` (desde dentro del VM).
   - Credenciales: `/opt/aurum/.env`.
3. **Mantenimiento:**
   - Reiniciar bot: `sudo systemctl restart aurum-core`
   - Logs: `sudo journalctl -u aurum-core -n 100 --no-pager`

## 📂 Estructura Remota
- `/opt/aurum/`: Directorio raíz del proyecto.
- `/opt/aurum/core/`: Lógica principal del bot.
- `/opt/aurum/config/`: Conectores y configuración (incluyendo `db_connector.py`).

---
*Documento autogenerado para optimización de tokens y eficiencia operativa.*
