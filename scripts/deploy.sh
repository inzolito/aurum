#!/bin/bash
# =============================================================================
# Aurum — Deploy al VM aurum-server (para Git Bash / WSL / Linux)
# Uso:
#   bash scripts/deploy.sh           # git pull + reinicio
#   bash scripts/deploy.sh --setup   # Primera vez: clone + setup completo
#   bash scripts/deploy.sh --env     # Solo subir .env
# =============================================================================
set -e

PROJECT="aurum-489120"
VM_NAME="aurum-server"
REMOTE_DIR="/opt/aurum"
REPO_URL="https://github.com/inzolito/aurum.git"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ─── Auto-detectar zona ───────────────────────────────────────────────────────
echo "[Deploy] Buscando zona de $VM_NAME..."
ZONE=$(gcloud compute instances list \
    --filter="name=$VM_NAME" \
    --format="value(zone)" \
    --project="$PROJECT" 2>/dev/null | head -1)

if [ -z "$ZONE" ]; then
    echo "ERROR: No se encontro el VM '$VM_NAME' en el proyecto '$PROJECT'."
    exit 1
fi
echo "[Deploy] VM encontrado en zona: $ZONE"

SSH_FLAGS="--project=$PROJECT --zone=$ZONE --ssh-flag=-o --ssh-flag=StrictHostKeyChecking=no --ssh-flag=-o --ssh-flag=UserKnownHostsFile=/dev/null"
SCP_FLAGS="--project=$PROJECT --zone=$ZONE --ssh-flag=-o --ssh-flag=StrictHostKeyChecking=no --ssh-flag=-o --ssh-flag=UserKnownHostsFile=/dev/null"

vm_run() {
    gcloud compute ssh "$VM_NAME" $SSH_FLAGS -- "$@"
}

# ─── MODO: Solo .env ─────────────────────────────────────────────────────────
if [[ "$1" == "--env" ]]; then
    echo "[Deploy] Subiendo .env..."
    gcloud compute scp $SCP_FLAGS "$LOCAL_DIR/.env" "$VM_NAME:$REMOTE_DIR/.env"
    vm_run "sudo chown aurum_bot:root $REMOTE_DIR/.env && sudo chmod 600 $REMOTE_DIR/.env"
    echo "[Deploy] .env actualizado."
    exit 0
fi

# ─── MODO: Primera vez ────────────────────────────────────────────────────────
if [[ "$1" == "--setup" ]]; then
    echo "[Deploy] Modo Setup — primera vez en el VM"
    vm_run "sudo apt-get update -qq && sudo apt-get install -y -qq git python3.11 python3.11-venv python3-pip build-essential libpq-dev"
    vm_run "sudo mkdir -p $REMOTE_DIR && sudo chown \$USER:\$USER $REMOTE_DIR"

    REPO_EXISTS=$(vm_run "test -d $REMOTE_DIR/.git && echo yes || echo no" 2>/dev/null || echo "no")
    if [[ "$REPO_EXISTS" == "yes" ]]; then
        echo "[Deploy] Repo ya existe, haciendo git pull..."
        vm_run "cd $REMOTE_DIR && git pull origin master"
    else
        echo "[Deploy] Clonando repositorio..."
        vm_run "git clone $REPO_URL $REMOTE_DIR"
    fi

    if [ -f "$LOCAL_DIR/.env" ]; then
        echo "[Deploy] Subiendo .env..."
        gcloud compute scp $SCP_FLAGS "$LOCAL_DIR/.env" "$VM_NAME:$REMOTE_DIR/.env"
    fi

    echo "[Deploy] Ejecutando setup_vm.sh..."
    vm_run "bash $REMOTE_DIR/scripts/setup_vm.sh"
    exit 0
fi

# ─── MODO NORMAL: git pull + reinicio ────────────────────────────────────────
echo "[Deploy] Actualizando codigo via git pull..."
vm_run "cd $REMOTE_DIR && git pull origin main"

echo "[Deploy] Actualizando dependencias..."
vm_run "cd $REMOTE_DIR && venv/bin/pip install --quiet -r requirements_linux.txt"

if [ -f "$LOCAL_DIR/.env" ]; then
    echo "[Deploy] Subiendo .env..."
    gcloud compute scp $SCP_FLAGS "$LOCAL_DIR/.env" "$VM_NAME:$REMOTE_DIR/.env"
    vm_run "sudo chown aurum_bot:root $REMOTE_DIR/.env && sudo chmod 600 $REMOTE_DIR/.env"
fi

if [[ "$1" != "--no-restart" ]]; then
    echo "[Deploy] Reiniciando servicios..."
    vm_run "sudo systemctl restart aurum-core aurum-hunter aurum-telegram aurum-dashboard && sleep 2 && sudo systemctl status aurum-core aurum-hunter aurum-telegram aurum-dashboard --no-pager"
fi

echo ""
echo "Deploy completado."
