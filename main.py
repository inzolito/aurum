"""
AURUM OMNI V1.0.0 — Motor de Ejecución Continua
Punto de entrada principal del sistema.
Ciclo: evalúa cada activo activo cada 60 segundos (1 vela M1).
"""
import time
import sys
import os
import subprocess
import psutil
from datetime import datetime

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager
from core.scheduler import AurumScheduler
from config.notifier import notificar_inicio, notificar_error_critico, notificar_resumen_horario
from config.logging_config import setup_logging, get_logger
import MetaTrader5 as mt5_api

setup_logging("INFO")
logger = get_logger("main")

# Intervalo entre ciclos en segundos (coincide con el cierre de una vela M1)
CICLO_SEGUNDOS = 60

# Archivo PID para prevenir instancias duplicadas y permitir detección fiable
_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aurum_core.pid")


def _escribir_pid():
    """Registra el PID actual en disco al iniciar."""
    try:
        with open(_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except OSError as e:
        print(f"[MAIN] Advertencia: no se pudo escribir PID file: {e}")


def _borrar_pid():
    """Elimina el PID file al apagar limpiamente."""
    try:
        if os.path.exists(_PID_FILE):
            os.remove(_PID_FILE)
    except OSError:
        pass


def _verificar_instancia_duplicada() -> bool:
    """
    Retorna True si ya hay una instancia de Aurum Core corriendo.
    Usa Named Mutex de Windows (atómico) como mecanismo principal para evitar
    race conditions, con PID file como respaldo en plataformas no-Windows.
    """
    if os.name == 'nt':
        # Named Mutex — operación atómica, sin race condition
        import ctypes
        _MUTEX_NAME = "Global\\AurumCoreMutex"
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        ERROR_ALREADY_EXISTS = 183
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        # Guardamos el handle en un módulo global para que no sea liberado por GC
        _verificar_instancia_duplicada._mutex_handle = handle
        return False
    else:
        # Fallback Unix: PID file
        if not os.path.exists(_PID_FILE):
            return False
        try:
            with open(_PID_FILE, 'r') as f:
                pid_existente = int(f.read().strip())
            if psutil.pid_exists(pid_existente) and pid_existente != os.getpid():
                return True
            os.remove(_PID_FILE)
        except (ValueError, OSError):
            pass
        return False


def _get_venv_python() -> str:
    """Retorna el intérprete Python del venv. Prioridad: pythonw.exe → python.exe → sys.executable."""
    _base = os.path.dirname(os.path.abspath(__file__))
    for nombre in ("pythonw.exe", "python.exe"):
        candidato = os.path.join(_base, "venv", "Scripts", nombre)
        if os.path.exists(candidato):
            return candidato
    return sys.executable


def _lanzar_proceso_daemon(nombre_script: str, nombre_display: str):
    """Lanza un script como proceso daemon silencioso usando el Python del venv."""
    _base = os.path.dirname(os.path.abspath(__file__))
    python_exe = _get_venv_python()
    script_path = os.path.join(_base, nombre_script)
    flags = 0x08000000 if os.name == 'nt' else 0
    try:
        subprocess.Popen([python_exe, script_path], creationflags=flags)
        print(f"[MAIN] {nombre_display} lanzado como proceso daemon (python: {python_exe}).")
    except Exception as e:
        print(f"[MAIN] Advertencia: no se pudo lanzar {nombre_display}: {e}")


def _lanzar_news_hunter():
    """Lanza news_hunter.py como proceso daemon si no está ya corriendo."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if "python" in proc.info.get('name', '').lower():
                if "news_hunter.py" in " ".join(proc.info.get('cmdline', [])).lower():
                    print("[MAIN] News Hunter ya está corriendo.")
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _lanzar_proceso_daemon("news_hunter.py", "News Hunter")


def _lanzar_telegram_daemon():
    """Lanza telegram_daemon.py como proceso independiente si no está ya corriendo."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if "python" in proc.info.get('name', '').lower():
                if "telegram_daemon.py" in " ".join(proc.info.get('cmdline', [])).lower():
                    print("[MAIN] Telegram Daemon ya está corriendo.")
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _lanzar_proceso_daemon("telegram_daemon.py", "Telegram Daemon")

# NOTA: La lista de activos ya NO está hardcodeada aquí.
# El motor obtiene los activos dinámicamente desde la tabla 'activos' en GCP.


class AurumEngine:
    def __init__(self):
        self.db = None
        self.mt5_conn = None
        self.gerente = None
        self.programador = None
        self.running = False
        self.ciclo = 0

    def inicializar(self) -> bool:
        """Intenta conectar a la BD y a MT5. Retorna True si exitosa."""
        self.db = DBConnector()
        self.mt5_conn = MT5Connector()

        if not self.db.conectar():
            print("[MAIN] ⚠️ ADVERTENCIA: No se pudo conectar a la base de datos (Cloud).")
            print("[MAIN] Activando MODO SUPERVIVENCIA (Survival Mode). El bot usará parámetros locales.")
            # No retornamos False, permitimos continuar en modo degradado
        else:
            print("[MAIN] Conexión a Base de Datos Cloud establecida.")

        if not self.mt5_conn.conectar():
            print("[MAIN] 🚨 CRITICO: No se pudo conectar a MT5. El motor no puede operar sin broker.")
            if self.db: self.db.desconectar()
            return False

        return True

    def run(self):
        print("=" * 60)
        print("  AURUM OMNI V1.0.0 — INICIANDO")
        print("=" * 60)

        if not self.db or not self.mt5_conn:
            if not self.inicializar():
                return

        # --- 0. VALIDACION V9.0 DE CACHE ---
        try:
            if self.db and self.db.conn and not self.db.conn.closed:
                self.db.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cache_nlp_impactos' AND column_name='hash_contexto';")
                if self.db.cursor.fetchone():
                    print("[MAIN] Estructura de BD verificada - OK.")
        except Exception as e:
            print(f"[MAIN] Error verificando esquema de BD: {e}")

        # --- 1. PID FILE — Prevenir instancias duplicadas ---
        if _verificar_instancia_duplicada():
            print("[MAIN] 🚨 Ya hay una instancia de Aurum Core corriendo. Abortando para evitar duplicados.")
            return

        _escribir_pid()
        pid = os.getpid()
        
        # --- 2. VALIDACION HARDCODEADA DE CUENTA MT5 ---
        cuenta_esperada = os.environ.get("MT5_LOGIN", "")
        info_cuenta = mt5_api.account_info()
        
        if not info_cuenta:
            print("[MAIN] CRITICO: No se pudo obtener la informacion de la cuenta MT5.")
            return
            
        cuenta_real = str(info_cuenta.login)
        print(f"\n[MAIN] SISTEMA INICIADO - PID: {pid} - CUENTA MT5: {cuenta_real}")
        
        if cuenta_real != cuenta_esperada:
            print(f"[MAIN] 🚨 FATAL: Cuenta MT5 incorrecta! Esperada: {cuenta_esperada}, Real: {cuenta_real}")
            print("[MAIN] Auto-destruccion de seguridad activada (Kill-Switch).")
            notificar_error_critico("SEGURIDAD", f"Intento de operacion en cuenta equivocada ({cuenta_real}). Bot abortado.")
            return

        self.gerente = Manager(self.db, self.mt5_conn)
        self.programador = AurumScheduler(self.gerente)
        self.programador.start()

        # V15.0: Los daemons independientes (Telegram + News Hunter) son gestionados
        # exclusivamente por heartbeat.py (SHIELD). Main no los lanza para evitar
        # condición de carrera con duplicados. El SHIELD los detecta y lanza en su
        # primer ciclo si no están corriendo.

        self.db.update_estado_bot("OPERANDO", "Aurum Omni V1.0 iniciado. Cargando activos desde BD...")
        print(f"[MAIN] Heartbeat inicial enviado a estado_bot.")
        print(f"[MAIN] Ciclo: cada {CICLO_SEGUNDOS}s | Activos: cargados dinamicamente desde BD\n")

        # Contadores para el pulso horario (cada 60 ciclos ~ 1 hora)
        CICLOS_POR_HORA = 60
        ciclos_hora     = 0
        ordenes_hora    = 0

        self.running = True
        try:
            while self.running:
                self.ciclo += 1
                from zoneinfo import ZoneInfo
                ahora_dt = datetime.now(tz=ZoneInfo('America/Santiago'))
                hora = ahora_dt.strftime('%H:%M:%S')

                # --- PROTOCOLO GATEKEEPER V13.0: Bypass de Fin de Semana ---
                dia = ahora_dt.weekday()
                hora_int = ahora_dt.hour
                
                es_finde = False
                if dia == 4 and hora_int >= 18:
                    es_finde = True
                elif dia == 5:
                    es_finde = True
                elif dia == 6 and hora_int < 18:
                    es_finde = True
                    
                if es_finde:
                    print(f"\n[GATEKEEPER] {ahora_dt.strftime('%A %H:%M')} -> MODO VIGILANCIA (Fin de semana).")
                    self.db.update_estado_bot("VIGILANCIA_FIN_DE_SEMANA", "Gatekeeper activo. Patrullando noticias...")
                    self.gerente.mantener_vigilancia()
                    time.sleep(600)
                    continue

                print(f"\n{'-'*60}")
                print(f"  CICLO #{self.ciclo}  |  {hora}")
                print(f"{'-'*60}")

                activos_db = self.db.obtener_activos_patrullaje()
                simbolos   = [a['simbolo'] for a in activos_db]

                self.db.update_estado_bot(
                    "OPERANDO",
                    f"Ciclo #{self.ciclo} en curso. Monitoreando: {', '.join(simbolos)}."
                )

                self.gerente.gestionar_posiciones_abiertas()
                self.gerente.auditar_precision_cierres()

                info_acc = mt5_api.account_info()
                # --- UMBRAL DE PERDIDAS — leído desde parametros_sistema en BD ---
                _params_dd = self.db.get_parametros()
                _max_dd = _params_dd.get("GERENTE.max_drawdown_usd", 1000.0)
                if info_acc and info_acc.equity < _max_dd:
                    msg_kill = f"🚨 MAX DRAWDOWN ALCANZADO (${_max_dd:,.0f}). SISTEMA HIBERNANDO HASTA MAÑANA."
                    print(f"\n[MAIN] {msg_kill}")
                    self.db.update_estado_bot("PAUSADO_POR_RIESGO", msg_kill)
                    notificar_error_critico("KILL-SWITCH", msg_kill)
                    self.mt5_conn.cerrar_todas_las_posiciones()
                    self.running = False
                    break

                for activo in activos_db:
                    print(f"\n[{hora}] Analizando {activo['simbolo']} ({activo['nombre']})...")
                    try:
                        resultado = self.gerente.evaluar(
                            activo['simbolo'],
                            modo_simulacion=False,
                            id_activo=activo['id']
                        )
                        if resultado.get("decision") not in ("IGNORADO", "CANCELADO_RIESGO"):
                            ordenes_hora += 1
                    except Exception as e:
                        print(f"[MAIN] ERROR evaluando {activo['simbolo']}: {e}")
                        self.db.registrar_log("ERROR", "MAIN",
                                         f"Excepcion en ciclo de {activo['simbolo']}: {e}")

                ciclos_hora    += 1
                if self.ciclo % CICLOS_POR_HORA == 0:
                    ciclos_hora  = 0
                    ordenes_hora = 0

                if not mt5_api.terminal_info():
                    print("[MAIN] MT5 desconectado. Intentando reconectar...")
                    self.db.update_estado_bot("ERROR", "MT5 desconectado. Reconectando...")
                    if self.mt5_conn.conectar():
                        print("[MAIN] MT5 reconectado exitosamente.")
                        self.db.update_estado_bot("OPERANDO", "MT5 reconectado. Reanudando ciclos.")
                    else:
                        print("[MAIN] FALLO reconexion MT5. Reintentando en el proximo ciclo.")

                print(f"\n[MAIN] Proximo ciclo en {CICLO_SEGUNDOS}s...")
                for _ in range(CICLO_SEGUNDOS):
                    if not self.running: break
                    time.sleep(1)

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        print("\n\n--- Apagando Aurum de forma segura ---")
        self.running = False
        _borrar_pid()
        if self.db:
            self.db.update_estado_bot("APAGADO", "Cierre manual o por sistema.")
        if self.programador:
            self.programador.stop_event.set()
        if self.mt5_conn:
            self.mt5_conn.desconectar()
        if self.db:
            self.db.desconectar()
        print("[MAIN] Sistema apagado. Hasta la proxima.")

def main():
    engine = AurumEngine()
    engine.run()

if __name__ == "__main__":
    main()
