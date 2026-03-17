"""
Deploy y arranque del Dashboard Aurum Prism en el servidor.
Correr desde /opt/aurum: python start_dashboard.py
"""
import os
import sys
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(BASE, "dashboard", "frontend")
BACKEND  = os.path.join(BASE, "dashboard", "backend")
DIST     = os.path.join(FRONTEND, "dist")

print("=== Aurum Prism — Deploy ===")

# 1. Instalar dependencias Python del backend
print("\n[1/3] Instalando dependencias Python...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "fastapi", "uvicorn", "python-jose[cryptography]",
    "passlib[bcrypt]", "python-dotenv"
], check=True)
print("      OK")

# 2. Compilar frontend
print("\n[2/3] Compilando frontend React...")
if not os.path.exists(os.path.join(FRONTEND, "node_modules")):
    print("      Instalando node_modules...")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)
print(f"      OK — dist generado en {DIST}")

# 3. Arrancar backend
print("\n[3/3] Arrancando backend en puerto 8000...")
print("      Acceder en: http://<IP-DEL-SERVIDOR>:8000")
print("      Usuario: msalasm  |  Contraseña: Singluten2!")
print("      (Ctrl+C para detener)\n")

os.chdir(BASE)
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "dashboard.backend.main:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--reload"
])
