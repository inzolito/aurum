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
import fcntl
from datetime import datetime

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager
from core.lab_evaluator import LabEvaluator
from core.scheduler import AurumScheduler
from config.notifier import notificar_inicio, notificar_error_critico, notificar_resumen_horario
from config.logging_config import setup_logging, get_logger
import MetaTrader5 as mt5_api

setup_logging("INFO")
logger = get_logger("main")

# Intervalo entre ciclos en segundos (coincide con el cierre de una vela M1)
CICLO_SEGUNDOS = 60

# Lock file para prevenir instancias duplicadas (fcntl.flock — atómico, auto-liberado por el OS)
_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aurum_core.lock")
_lock_fh   = None  # file handle global — debe mantenerse abierto durante toda la ejecución


def _adquirir_lock() -> bool:
    """
    Intenta adquirir un lock exclusivo sobre aurum_core.lock.
    Retorna True si lo logra (única instancia), False si ya hay otra corriendo.
    El OS libera el lock automáticamente al morir el proceso (incluso con SIGKILL).
    Funciona en Linux/Mac. En Windows cae al PID file como fallback.
    """
    global _lock_fh
    if os.name == 'nt':
        # Windows: Named Mutex
        import ctypes
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\AurumCoreMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.kernel32.CloseHandle(handle)
            return False
        _adquirir_lock._mutex_handle = handle
        return True
    else:
        # Linux/Mac: fcntl.flock — atómico y auto-liberado por el OS
        try:
            _lock_fh = open(_LOCK_FILE, 'a')  # 'a' no trunca el archivo antes de adquirir el lock
            fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fh.write(str(os.getpid()))
            _lock_fh.flush()
            return True
        except OSError:
            # Otro proceso ya tiene el lock
            if _lock_fh:
                _lock_fh.close()
                _lock_fh = None
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


def _iniciar_actualizador_pnl(db, intervalo=10):
    """Hilo daemon que actualiza pnl_usd de posiciones abiertas cada `intervalo` segundos."""
    import threading
    def _loop():
        while True:
            try:
                posiciones = mt5_api.positions_get()
                if posiciones:
                    with db._lock:
                        for pos in posiciones:
                            db.cursor.execute(
                                "UPDATE registro_operaciones SET pnl_usd = %s "
                                "WHERE ticket_mt5 = %s AND resultado_final IS NULL",
                                (round(float(pos.profit), 2), int(pos.ticket))
                            )
                        db.conn.commit()
            except Exception as e:
                print(f"[PNL-UPDATER] Error: {e}")
                try:
                    db.conn.rollback()
                except Exception:
                    pass
            time.sleep(intervalo)
    t = threading.Thread(target=_loop, daemon=True, name="pnl-updater")
    t.start()
    print(f"[MAIN] PnL-Updater iniciado (intervalo {intervalo}s).")


class AurumEngine:
    def __init__(self):
        self.db = None
        self.mt5_conn = None
        self.gerente = None
        self.lab_evaluator = None
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

        # --- 1. LOCK EXCLUSIVO — Prevenir instancias duplicadas (fcntl.flock) ---
        if not _adquirir_lock():
            print("[MAIN] 🚨 Ya hay una instancia de Aurum Core corriendo. Abortando.")
            try:
                from config.notifier import _enviar_telegram
                _enviar_telegram("🚨 <b>AURUM CORE — INSTANCIA DUPLICADA DETECTADA</b>\n\nEl bot intentó arrancar pero ya hay un proceso corriendo.\nRevisa el servidor inmediatamente.")
            except Exception:
                pass
            sys.exit(1)

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
        self.lab_evaluator = LabEvaluator(self.db)
        self.programador = AurumScheduler(self.gerente)
        self.programador.start()

        # Hilo daemon: actualiza pnl_usd de posiciones abiertas cada 10s
        _iniciar_actualizador_pnl(self.db, intervalo=10)

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
                    self.db.update_estado_bot("VIGILANCIA_FINDE", "Gatekeeper activo. Patrullando noticias...")
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
                if info_acc:
                    self.db.update_estado_bot(
                        "OPERANDO",
                        f"Ciclo #{self.ciclo} en curso. Monitoreando: {', '.join(simbolos)}.",
                        balance=round(float(info_acc.balance), 2),
                        equity=round(float(info_acc.equity), 2),
                        pnl_flotante=round(float(info_acc.profit), 2),
                    )
                # KILL-SWITCH DESHABILITADO (demo — cuenta sin drawdown real)
                # _params_dd = self.db.get_parametros()
                # _max_dd = _params_dd.get("GERENTE.max_drawdown_usd", 1000.0)
                # if info_acc and info_acc.equity < _max_dd:
                #     msg_kill = f"MAX DRAWDOWN ALCANZADO (${_max_dd:,.0f}). SISTEMA HIBERNANDO HASTA MANANA."
                #     self.db.update_estado_bot("PAUSADO_POR_RIESGO", msg_kill)
                #     notificar_error_critico("KILL-SWITCH", msg_kill)
                #     self.mt5_conn.cerrar_todas_las_posiciones()
                #     self.running = False
                #     break

                # Recolector de votos para el Laboratorio (V18)
                _votos_lab   = {}  # {simbolo: {trend, nlp, sniper, hurst, volume, cross}}
                _precios_lab = {}  # {simbolo: {bid, ask}}

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
                        # Capturar votos para el lab si están disponibles en el resultado
                        if "votos" in resultado:
                            _votos_lab[activo['simbolo']] = resultado["votos"]
                        # Capturar precio actual del activo
                        try:
                            _sb = activo.get("simbolo_broker") or self.db.obtener_simbolo_broker(activo['simbolo'])
                            if _sb:
                                _tick = mt5_api.symbol_info_tick(_sb)
                                if _tick:
                                    _precios_lab[activo['simbolo']] = {
                                        "bid": float(_tick.bid),
                                        "ask": float(_tick.ask),
                                    }
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"[MAIN] ERROR evaluando {activo['simbolo']}: {e}")
                        self.db.registrar_log("ERROR", "MAIN",
                                         f"Excepcion en ciclo de {activo['simbolo']}: {e}")

                # V18: Evaluar Laboratorio al final del ciclo de producción
                try:
                    if _precios_lab:
                        self.lab_evaluator.evaluar_todos(_votos_lab, _precios_lab)
                except Exception as e_lab:
                    print(f"[LAB] Error en ciclo del laboratorio: {e_lab}")

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
