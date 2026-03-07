import sys
import os
from pathlib import Path

# Asegurar que los módulos del proyecto sean importables
sys.path.append(os.getcwd())

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager

def force_full_analysis():
    db = DBConnector()
    mt5 = MT5Connector()
    
    if not db.conectar() or not mt5.conectar():
        print("Error en las conexiones iniciales.")
        return
    
    try:
        gerente = Manager(db, mt5)
        activos = db.obtener_activos_patrullaje()
        
        print(f"\n{'='*60}")
        print(f"  FORZANDO CICLO DE ANALISIS - {len(activos)} ACTIVOS")
        print(f"{'='*60}")
        
        for activo in activos:
            simbolo = activo['simbolo']
            print(f"\n>>> Analizando {simbolo}...")
            # Usamos modo_simulacion=True para generar el reporte sin abrir posiciones reales en este test
            resultado = gerente.evaluar(simbolo, modo_simulacion=True, id_activo=activo['id'])
            
            decision = resultado.get("decision")
            veredicto = resultado.get("veredicto", 0.0)
            motivo = resultado.get("motivo", "N/A")
            
            print(f"    Veredicto: {veredicto:+.4f}")
            print(f"    Decision:  {decision}")
            print(f"    Motivo:    {motivo}")
            
        print(f"\n{'='*60}")
        print("  CICLO COMPLETADO")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"Error durante el ciclo forzado: {e}")
    finally:
        mt5.desconectar()
        db.desconectar()

if __name__ == "__main__":
    force_full_analysis()
