#!/bin/bash
# =============================================================================
# Aurum — Script de actualización (ejecutado desde el dashboard o manualmente)
# El frontend se buildea LOCALMENTE y se commitea al repo (dist/ trackeado en git).
# El servidor NUNCA corre npm build — evita OOM en e2-micro.
# =============================================================================
set -e
AURUM_DIR="/opt/aurum"
LOG_FILE="/tmp/aurum_update_$(date +%s).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "=== Aurum Update iniciado ==="

# 1. Git — forzar sincronización con origin
log "Sincronizando con Git..."
cd "$AURUM_DIR"
git fetch origin 2>&1 | tee -a "$LOG_FILE"
git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE"

# 2. Dependencias Python (por si hay nuevas)
log "Verificando dependencias Python..."
"$AURUM_DIR/venv/bin/pip" install --quiet -r "$AURUM_DIR/requirements_linux.txt" 2>&1 | tee -a "$LOG_FILE" || true

# 3. Reiniciar servicios del bot
log "Reiniciando servicios..."
sudo systemctl restart aurum-core     2>&1 | tee -a "$LOG_FILE"
sudo systemctl restart aurum-hunter   2>&1 | tee -a "$LOG_FILE"
sudo systemctl restart aurum-telegram 2>&1 | tee -a "$LOG_FILE"
# aurum-dashboard se reinicia solo desde el backend después de responder al cliente

log "=== Update completado ==="
cat "$LOG_FILE"
