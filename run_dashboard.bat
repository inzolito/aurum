@echo off
title AURUM OMNI - CLOUD DASHBOARD
echo ===========================================
echo   AURUM OMNI V1.0 - PROFESSIONAL INTERFACE
echo ===========================================
echo.

:: Check for venv
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] No se detecto el entorno virtual (venv).
    echo Asegurate de estar en la carpeta c:\www\Aurum
    pause
    exit /b 1
)

:: Run script
".\venv\Scripts\python.exe" aurum_cli.py

:: Keep window open ONLY if there was a crash
if %ERRORLEVEL% neq 0 (
    echo.
    echo [SISTEMA] El dashboard se cerro con un error (Code: %ERRORLEVEL%)
    pause
)
