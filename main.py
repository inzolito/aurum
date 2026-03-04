"""
AURUM OMNI V1.0.0 — Motor de Ejecución Continua
Punto de entrada principal del sistema.
Ciclo: evalúa cada activo activo cada 60 segundos (1 vela M1).
"""
import time
import sys

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager

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

    db, mt5 = inicializar()
    if not db:
        sys.exit(1)

    gerente = Manager(db, mt5)

    db.update_estado_bot("OPERANDO", "Sistema iniciado. Monitoreando Oro y Euro.")
    print(f"[MAIN] Heartbeat inicial enviado a estado_bot.")
    print(f"[MAIN] Activos: {ACTIVOS} | Ciclo: cada {CICLO_SEGUNDOS}s\n")

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
            simbolos = [a['simbolo'] for a in activos_db]

            # Heartbeat en cada ciclo
            db.update_estado_bot(
                "OPERANDO",
                f"Ciclo #{ciclo} en curso. Monitoreando: {', '.join(simbolos)}."
            )

            # Evaluar cada activo con su id real de BD
            for activo in activos_db:
                print(f"\n[{hora}] Analizando {activo['simbolo']} ({activo['nombre']})...")
                try:
                    gerente.evaluar(activo['simbolo'], modo_simulacion=False,
                                   id_activo=activo['id'])  # PRODUCCION DEMO
                except Exception as e:
                    print(f"[MAIN] ERROR evaluando {activo['simbolo']}: {e}")
                    db.registrar_log("ERROR", "MAIN",
                                    f"Excepcion en ciclo de {activo['simbolo']}: {e}")

            # Reconexión automática a MT5 si se desconecta
            import MetaTrader5 as mt5_lib
            if not mt5_lib.terminal_info():
                print("[MAIN] MT5 desconectado. Intentando reconectar...")
                db.update_estado_bot("ERROR", "MT5 desconectado. Reconectando...")
                if mt5.conectar():
                    print("[MAIN] MT5 reconectado exitosamente.")
                    db.update_estado_bot("OPERANDO", "MT5 reconectado. Reanudando ciclos.")
                else:
                    print("[MAIN] FALLO reconexion MT5. Reintentando en el proximo ciclo.")

            print(f"\n[MAIN] Proximo ciclo en {CICLO_SEGUNDOS}s...")
            time.sleep(CICLO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\n\n--- Apagando Aurum de forma segura (Ctrl+C) ---")
        db.update_estado_bot("APAGADO", "Cierre manual por el usuario.")
        mt5.desconectar()
        db.desconectar()
        print("[MAIN] Sistema apagado. Hasta la proxima.")
        sys.exit(0)


if __name__ == "__main__":
    main()
