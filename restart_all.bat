@echo off
echo Reiniciando todos los procesos de Aurum...
taskkill /F /IM pythonw.exe
timeout /t 2 /nobreak > nul
powershell.exe -ExecutionPolicy Bypass -File start_bot.ps1
exit
