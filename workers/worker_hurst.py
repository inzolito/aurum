import numpy as np
import pandas as pd
import MetaTrader5 as mt5

class HurstWorker:
    """
    Obrero Juez de Persistencia.
    Calcula el exponente de Hurst (H) para determinar si la serie
    tiene tendencia persistente (H > 0.55), es ruido (0.45 < H < 0.55)
    o es antipersistente (H < 0.45).
    """

    def __init__(self, db, mt5):
        self.db  = db
        self.mt5 = mt5
        self._cache = {} # {simbolo: {'time': float, 'price': float, 'result': dict}}

    def calcular_hurst(self, series: pd.Series) -> float:
        """
        Calcula el exponente de Hurst usando una aproximación de Rescaled Range simplificada.
        """
        if len(series) < 100:
            return 0.5
        
        # Trabajamos con los retornos para medir persistencia de movimiento
        y = np.log(series).diff().dropna().values
        if len(y) < 100: return 0.5

        def get_rs(data):
            # R/S = (max(Z) - min(Z)) / std(data)
            mean_adj = data - np.mean(data)
            Z = np.cumsum(mean_adj)
            R = np.max(Z) - np.min(Z)
            S = np.std(data)
            return R / S if S > 0 else 0

        # Dividimos la serie en fragmentos de tamaño 'n'
        lags = [20, 40, 80, 160, 320, 512]
        rs_values = []
        for n in lags:
            # Calculamos R/S promedio para fragmentos de tamaño n
            num_chunks = len(y) // n
            if num_chunks == 0: continue
            
            rs_chunks = []
            for i in range(num_chunks):
                chunk = y[i*n : (i+1)*n]
                rs = get_rs(chunk)
                if rs > 0: rs_chunks.append(rs)
            
            if rs_chunks:
                rs_values.append(np.mean(rs_chunks))

        if len(rs_values) < 2:
            return 0.5

        # Ajuste lineal log(R/S) vs log(n)
        poly = np.polyfit(np.log(lags[:len(rs_values)]), np.log(rs_values), 1)
        return poly[0]

    def analizar(self, simbolo_interno: str) -> dict:
        """
        Analiza la persistencia del activo usando 1,024 velas M1.
        Usa caché dinámico para optimizar latencia (Lazy Refresh).
        """
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            return {"h": 0.5, "estado": "RUIDO"}

        # --- LÓGICA DE CACHÉ (Lazy Refresh) ---
        import time
        ahora = time.time()
        tick_actual = mt5.symbol_info_tick(simbolo_broker)
        precio_actual = tick_actual.last if tick_actual else 0
        
        if simbolo_broker in self._cache:
            cache = self._cache[simbolo_broker]
            diff_tiempo = ahora - cache['time']
            diff_precio = abs(precio_actual - cache['price']) / cache['price'] if cache['price'] > 0 else 1.0
            
            # Solo recalcular si han pasado > 5 min o el precio movio > 0.1%
            if diff_tiempo < 300 and diff_precio < 0.001:
                return cache['result']

        # --- PROCESAMIENTO REAL ---
        # Pedir 1,024 velas como solicitó el usuario
        df = self.mt5.obtener_velas(simbolo_broker, 1024)
        data_quality = "OK"
        if df is None or df.empty or len(df) < 1024:
            if df is not None and len(df) > 100:
                print(f"[HURST] {simbolo_interno} — datos insuficientes ({len(df)} velas, se requieren 1024). Calidad: BAJA.")
                data_quality = "LOW"
                h = self.calcular_hurst(df['cierre'])
            else:
                return {"h": 0.5, "estado": "RUIDO", "data_quality": "NO_DATA"}
        else:
            h = self.calcular_hurst(df['cierre'])

        h = round(h, 4)

        if h > 0.55:
            estado = "PERSISTENTE"
        elif h < 0.45:
            estado = "ANTIPERSISTENTE"
        else:
            estado = "RUIDO"

        res = {"h": h, "estado": estado, "data_quality": data_quality}
        
        # Guardar en caché
        self._cache[simbolo_broker] = {
            'time': ahora,
            'price': precio_actual,
            'result': res
        }
        
        print(f"[HURST] {simbolo_interno} | H: {h:.4f} | Estado: {estado}")
        return res

# Test rápido
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config.db_connector import DBConnector
    from config.mt5_connector import MT5Connector

    db = DBConnector()
    mt5 = MT5Connector()
    if db.conectar() and mt5.conectar():
        hurst = HurstWorker(db, mt5)
        res = hurst.analizar("XAUUSD")
        print(f"Resultado: {res}")
        mt5.desconectar()
        db.desconectar()
