#!/bin/bash
# =============================================================================
# Aurum — Script de actualización (ejecutado desde el dashboard o manualmente)
# Uso: bash /opt/aurum/scripts/update.sh
# =============================================================================
set -e
AURUM_DIR="/opt/aurum"
LOG_FILE="/tmp/aurum_update_$(date +%s).log"
FRONTEND_DIR="$AURUM_DIR/dashboard/frontend"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "=== Aurum Update iniciado ==="

# 1. Git — forzar sincronización con origin (ignora cambios locales)
log "Sincronizando con Git..."
cd "$AURUM_DIR"
git fetch origin 2>&1 | tee -a "$LOG_FILE"
git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE"

# 2. Dependencias Python (por si hay nuevas)
log "Verificando dependencias Python..."
"$AURUM_DIR/venv/bin/pip" install --quiet -r "$AURUM_DIR/requirements_linux.txt" 2>&1 | tee -a "$LOG_FILE" || true

# 3. Build frontend
log "Compilando frontend..."
cd "$FRONTEND_DIR"

# Arreglar permisos del dist antes de compilar (evita EACCES al limpiar)
if [ -d dist ]; then
    sudo chown -R "$(whoami)":"$(whoami)" dist 2>/dev/null || true
fi

npm run build 2>&1 | tee -a "$LOG_FILE"

# Devolver ownership al usuario del servicio
sudo chown -R aurum_bot:aurum_bot dist 2>&1 | tee -a "$LOG_FILE"

# 4. Reiniciar servicios del bot
log "Reiniciando servicios del bot..."
sudo systemctl restart aurum-core aurum-hunter aurum-telegram 2>&1 | tee -a "$LOG_FILE"

log "=== Update completado ==="
cat "$LOG_FILE"
