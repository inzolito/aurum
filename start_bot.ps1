<#
.SYNOPSIS
    Script de Inicio Seguro para Aurum Omni.
.DESCRIPTION
    Verifica que no haya instancias previas mediante PID file antes de lanzar.
    Usa SIEMPRE el Python del entorno virtual para coherencia con el Named Mutex.
    Crea el directorio logs/ si no existe.
#>

$ErrorActionPreference = "SilentlyContinue"
$ProjectDir  = "C:\www\Aurum"
$VenvPython  = "$ProjectDir\venv\Scripts\pythonw.exe"
$MainScript  = "$ProjectDir\main.py"
$PidFile     = "$ProjectDir\aurum_core.pid"
$LogDir      = "$ProjectDir\logs"
$LogFile     = "$LogDir\bot.log"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "    AURUM OMNI - INICIO SEGURO V2"        -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Verificar que el venv existe
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] No se encontro el entorno virtual en $VenvPython" -ForegroundColor Red
    Write-Host "        Ejecuta: python -m venv venv && venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# Crear directorio de logs si no existe
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "[INFO] Directorio logs/ creado." -ForegroundColor DarkGray
}

# Verificar PID file — si existe y el proceso sigue vivo, no lanzar
if (Test-Path $PidFile) {
    $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $runningProc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($runningProc) {
            Write-Host "[AVISO] Aurum Core ya esta corriendo (PID $existingPid). No se lanzara una segunda instancia." -ForegroundColor Yellow
            Write-Host "        Si el bot esta bloqueado, usa: Stop-Process -Id $existingPid -Force" -ForegroundColor DarkGray
            exit 0
        } else {
            Write-Host "[INFO] PID file obsoleto encontrado. Limpiando..." -ForegroundColor DarkGray
            Remove-Item $PidFile -Force
        }
    }
}

# Matar procesos duplicados por nombre de script como medida adicional
$processList = Get-WmiObject Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
               Where-Object { $_.CommandLine -match "main\.py" }

if ($processList) {
    Write-Host "[KILL-SWITCH] Encontradas $($processList.Count) instancia(s) previas. Terminando..." -ForegroundColor Yellow
    foreach ($proc in $processList) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "             Terminado PID $($proc.ProcessId)" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
}

# Lanzar con el Python del venv (silencioso, log a archivo)
Write-Host "[INIT] Lanzando main.py con venv Python..." -ForegroundColor Green
$proc = Start-Process -FilePath $VenvPython -ArgumentList "-u `"$MainScript`"" -WorkingDirectory $ProjectDir -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError "$LogDir\bot_err.log" -PassThru

Write-Host "[INIT] Lanzando heartbeat.py (SHIELD) con venv Python..." -ForegroundColor Green
$ShieldScript = "$ProjectDir\heartbeat.py"
$procShield = Start-Process -FilePath $VenvPython -ArgumentList "-u `"$ShieldScript`"" -WorkingDirectory $ProjectDir -WindowStyle Hidden -RedirectStandardOutput "$LogDir\shield_stdout.log" -RedirectStandardError "$LogDir\shield_err.log" -PassThru

Write-Host "[OK] Bot iniciado -- PID $($proc.Id) | SHIELD -- PID $($procShield.Id)" -ForegroundColor Green
Write-Host "     Logs en: $LogFile" -ForegroundColor DarkGray
