import sys
from pathlib import Path
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import pytz

sys.path.append(str(Path(__file__).parent.parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector

def simulate_trade():
    mt5_conn = MT5Connector()
    db_conn = DBConnector()
    
    if not mt5_conn.conectar() or not db_conn.conectar():
        print("Error of connection")
        return

    simbolo_interno = "AUDJPY"
    simbolo_broker = db_conn.obtener_simbolo_broker(simbolo_interno)
    print(f"Simbolo broker: {simbolo_broker}")

    # Hora del evento: 17:38 hora local (Santiago, UTC-3) -> 20:38 UTC
    # Buscamos velas desde las 20:38 UTC
    # mt5.copy_rates_from busca desde la fecha dada hacia atras.
    # Mejor usar mt5.copy_rates_range
    
    # Hora inicio: 17:38 Santiago -> 20:38 UTC. 
    # Fecha de la imagen es 31-03-2026 17:43. La operacion era a las 17:38
    tz_santiago = pytz.timezone("America/Santiago")
    dt_inicio_local = tz_santiago.localize(datetime(2026, 3, 31, 17, 38, 0))
    dt_inicio_utc = dt_inicio_local.astimezone(pytz.utc)

    # Convert a datetime without tzinfo para copy_rates_range (usa UTC as default if setup right, or local)
    # Actually MT5 uses server time. Let's get server time offset or just fetch last N candles and filter.
    
    # Vamos a traer las últimas 100 velas de M1 (más de hora y media) y buscar la vela de las 17:38 local
    velas = mt5_conn.obtener_velas(simbolo_broker, 100)
    
    if velas is None or velas.empty:
        print("No se encontraron velas.")
        return
        
    # Extraer vela de entrada
    print("\nÚltimas 5 velas para entender el timezone:")
    print(velas.tail(5)[['time', 'open', 'high', 'low', 'close']])

    # Find the candle corresponding to 17:38 local time.
    # The 'time' column is already localized and converted to UTC timezone normally in MT5Connector, 
    # but let's check its format.
    
    # To be safe, we calculate risk parameters as Manager would have 
    from core.risk_module import RiskModule
    risk = RiskModule(db_conn, mt5_conn)
    direccion = "COMPRA" # AUDJPY Verditco > 0
    veredicto = 0.478
    
    lotes, sl, tp = risk.calcular_riesgo_completo(simbolo_broker, direccion, veredicto)
    
    print(f"\nRiesgo Calculado: Direccion={direccion}, Lotes={lotes}, SL={sl}, TP={tp}")
    
    mt5_conn.desconectar()
    db_conn.desconectar()

if __name__ == "__main__":
    simulate_trade()
