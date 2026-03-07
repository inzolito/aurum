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

VERIFICAR_CADA_SEGUNDOS = 180  # 3 minutos
MAX_TIEMPO_INACTIVO_SEGUNDOS = 300  # 5 minutos

def get_aurum_processes():
    """Busca procesos de python que esten ejecutando main.py o manager.py."""
    encontrados = []
    
    # Buscamos iterando los procesos
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and "python" in proc.info.get('name', '').lower():
                cmd_str = " ".join(cmdline).lower()
                if "main.py" in cmd_str or "manager.py" in cmd_str:
                    encontrados.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
    return encontrados

def check_heartbeat():
    print("=" * 60)
    print("🛡️ AURUM HEARTBEAT MONITOR - INICIANDO [INDEPENDIENTE]")
    print(f"Verificando cada {VERIFICAR_CADA_SEGUNDOS}s | Timeout: {MAX_TIEMPO_INACTIVO_SEGUNDOS}s")
    print("=" * 60)

    db = DBConnector()
    # Conexión inicial silenciosa
    db.conectar()
    
    alerta_enviada = False

    while True:
        try:
            # 1. Verificar Proceso (MANDATORIO E INDEPENDIENTE)
            procesos = get_aurum_processes()
            proceso_vivo = len(procesos) > 0

            # 2. Verificar Logs (estado_bot) - SECUNDARIO Y PROTEGIDO
            log_vivo = False
            tiempo_inactivo = 0
            
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
                        
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] OK: Proceso={proceso_vivo} | Estado={fila[1]} | DB Latido={tiempo_inactivo:.0f}s")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: Fallo al consultar BD ({e}). Vigilancia via OS activa.")
                db.desconectar()
                # Si falla la BD pero el proceso vive, el watchdog confía en el proceso
                if proceso_vivo:
                    log_vivo = True # Forzamos OK para no dar falso positivo por BD caída

            # 3. Decision
            if not proceso_vivo:
                if not alerta_enviada:
                    motivo = "Proceso no encontrado (main.py / manager.py) ha muerto o fue cerrado."
                    msg = f"🚨 <b>¡Maikol, Aurum se ha detenido!</b> 🚨\n\nMotivo: {motivo}\nIntentando reinicio forzado o revision urgente."
                    print(f"\n[!!!] ENVIANDO ALERTA CRITICA:\n{msg}")
                    _enviar_telegram(msg)
                    alerta_enviada = True
            else:
                if alerta_enviada:
                    msg_recovery = "✅ <b>Aurum recuperado.</b> Señal de vida del proceso detectada."
                    _enviar_telegram(msg_recovery)
                    alerta_enviada = False

        except Exception as e:
            print(f"[HEARTBEAT] Excepcion en el loop principal: {e}")
            
        time.sleep(VERIFICAR_CADA_SEGUNDOS)

if __name__ == "__main__":
    check_heartbeat()
