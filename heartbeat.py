import time
import sys
import os
import psutil
from datetime import datetime, timezone
from pathlib import Path

# Configurar path para importar db_connector
sys.path.append(str(Path(__file__).parent.absolute()))
from config.db_connector import DBConnector
from config.notifier import _enviar_telegram

VERIFICAR_CADA_SEGUNDOS = 120  # 2 minutos
MAX_TIEMPO_INACTIVO_SEGUNDOS = 600  # 10 minutos

import subprocess

def get_aurum_processes():
    """Busca procesos de python que estén ejecutando main.py, manager.py o news_hunter.py."""
    encontrados = {"core": [], "hunter": []}
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and "python" in proc.info.get('name', '').lower():
                cmd_str = " ".join(cmdline).lower()
                if "main.py" in cmd_str or "manager.py" in cmd_str:
                    encontrados["core"].append(proc)
                elif "news_hunter.py" in cmd_str:
                    encontrados["hunter"].append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
    return encontrados

def cleanup_ghost_processes():
    """Busca y termina procesos huérfanos o duplicados del proyecto."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    current_pid = os.getpid()
    
    # Primero identificamos qué debería estar corriendo
    procesos = get_aurum_processes()
    
    # Regla: Solo puede haber UN main/manager y UN news_hunter
    if len(procesos["core"]) > 1:
        print(f"[CLEANUP] Detectados {len(procesos['core'])} procesos Core. Limpiando excedentes...")
        for p in procesos["core"][1:]: # Mantenemos el más antiguo o el primero
            try: p.terminate()
            except: pass

    if len(procesos["hunter"]) > 1:
        print(f"[CLEANUP] {len(procesos['hunter'])} procesos Hunter detectados. Limpiando...")
        for p in procesos["hunter"][1:]:
            try: p.terminate()
            except: pass

def check_heartbeat():
    print("=" * 60)
    print("🛡️ AURUM SHIELD - MONITOR AUTÓNOMO V2.5")
    print(f"Watchdog activo 24/7 | Cwd: {os.getcwd()}")
    print("=" * 60)

    db = DBConnector()
    db.conectar()
    
    alerta_core_enviada = False
    alerta_hunter_enviada = False

    while True:
        try:
            # 0. Limpieza Preventiva de Fantasmas
            cleanup_ghost_processes()
            
            # 1. Verificar Procesos
            procesos = get_aurum_processes()
            core_vivo = len(procesos["core"]) > 0
            hunter_vivo = len(procesos["hunter"]) > 0

            # 2. Verificar Logs Core (Estado Vital)
            log_vivo = False
            tiempo_inactivo = 999
            try:
                if not db.conn or db.conn.closed:
                    db.conectar()
                    
                if db.conn and not db.conn.closed:
                    db.cursor.execute("SELECT tiempo, estado_general FROM estado_bot WHERE id = 1;")
                    fila = db.cursor.fetchone()
                    if fila:
                        ultimo_tiempo = fila[0]
                        ahora = datetime.now(timezone.utc)
                        tiempo_inactivo = (ahora - ultimo_tiempo).total_seconds()
                        if tiempo_inactivo < MAX_TIEMPO_INACTIVO_SEGUNDOS:
                            log_vivo = True
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR DB: {e}")
                if core_vivo: log_vivo = True 

            print(f"[{datetime.now().strftime('%H:%M:%S')}] SHIELD: Core={'OK' if core_vivo and log_vivo else 'FAIL'} | Hunter={'OK' if hunter_vivo else 'FAIL'} | DB Latido={tiempo_inactivo:.0f}s")

            # 3. Reparación Core (Si el proceso existe pero no hay latido, lo reiniciamos)
            if core_vivo and not log_vivo:
                print("[!] Motor Core congelado. Reiniciando proceso...")
                for p in procesos["core"]:
                    try: p.kill()
                    except: pass
                core_vivo = False # Forzar reinicio en el siguiente bloque

            if not core_vivo:
                print("[!] Motor Core caido. Intentando reinicio silencioso...")
                try:
                    python_exe = sys.executable
                    main_path = os.path.join(os.path.dirname(__file__), "main.py")
                    # Usamos 0x08000000 (CREATE_NO_WINDOW) para que sea silencioso en Windows
                    flags = 0x08000000 if os.name == 'nt' else 0
                    subprocess.Popen([python_exe, main_path], creationflags=flags)
                    if not alerta_core_enviada:
                        _enviar_telegram("⚠️ <b>Maikol, el motor principal ha sido reiniciado silenciosamente por el SHIELD.</b>")
                        alerta_core_enviada = True
                except Exception as e:
                    print(f"Error reiniciando Core: {e}")

            # 4. Reparación News Hunter
            if not hunter_vivo:
                print("[!] News Hunter caido. Reiniciando silenciosamente...")
                try:
                    python_exe = sys.executable
                    script_path = os.path.join(os.path.dirname(__file__), "news_hunter.py")
                    # 0x08000000 (CREATE_NO_WINDOW)
                    flags = 0x08000000 if os.name == 'nt' else 0
                    subprocess.Popen([python_exe, script_path], creationflags=flags)
                    if not alerta_hunter_enviada:
                        _enviar_telegram("📡 <b>News Hunter recuperado silenciosamente.</b>")
                        alerta_hunter_enviada = True
                except Exception as e:
                    print(f"Error reiniciando Hunter: {e}")
            else:
                alerta_hunter_enviada = False

        except Exception as e:
            print(f"[SHIELD ERROR] {e}")
            
        time.sleep(VERIFICAR_CADA_SEGUNDOS)

if __name__ == "__main__":
    check_heartbeat()
