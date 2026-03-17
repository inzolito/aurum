from workers.worker_cross import CrossWorker
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector

def test_cross():
    db = DBConnector()
    mt5 = MT5Connector()
    
    if not (db.conectar() and mt5.conectar()):
        print("Error de conexión")
        return

    worker = CrossWorker(db, mt5)
    
    print("\nEvaluando Sensores Globales...")
    res_xau = worker.analizar("XAUUSD")
    res_gbp = worker.analizar("GBPJPY")
    
    print("\n" + "="*40)
    print("REPORTE DEL ESPIA GLOBAL")
    print("-" * 40)
    print(f"DXY Proxy (EURUSD inv): {res_xau['var_dxy']}%")
    print(f"SPXUSD (S&P 500):        {res_xau['var_spx']}%")
    print(f"Black Swan Detector:     {'🚨 ACTIVADO' if res_xau['black_swan'] else 'Normal'}")
    print("-" * 40)
    print(f"Voto para XAUUSD: {res_xau['voto']:+.2f} ({res_xau['ajuste']})")
    print(f"Voto para GBPJPY: {res_gbp['voto']:+.2f} ({res_gbp['ajuste']})")
    print("="*40)
    
    mt5.desconectar()
    db.desconectar()

if __name__ == "__main__":
    test_cross()
