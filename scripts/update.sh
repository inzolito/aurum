#!/bin/bash
# =============================================================================
# Aurum — Script de actualización local (ejecutar en el VM)
# Uso: bash /opt/aurum/scripts/update.sh
# =============================================================================
set -e
AURUM_DIR="/opt/aurum"
LOG_FILE="/tmp/aurum_update_$(date +%s).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "=== Aurum Update iniciado ==="

# 1. Git pull
log "Descargando cambios de Git..."
cd "$AURUM_DIR"
git pull origin main 2>&1 | tee -a "$LOG_FILE"

# 2. Dependencias Python (por si hay nuevas)
log "Verificando dependencias Python..."
"$AURUM_DIR/venv/bin/pip" install --quiet -r "$AURUM_DIR/requirements_linux.txt" 2>&1 | tee -a "$LOG_FILE" || true

# 3. Build frontend
log "Compilando frontend..."
cd "$AURUM_DIR/dashboard/frontend"
npm run build 2>&1 | tee -a "$LOG_FILE"
chown -R aurum_bot:aurum_bot "$AURUM_DIR/dashboard/frontend/dist"

# 4. Reiniciar servicios del bot
log "Reiniciando servicios del bot..."
sudo systemctl restart aurum-core aurum-hunter aurum-telegram 2>&1 | tee -a "$LOG_FILE"

log "=== Update completado ==="
cat "$LOG_FILE"
