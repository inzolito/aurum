<#
.SYNOPSIS
    Script de Inicio Seguro (Kill-Switch) para Aurum Omni.
.DESCRIPTION
    Mata cualquier instancia previa de main.py para evitar procesos dobles.
    Luego, arranca el bot principal.
#>

$ErrorActionPreference = "SilentlyContinue"

Write-Host "========================================="
Write-Host "    AURUM OMNI - INICIO SEGURO"
Write-Host "========================================="

# 1. Kill-Switch: Buscar procesos de Python ejecutando main.py
Write-Host "[KILL-SWITCH] Buscando instancias previas del bot..."

$processList = Get-WmiObject Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match "main.py" }

if ($processList) {
    foreach ($proc in $processList) {
        Write-Host "[KILL-SWITCH] Matando proceso Python PID $($proc.ProcessId)..." -ForegroundColor Yellow
        Stop-Process -Id $proc.ProcessId -Force
    }
    Start-Sleep -Seconds 2
    Write-Host "[KILL-SWITCH] Instancias previas eliminadas." -ForegroundColor Green
} else {
    Write-Host "[KILL-SWITCH] No se encontraron instancias previas corriendo." -ForegroundColor DarkGray
}

# 2. Iniciar el nuevo proceso
Write-Host "[INIT] Levantando proceso main.py en background..."
Start-Process cmd -ArgumentList "/c C:\www\Aurum\venv\Scripts\python.exe -u C:\www\Aurum\main.py > C:\www\Aurum\logs\bot.log 2>&1" -WorkingDirectory "C:\www\Aurum" -WindowStyle Hidden -PassThru | Select-Object Id

Write-Host "[OK] Bot iniciado. Revisar logs/bot.log" -ForegroundColor Green
