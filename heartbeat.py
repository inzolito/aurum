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
from config.logging_config import setup_logging, get_logger

setup_logging("INFO")
logger = get_logger("heartbeat")

VERIFICAR_CADA_SEGUNDOS = 120  # 2 minutos
MAX_TIEMPO_INACTIVO_SEGUNDOS = 600  # 10 minutos

# Lock file del motor Core (fcntl.flock) — reemplaza el viejo PID file
_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aurum_core.lock")

# Ciclos de espera tras reiniciar el Core antes de volver a evaluar su salud
# Evita el loop "DB offline → matar → reiniciar → DB offline → matar..."
_COOLDOWN_CICLOS_TRAS_REINICIO = 4  # 4 × 120s = 8 minutos


def _get_venv_python() -> str:
    """
    Retorna la ruta al intérprete Python del venv.
    Prioridad: pythonw.exe (sin consola) → python.exe → sys.executable.
    """
    _base = os.path.dirname(os.path.abspath(__file__))
    for nombre in ("pythonw.exe", "python.exe"):
        candidato = os.path.join(_base, "venv", "Scripts", nombre)
        if os.path.exists(candidato):
            return candidato
    return sys.executable

def _core_tiene_lock() -> bool:
    """
    Intenta adquirir el lock exclusivo de aurum_core.lock de forma no-bloqueante.
    - Retorna True  → lock OCUPADO → core está corriendo.
    - Retorna False → lock LIBRE   → core no está corriendo.
    Usa el mismo mecanismo fcntl.flock que main.py.
    """
    if os.name == 'nt':
        # Windows: comprobar por psutil (Named Mutex no es fácil de verificar desde fuera)
        return False  # fallback: depender solo de psutil en Windows
    import fcntl
    fh = None
    try:
        fh = open(_LOCK_FILE, 'a')
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Pudimos adquirir → nadie tiene el lock → core muerto
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False
    except OSError:
        return True  # Lock tomado → core vivo
    finally:
        if fh:
            try: fh.close()
            except OSError: pass


def get_aurum_processes():
    """
    Busca procesos Python ejecutando main.py, news_hunter.py o telegram_daemon.py.

    En Windows, venv/Scripts/pythonw.exe actúa como launcher y lanza el intérprete
    del sistema Python como proceso hijo corriendo el mismo script. Ese par
    launcher+worker cuenta como UNA sola instancia.

    Solo devuelve el proceso raíz de cada cadena (el que no tiene padre Aurum
    corriendo el mismo script). Así evitamos contar pares launcher+worker como
    duplicados.
    """
    encontrados = {"core": [], "hunter": [], "daemon": []}

    # Primer paso: recolectar todos los procesos Python de Aurum con su PPID
    all_aurum = {}  # pid -> (key, proc)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid']):
        try:
            cmdline = proc.info.get('cmdline')
            if not cmdline or "python" not in proc.info.get('name', '').lower():
                continue
            cmd_str = " ".join(cmdline).lower()
            key = None
            if "main.py" in cmd_str or "manager.py" in cmd_str:
                key = "core"
            elif "news_hunter.py" in cmd_str:
                key = "hunter"
            elif "telegram_daemon.py" in cmd_str:
                key = "daemon"
            if key:
                all_aurum[proc.info['pid']] = (key, proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Segundo paso: solo contar procesos raíz (sin padre Aurum para el mismo script)
    for pid, (key, proc) in all_aurum.items():
        try:
            ppid = proc.info.get('ppid', 0)
            parent_entry = all_aurum.get(ppid)
            # Si el padre no es un proceso Aurum del mismo tipo → es raíz (launcher o standalone)
            if parent_entry is None or parent_entry[0] != key:
                encontrados[key].append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return encontrados


def cleanup_ghost_processes():
    """Busca y termina cadenas duplicadas (verdaderos duplicados, no pares launcher+worker)."""
    procesos = get_aurum_processes()

    for nombre, lista in procesos.items():
        if len(lista) <= 1:
            continue
        print(f"[CLEANUP] {len(lista)} cadenas '{nombre}' detectadas. Eliminando excedentes...")
        # Conservar la primera cadena, terminar el árbol de las demás
        for p in lista[1:]:
            try:
                # Matar árbol completo del duplicado (launcher + worker hijo)
                children = p.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                p.kill()
                print(f"[CLEANUP] Cadena duplicada terminada (raíz PID {p.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

def check_heartbeat():
    print("=" * 60)
    print("AURUM SHIELD - MONITOR AUTONOMO V2.5")
    print(f"Watchdog activo 24/7 | Cwd: {os.getcwd()}")
    print("=" * 60)

    db = DBConnector()
    db.conectar()
    
    alerta_core_enviada   = False
    alerta_hunter_enviada = False
    alerta_daemon_enviada = False
    alerta_db_enviada     = False
    cooldown_reinicio = 0  # Ciclos de espera tras reiniciar el Core

    while True:
        try:
            # 0. Limpieza Preventiva de Fantasmas
            cleanup_ghost_processes()

            # 1. Verificar Procesos
            procesos = get_aurum_processes()
            # Fuente de verdad: psutil (proceso existe) OR flock ocupado (fcntl.flock)
            # Ambas deben coincidir en "muerto" antes de intentar reinicio.
            core_vivo   = len(procesos["core"]) > 0 or _core_tiene_lock()
            hunter_vivo = len(procesos["hunter"]) > 0
            daemon_vivo = len(procesos["daemon"]) > 0

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

                    db_ok = False
                    if db.conn and not db.conn.closed:
                        db.cursor.execute("SELECT tiempo, estado_general FROM estado_bot WHERE id = 1;")
                        fila = db.cursor.fetchone()
                        if fila:
                            ultimo_tiempo = fila[0]
                            ahora = datetime.now(timezone.utc)
                            tiempo_inactivo = (ahora - ultimo_tiempo).total_seconds()
                            if tiempo_inactivo < MAX_TIEMPO_INACTIVO_SEGUNDOS:
                                log_vivo = True
                        db_ok = True
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR DB: {e}")
                    if core_vivo:
                        log_vivo = True  # Si la DB falla, no matar el proceso
                    if not alerta_db_enviada:
                        _enviar_telegram(f"🔴 <b>SHIELD: Base de datos inaccesible.</b>\nEl motor sigue en Survival Mode — señales NLP desactualizadas.\nError: <code>{e}</code>")
                        alerta_db_enviada = True

                if db_ok and alerta_db_enviada:
                    _enviar_telegram("✅ <b>SHIELD: Base de datos recuperada.</b>")
                    alerta_db_enviada = False
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SHIELD: Core={'OK' if core_vivo and log_vivo else 'FAIL'} | Hunter={'OK' if hunter_vivo else 'FAIL'} | Daemon={'OK' if daemon_vivo else 'FAIL'} | DB Latido={tiempo_inactivo:.0f}s")

            if cooldown_reinicio == 0:
                # 3. Reparación Core
                if core_vivo and not log_vivo:
                    print("[!] Motor Core congelado (proceso vivo pero sin latido). Reiniciando...")
                    for p in procesos["core"]:
                        try: p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                    _borrar_pid_shield()
                    core_vivo = False

                if not core_vivo and not _core_tiene_lock():
                    # Doble verificación: ni psutil lo ve ni el lock está ocupado
                    print("[!] Motor Core caido. Intentando reinicio silencioso...")
                    try:
                        _base = os.path.dirname(os.path.abspath(__file__))
                        python_exe = _get_venv_python()
                        main_path = os.path.join(_base, "main.py")
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
                    _base = os.path.dirname(os.path.abspath(__file__))
                    python_exe = _get_venv_python()
                    script_path = os.path.join(_base, "news_hunter.py")
                    flags = 0x08000000 if os.name == 'nt' else 0
                    subprocess.Popen([python_exe, script_path], creationflags=flags)
                    if not alerta_hunter_enviada:
                        _enviar_telegram("📡 <b>News Hunter recuperado silenciosamente.</b>")
                        alerta_hunter_enviada = True
                except Exception as e:
                    print(f"Error reiniciando Hunter: {e}")
            else:
                alerta_hunter_enviada = False

            # 5. Reparación Telegram Daemon
            if not daemon_vivo:
                print("[!] Telegram Daemon caido. Reiniciando silenciosamente...")
                try:
                    _base = os.path.dirname(os.path.abspath(__file__))
                    python_exe = _get_venv_python()
                    script_path = os.path.join(_base, "telegram_daemon.py")
                    flags = 0x08000000 if os.name == 'nt' else 0
                    subprocess.Popen([python_exe, script_path], creationflags=flags)
                    if not alerta_daemon_enviada:
                        _enviar_telegram("📱 <b>Daemon Telegram recuperado silenciosamente.</b>")
                        alerta_daemon_enviada = True
                except Exception as e:
                    print(f"Error reiniciando Telegram Daemon: {e}")
            else:
                alerta_daemon_enviada = False

        except Exception as e:
            print(f"[SHIELD ERROR] {e}")

        time.sleep(VERIFICAR_CADA_SEGUNDOS)


def _borrar_pid_shield():
    """Ya no hay PID file — el lock (fcntl.flock) se libera automáticamente al morir el proceso."""
    pass

if __name__ == "__main__":
    check_heartbeat()
