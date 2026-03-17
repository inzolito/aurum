# =============================================================================
# Aurum — Deploy al VM aurum-server desde Windows
# Requiere: gcloud CLI instalado y autenticado (gcloud auth login)
# Uso:
#   .\scripts\deploy.ps1              # Solo git pull + reinicio
#   .\scripts\deploy.ps1 -Setup       # Primera vez: clone + setup completo
#   .\scripts\deploy.ps1 -EnvOnly     # Solo subir el .env
# =============================================================================

param(
    [switch]$Setup,      # Primera vez en el VM
    [switch]$EnvOnly,    # Solo actualizar .env
    [switch]$NoRestart   # No reiniciar servicios al final
)

$ErrorActionPreference = "Stop"

# ─── Configuración ────────────────────────────────────────────────────────────
$PROJECT    = "aurum-489120"
$VM_NAME    = "aurum-server"
$REMOTE_DIR = "/opt/aurum"
$REPO_URL   = "https://github.com/inzolito/aurum.git"
$LOCAL_DIR  = Split-Path -Parent $PSScriptRoot   # raíz del proyecto

# ─── Auto-detectar zona ───────────────────────────────────────────────────────
Write-Host "[Deploy] Buscando zona de $VM_NAME..." -ForegroundColor Cyan
$ZONE = gcloud compute instances list `
    --filter="name=$VM_NAME" `
    --format="value(zone)" `
    --project="$PROJECT" 2>$null | Select-Object -First 1

if (-not $ZONE) {
    Write-Error "No se encontro el VM '$VM_NAME' en el proyecto '$PROJECT'."
    Write-Host "Verifica: gcloud compute instances list --project=$PROJECT"
    exit 1
}
Write-Host "[Deploy] VM encontrado en zona: $ZONE" -ForegroundColor Green

# Helper: ejecutar comando en el VM via SSH
function Invoke-VM {
    param([string]$Command)
    gcloud compute ssh $VM_NAME `
        --project=$PROJECT `
        --zone=$ZONE `
        --command=$Command
}

# ─── MODO: Solo subir .env ────────────────────────────────────────────────────
if ($EnvOnly) {
    Write-Host "[Deploy] Subiendo .env al VM..." -ForegroundColor Cyan
    $envPath = Join-Path $LOCAL_DIR ".env"
    if (-not (Test-Path $envPath)) {
        Write-Error "No se encontro .env en $envPath"
        exit 1
    }
    gcloud compute scp `
        --project=$PROJECT `
        --zone=$ZONE `
        $envPath `
        "${VM_NAME}:${REMOTE_DIR}/.env"
    Invoke-VM "sudo chown aurum_bot:root $REMOTE_DIR/.env && sudo chmod 600 $REMOTE_DIR/.env"
    Write-Host "[Deploy] .env actualizado." -ForegroundColor Green
    exit 0
}

# ─── MODO: Primera vez (Setup completo) ──────────────────────────────────────
if ($Setup) {
    Write-Host "[Deploy] Modo Setup — primera vez en el VM" -ForegroundColor Yellow

    # Instalar git si no está
    Invoke-VM "sudo apt-get update -qq && sudo apt-get install -y -qq git python3.11 python3.11-venv python3-pip build-essential libpq-dev"

    # Crear directorio y clonar repo
    Invoke-VM "sudo mkdir -p $REMOTE_DIR && sudo chown `$USER:`$USER $REMOTE_DIR"

    # Verificar si ya existe el repo
    $repoExists = gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE --command="test -d $REMOTE_DIR/.git && echo yes || echo no" 2>$null
    if ($repoExists -eq "yes") {
        Write-Host "[Deploy] Repo ya existe, haciendo git pull..." -ForegroundColor Cyan
        Invoke-VM "cd $REMOTE_DIR && git pull origin master"
    } else {
        Write-Host "[Deploy] Clonando repositorio..." -ForegroundColor Cyan
        Invoke-VM "git clone $REPO_URL $REMOTE_DIR"
    }

    # Subir .env
    Write-Host "[Deploy] Subiendo .env..." -ForegroundColor Cyan
    $envPath = Join-Path $LOCAL_DIR ".env"
    if (Test-Path $envPath) {
        gcloud compute scp --project=$PROJECT --zone=$ZONE $envPath "${VM_NAME}:${REMOTE_DIR}/.env"
    } else {
        Write-Warning ".env no encontrado localmente. Subelo manualmente."
    }

    # Ejecutar setup completo
    Write-Host "[Deploy] Ejecutando setup_vm.sh en el VM..." -ForegroundColor Cyan
    Invoke-VM "bash $REMOTE_DIR/scripts/setup_vm.sh"

    Write-Host ""
    Write-Host "Setup completo. Inicia los servicios con:" -ForegroundColor Green
    Write-Host "  gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE"
    Write-Host "  sudo systemctl start aurum-core aurum-hunter aurum-telegram"
    exit 0
}

# ─── MODO NORMAL: git pull + reinicio ────────────────────────────────────────
Write-Host "[Deploy] Actualizando codigo en el VM via git pull..." -ForegroundColor Cyan
Invoke-VM "cd $REMOTE_DIR && git pull origin master"

# Actualizar dependencias si requirements_linux.txt cambio
Write-Host "[Deploy] Verificando dependencias Python..." -ForegroundColor Cyan
Invoke-VM "cd $REMOTE_DIR && venv/bin/pip install --quiet -r requirements_linux.txt"

# Subir .env actualizado
$envPath = Join-Path $LOCAL_DIR ".env"
if (Test-Path $envPath) {
    Write-Host "[Deploy] Subiendo .env actualizado..." -ForegroundColor Cyan
    gcloud compute scp `
        --project=$PROJECT `
        --zone=$ZONE `
        $envPath `
        "${VM_NAME}:${REMOTE_DIR}/.env"
    Invoke-VM "sudo chown aurum_bot:root $REMOTE_DIR/.env && sudo chmod 600 $REMOTE_DIR/.env"
}

# Reiniciar servicios
if (-not $NoRestart) {
    Write-Host "[Deploy] Reiniciando servicios..." -ForegroundColor Cyan
    Invoke-VM "sudo systemctl daemon-reload && sudo systemctl restart aurum-core aurum-hunter aurum-telegram"
    Start-Sleep -Seconds 3
    Invoke-VM "sudo systemctl status aurum-core aurum-hunter aurum-telegram --no-pager -l"
}

Write-Host ""
Write-Host "Deploy completado exitosamente." -ForegroundColor Green
Write-Host ""
Write-Host "Ver logs en vivo:"
Write-Host "  gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE"
Write-Host "  sudo journalctl -u aurum-core -f"
