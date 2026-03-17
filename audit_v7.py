import sys
import os
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager

def run_audit():
    print("="*80)
    print(f"🕵️ AUDITORÍA DE SISTEMA AURUM v7.0 (SMC Sniper) - {time.strftime('%H:%M:%S')}")
    print("="*80)

    db = DBConnector()
    mt5 = MT5Connector()

    if not db.conectar() or not mt5.conectar():
        print("Error de conexión.")
        return

    gerente = Manager(db, mt5)
    activos = db.obtener_activos_patrullaje()

    for activo in activos:
        simbolo = activo['simbolo']
        print(f"\n--- ANALIZANDO: {simbolo} ---")
        start_time = time.time()
        
        try:
            # Forzamos evaluación en modo simulación para ver los logs
            res = gerente.evaluar(simbolo, modo_simulacion=True, id_activo=activo['id'])
            
            latencia = (time.time() - start_time) * 1000
            print(f"  ⏱️ Latencia: {latencia:.2f} ms")
            
        except Exception as e:
            print(f"  ❌ Error en {simbolo}: {e}")

    print("\n" + "="*80)
    print(f"AUDITORÍA FINALIZADA")
    print("="*80)
    
    mt5.desconectar()
    db.desconectar()

if __name__ == "__main__":
    run_audit()
