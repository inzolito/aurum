import time
import pandas as pd
from core.manager import Manager
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector

def auditar_todo():
    db = DBConnector()
    mt5 = MT5Connector()
    
    if not (db.conectar() and mt5.conectar()):
        print("Error de conexión inicial")
        return

    manager = Manager(db, mt5)
    activos = ["XAUUSD", "GBPUSD", "USTEC", "US500", "USDJPY"]
    
    print("\n" + "="*80)
    print(f"🕵️ AUDITORÍA DE SISTEMA AURUM v6.0 - {time.strftime('%H:%M:%S')}")
    print("="*80)
    
    start_total = time.time()
    
    for activo in activos:
        print(f"\n--- ANALIZANDO: {activo} ---")
        start_activo = time.time()
        
        # Obtenemos datos de los obreros manualmente para transparencia total
        # (Simulamos lo que haria el manager.evaluar pero con prints detallados)
        manager.db.cursor.execute("SELECT id FROM activos WHERE simbolo = %s", (activo,))
        res_id = manager.db.cursor.fetchone()
        id_activo = res_id[0] if res_id else None
        
        v_trend  = manager.trend.analizar(activo)
        v_nlp    = manager.nlp.analizar(activo, id_activo=id_activo)
        v_volume = manager.volume.analizar(activo)
        v_flow   = manager.flow.analizar(activo)
        v_cross  = manager.cross.analizar(activo)
        res_hurst = manager.hurst.analizar(activo)
        
        # Pesos V6: Trend (35%), NLP (25%), Volume (15%), Flow (10%), Cross (15%)
        # Nota: Flow es bajo por ser L2, Cross es medio por ser macro.
        veredicto = (v_trend * 0.35) + (v_nlp * 0.25) + (v_volume['voto'] * 0.15) + (v_flow * 0.10) + (v_cross['voto'] * 0.15)
        
        end_activo = time.time()
        latencia = (end_activo - start_activo) * 1000
        
        print(f"📊 RESULTADOS {activo}:")
        print(f"  - Trend (35%):  {v_trend:+.2f}")
        print(f"  - NLP IA (25%): {v_nlp:+.2f}")
        print(f"  - Volume (15%): {v_volume['voto']:+.2f} | POC: {v_volume['poc']} | {v_volume['contexto']}")
        print(f"  - Cross (15%):  {v_cross['voto']:+.2f} | DXY Var: {v_cross['var_dxy']}% | SPX Var: {v_cross['var_spx']}%")
        print(f"  - Flow (10%):   {v_flow:+.2f}")
        print(f"  - HURST:        {res_hurst['h']:.4f} ({res_hurst['estado']})")
        print(f"  >>> VEREDICTO FINAL: {veredicto:+.4f}")
        print(f"  ⏱️ Latencia: {latencia:.2f} ms")
        
        if res_hurst['estado'] != "PERSISTENTE":
            print(f"  🛑 ESTATUS: VETADO por Hurst (Ruido/Rango)")
        elif abs(veredicto) >= 0.45:
            print(f"  🎯 ESTATUS: ¡GATILLO LISTO! (+0.45)")
        elif abs(veredicto) >= 0.38:
            print(f"  ⚠️ ESTATUS: PROXIMIDAD DETECTADA")
        else:
            print(f"  💤 ESTATUS: Observación pasiva")

    end_total = time.time()
    print("\n" + "="*80)
    print(f"CARGA DE SISTEMA (Surface Pro 5): {(end_total - start_total):.2f} segundos total")
    print("="*80)
    
    mt5.desconectar()
    db.desconectar()

if __name__ == "__main__":
    auditar_todo()
