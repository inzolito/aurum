import time
import sys
import os
import psutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Configurar path para importar db_connector
sys.path.append(str(Path(__file__).parent.absolute()))
from config.db_connector import DBConnector
from config.notifier import _enviar_telegram

VERIFICAR_CADA_SEGUNDOS = 120  # 2 minutos
MAX_TIEMPO_INACTIVO_SEGUNDOS = 600  # 10 minutos

# PID file del motor Core — compartido con main.py
_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aurum_core.pid")

# Ciclos de espera tras reiniciar el Core antes de volver a evaluar su salud
# Evita el loop "DB offline → matar → reiniciar → DB offline → matar..."
_COOLDOWN_CICLOS_TRAS_REINICIO = 4  # 4 × 120s = 8 minutos

def get_core_pid_from_file() -> int | None:
    """
    Lee el PID del motor Core desde aurum_core.pid.
    Retorna el PID si el proceso sigue vivo, None si el archivo no existe
    o el proceso ya terminó (PID obsoleto).
    """
    try:
        if os.path.exists(_PID_FILE):
            with open(_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                return pid
            # PID obsoleto — limpiar
            os.remove(_PID_FILE)
    except (ValueError, OSError):
        pass
    return None


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
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass

    if len(procesos["hunter"]) > 1:
        print(f"[CLEANUP] {len(procesos['hunter'])} procesos Hunter detectados. Limpiando...")
        for p in procesos["hunter"][1:]:
            try: p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass

def check_heartbeat():
    print("=" * 60)
    print("🛡️ AURUM SHIELD - MONITOR AUTÓNOMO V2.5")
    print(f"Watchdog activo 24/7 | Cwd: {os.getcwd()}")
    print("=" * 60)

    db = DBConnector()
    db.conectar()
    
    alerta_core_enviada = False
    alerta_hunter_enviada = False
    cooldown_reinicio = 0  # Ciclos de espera tras reiniciar el Core

    while True:
        try:
            # 0. Limpieza Preventiva de Fantasmas
            cleanup_ghost_processes()

            # 1. Verificar Procesos
            procesos = get_aurum_processes()
            # Usar PID file como fuente de verdad primaria para el Core
            core_pid = get_core_pid_from_file()
            core_vivo = core_pid is not None
            hunter_vivo = len(procesos["hunter"]) > 0

            # 2. Verificar Logs Core (Estado Vital) — solo si no estamos en cooldown
            log_vivo = False
            tiempo_inactivo = 999

            if cooldown_reinicio > 0:
                # En periodo de gracia tras reinicio: no evaluar latido aún
                log_vivo = True
                cooldown_reinicio -= 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SHIELD: Cooldown post-reinicio ({cooldown_reinicio} ciclos restantes). Core={'ARRANCANDO' if core_vivo else 'PENDIENTE'} | Hunter={'OK' if hunter_vivo else 'FAIL'}")
            else:
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
                    if core_vivo:
                        log_vivo = True  # Si la DB falla, no matar el proceso

                print(f"[{datetime.now().strftime('%H:%M:%S')}] SHIELD: Core={'OK' if core_vivo and log_vivo else 'FAIL'} | Hunter={'OK' if hunter_vivo else 'FAIL'} | DB Latido={tiempo_inactivo:.0f}s")

            if cooldown_reinicio == 0:
                # 3. Reparación Core
                if core_vivo and not log_vivo:
                    print("[!] Motor Core congelado (proceso vivo pero sin latido). Reiniciando...")
                    for p in procesos["core"]:
                        try: p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                    _borrar_pid_shield()
                    core_vivo = False

                if not core_vivo:
                    print("[!] Motor Core caido. Intentando reinicio silencioso...")
                    try:
                        python_exe = sys.executable
                        main_path = os.path.join(os.path.dirname(__file__), "main.py")
                        flags = 0x08000000 if os.name == 'nt' else 0
                        subprocess.Popen([python_exe, main_path], creationflags=flags)
                        cooldown_reinicio = _COOLDOWN_CICLOS_TRAS_REINICIO
                        alerta_core_enviada_flag = not alerta_core_enviada
                        if not alerta_core_enviada:
                            _enviar_telegram("⚠️ <b>Maikol, el motor principal ha sido reiniciado silenciosamente por el SHIELD.</b>")
                            alerta_core_enviada = True
                    except Exception as e:
                        print(f"Error reiniciando Core: {e}")
                else:
                    alerta_core_enviada = False

            # 4. Reparación News Hunter
            if not hunter_vivo:
                print("[!] News Hunter caido. Reiniciando silenciosamente...")
                try:
                    python_exe = sys.executable
                    script_path = os.path.join(os.path.dirname(__file__), "news_hunter.py")
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


def _borrar_pid_shield():
    """Elimina el PID file del Core cuando el SHIELD fuerza un reinicio."""
    try:
        if os.path.exists(_PID_FILE):
            os.remove(_PID_FILE)
    except OSError:
        pass

if __name__ == "__main__":
    check_heartbeat()
