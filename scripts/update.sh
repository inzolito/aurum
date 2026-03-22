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
# Asegurar permisos correctos antes del reset (evita error en dist/assets/)
chown -R aurum_bot:root "$AURUM_DIR/dashboard/frontend/dist/" 2>/dev/null || true
chown -R aurum_bot:root "$AURUM_DIR/.git/" 2>/dev/null || true
git fetch origin 2>&1 | tee -a "$LOG_FILE"
git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE"

# 2. Dependencias Python (por si hay nuevas)
log "Verificando dependencias Python..."
"$AURUM_DIR/venv/bin/pip" install --quiet -r "$AURUM_DIR/requirements_linux.txt" 2>&1 | tee -a "$LOG_FILE" || true

# 3. Resetear latido DB para evitar que el Shield mate el bot por timestamp viejo
log "Reseteando latido en BD..."
"$AURUM_DIR/venv/bin/python" -c "
import os, sys
sys.path.insert(0, '$AURUM_DIR')
from dotenv import load_dotenv
load_dotenv('$AURUM_DIR/.env')
from config.db_connector import DBConnector
db = DBConnector()
if db.conectar():
    db.cursor.execute(\"UPDATE estado_bot SET tiempo = NOW() WHERE id = 1;\")
    db.conn.commit()
    print('[UPDATE] Latido reseteado OK')
else:
    print('[UPDATE] WARN: No se pudo conectar a DB para resetear latido')
" 2>&1 | tee -a "$LOG_FILE" || true

# 4. Reiniciar servicios del bot
log "Reiniciando servicios..."
sudo systemctl restart aurum-core     2>&1 | tee -a "$LOG_FILE"
sudo systemctl restart aurum-hunter   2>&1 | tee -a "$LOG_FILE"
sudo systemctl restart aurum-telegram 2>&1 | tee -a "$LOG_FILE"
# aurum-dashboard se reinicia solo desde el backend después de responder al cliente

log "=== Update completado ==="
cat "$LOG_FILE"
