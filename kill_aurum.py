import os
import psutil
import time
import sys
import io

# Forzar UTF-8 para evitar errores de charmap en Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def kill_aurum_processes():
    print("[SAFE-EXIT] Buscando procesos zombis de Aurum...")
    current_pid = os.getpid()
    count = 0
    
    # Scripts que queremos detener
    aurum_scripts = ["main.py", "manager.py", "telegram_bot.py", "heartbeat.py", "scheduler.py"]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            info = proc.info
            cmdline = info.get('cmdline')
            if not cmdline: continue
            
            cmd_str = " ".join(cmdline).lower()
            # Verificar si es un proceso python ejecutando Aurum
            if "python" in info['name'].lower():
                if any(script in cmd_str for script in aurum_scripts):
                    if info['pid'] != current_pid:
                        print(f"[*] Deteniendo PID {info['pid']}: {cmd_str}")
                        try:
                            proc.terminate()
                            # Esperar un poco y forzar si no muere
                            try:
                                proc.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                proc.kill()
                            count += 1
                        except Exception as e:
                            print(f"[!] No se pudo matar {info['pid']}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if count > 0:
        print(f"OK: Se han detenido {count} procesos de Aurum.")
    else:
        print("INFO: No se encontraron procesos activos para detener.")

if __name__ == "__main__":
    kill_aurum_processes()
    time.sleep(1)
