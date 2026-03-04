"""
AURUM OMNI V1.0.0 — Motor de Ejecución Continua
Punto de entrada principal del sistema.
Ciclo: evalúa cada activo activo cada 60 segundos (1 vela M1).
"""
import time
import sys
import os
from datetime import datetime

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager
from core.scheduler import AurumScheduler
from config.notifier import notificar_inicio, notificar_error_critico, notificar_resumen_horario, notificar_error_critico

# Intervalo entre ciclos en segundos (coincide con el cierre de una vela M1)
CICLO_SEGUNDOS = 60

# NOTA: La lista de activos ya NO está hardcodeada aquí.
# El motor obtiene los activos dinámicamente desde la tabla 'activos' en GCP.


def inicializar() -> tuple[DBConnector, MT5Connector] | tuple[None, None]:
    """Intenta conectar a la BD y a MT5. Retorna (db, mt5) o (None, None) si falla."""
    db = DBConnector()
    mt5 = MT5Connector()

    if not db.conectar():
        print("[MAIN] CRITICO: No se pudo conectar a la base de datos. Abortando.")
        return None, None

    if not mt5.conectar():
        print("[MAIN] CRITICO: No se pudo conectar a MT5. Abortando.")
        db.desconectar()
        return None, None

    return db, mt5


def main():
    print("=" * 60)
    print("  AURUM OMNI V1.0.0 — INICIANDO")
    print("=" * 60)

    db, mt5_conn = inicializar()
    if not db:
        sys.exit(1)

    # --- 1. KILL-SWITCH & PID LOGGING ---
    pid = os.getpid()
    
    # --- 2. VALIDACION HARDCODEADA DE CUENTA MT5 ---
    cuenta_esperada = os.environ.get("MT5_LOGIN", "")
    import MetaTrader5 as mt_api
    info_cuenta = mt_api.account_info()
    
    if not info_cuenta:
        print("[MAIN] CRITICO: No se pudo obtener la informacion de la cuenta MT5.")
        sys.exit(1)
        
    cuenta_real = str(info_cuenta.login)
    print(f"\n[MAIN] SISTEMA INICIADO - PID: {pid} - CUENTA MT5: {cuenta_real}")
    
    if cuenta_real != cuenta_esperada:
        print(f"[MAIN] 🚨 FATAL: Cuenta MT5 incorrecta! Esperada: {cuenta_esperada}, Real: {cuenta_real}")
        print("[MAIN] Auto-destruccion de seguridad activada (Kill-Switch).")
        notificar_error_critico("SEGURIDAD", f"Intento de operacion en cuenta equivocada ({cuenta_real}). Bot abortado.")
        sys.exit(1)

    gerente = Manager(db, mt5_conn)
    programador = AurumScheduler(gerente)
    programador.start()

    db.update_estado_bot("OPERANDO", "Aurum Omni V1.0 iniciado. Cargando activos desde BD...")
    print(f"[MAIN] Heartbeat inicial enviado a estado_bot.")
    print(f"[MAIN] Ciclo: cada {CICLO_SEGUNDOS}s | Activos: cargados dinamicamente desde BD\n")

    # --- Mensaje de inicio a Telegram ---
    activos_inicio  = db.obtener_activos_patrullaje()
    simbolos_inicio = [a['simbolo'] for a in activos_inicio]
    notificar_inicio(simbolos_inicio)

    # Contadores para el pulso horario (cada 60 ciclos ~ 1 hora)
    CICLOS_POR_HORA = 60
    ciclos_hora     = 0
    ordenes_hora    = 0

    ciclo = 0
    try:
        while True:
            ciclo += 1
            hora = time.strftime('%H:%M:%S')
            print(f"\n{'-'*60}")
            print(f"  CICLO #{ciclo}  |  {hora}")
            print(f"{'-'*60}")

            # Obtener activos dinámicamente desde la BD (no hardcodeados)
            activos_db = db.obtener_activos_patrullaje()
            simbolos   = [a['simbolo'] for a in activos_db]

            # Heartbeat en cada ciclo
            db.update_estado_bot(
                "OPERANDO",
                f"Ciclo #{ciclo} en curso. Monitoreando: {', '.join(simbolos)}."
            )

            # --- NUEVO: Gestión de Riesgo y Auditoría de Cierre ---
            gerente.gestionar_posiciones_abiertas() # Breakeven
            gerente.auditar_precision_cierres()     # Log de Precisión

            # --- NUEVA LOGICA DE CORTACORRIENTE (KILL-SWITCH) ---
            import MetaTrader5 as mt5_api
            info_acc = mt5_api.account_info()
            if info_acc and info_acc.equity < 2850.0:
                msg_kill = "🚨 MAX DRAWDOWN ALCANZADO ($2,850). SISTEMA HIBERNANDO HASTA MAÑANA."
                print(f"\n[MAIN] {msg_kill}")
                db.update_estado_bot("PAUSADO_POR_RIESGO", msg_kill)
                notificar_error_critico("KILL-SWITCH", msg_kill)
                mt5_conn.cerrar_todas_las_posiciones()
                break # Detener el bot

            # --- GESTIÓN DE POSICIONES ABIERTAS (BREAKEVEN) ---
            gerente.gestionar_posiciones_abiertas()

            # Evaluar cada activo con su id real de BD
            for activo in activos_db:
                print(f"\n[{hora}] Analizando {activo['simbolo']} ({activo['nombre']})...")
                try:
                    resultado = gerente.evaluar(
                        activo['simbolo'],
                        modo_simulacion=False,
                        id_activo=activo['id']   # PRODUCCION DEMO
                    )
                    # Contar órdenes realmente disparadas
                    if resultado.get("decision") not in ("IGNORADO", "CANCELADO_RIESGO"):
                        ordenes_hora += 1
                except Exception as e:
                    print(f"[MAIN] ERROR evaluando {activo['simbolo']}: {e}")
                    db.registrar_log("ERROR", "MAIN",
                                     f"Excepcion en ciclo de {activo['simbolo']}: {e}")

            ciclos_hora    += 1
            uptime_minutos  = (ciclo * CICLO_SEGUNDOS) // 60

            # --- Pulso horario: cada 60 ciclos (~1h) ---
            if ciclo % CICLOS_POR_HORA == 0:
                notificar_resumen_horario(
                    ciclo          = ciclo,
                    activos        = simbolos,
                    ciclos_hora    = ciclos_hora,
                    ordenes_hora   = ordenes_hora,
                    uptime_minutos = uptime_minutos
                )
                ciclos_hora  = 0
                ordenes_hora = 0

            # Reconexión automática a MT5 si se desconecta
            import MetaTrader5 as mt5_lib
            if not mt5_lib.terminal_info():
                print("[MAIN] MT5 desconectado. Intentando reconectar...")
                db.update_estado_bot("ERROR", "MT5 desconectado. Reconectando...")
                if mt5_conn.conectar():
                    print("[MAIN] MT5 reconectado exitosamente.")
                    db.update_estado_bot("OPERANDO", "MT5 reconectado. Reanudando ciclos.")
                else:
                    print("[MAIN] FALLO reconexion MT5. Reintentando en el proximo ciclo.")

            print(f"\n[MAIN] Proximo ciclo en {CICLO_SEGUNDOS}s...")
            time.sleep(CICLO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\n\n--- Apagando Aurum de forma segura (Ctrl+C) ---")
        db.update_estado_bot("APAGADO", "Cierre manual por el usuario.")
        programador.stop_event.set()
        mt5_conn.desconectar()
        db.desconectar()
        print("[MAIN] Sistema apagado. Hasta la proxima.")
        sys.exit(0)


if __name__ == "__main__":
    main()
