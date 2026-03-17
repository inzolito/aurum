from workers.worker_volume import VolumeWorker
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector

def test_volume():
    db = DBConnector()
    mt5 = MT5Connector()
    
    if not (db.conectar() and mt5.conectar()):
        print("Error de conexión")
        return

    worker = VolumeWorker(db, mt5)
    activos = ["XAUUSD", "GBPUSD", "US500"]
    
    for activo in activos:
        print(f"\nGenerando Volume Profile para {activo}...")
        res = worker.analizar(activo)
    
    print("\n" + "="*40)
    print(f"MAPA DE VOLUMEN - {activo}")
    print("-" * 40)
    print(f"POC:      {res['poc']}")
    print(f"VAH:      {res['vah']}")
    print(f"VAL:      {res['val']}")
    print(f"Contexto: {res['contexto']}")
    print(f"Ajuste:   {res['ajuste']}")
    print(f"Voto VP:  {res['voto']:+.2f}")
    print("="*40)
    
    mt5.desconectar()
    db.desconectar()

if __name__ == "__main__":
    test_volume()
