@echo off
echo [PRISM] Iniciando Backend FastAPI...
start /B python dashboard\backend\main.py
echo [PRISM] Backend en ejecucion (puerto 8000).
echo [PRISM] Iniciando Frontend Vite...
cd dashboard\frontend
npm run dev -- --host
