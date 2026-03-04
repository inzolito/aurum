import pandas as pd
import numpy as np
from datetime import datetime

class CrossWorker:
    """
    Obrero Espía Global.
    Analiza correlaciones intermarket y sensores de riesgo global.
    Sensores: SPXUSD (Riesgo), EURUSD (Proxy DXY).
    """

    def __init__(self, db, mt5):
        self.db = db
        self.mt5 = mt5
        self.sensor_spx = "SPXUSD"
        self.sensor_dxy_proxy = "EURUSD_i" # Usamos el símbolo del broker

    def analizar(self, simbolo_interno: str) -> dict:
        """
        Analiza la armonía global y retorna el voto (-1.0 a 1.0) y telemetría.
        """
        # 1. Obtener variaciones de los sensores (últimas 24h o sesión actual)
        var_spx = self._obtener_variacion(self.sensor_spx)
        var_dxy = -self._obtener_variacion(self.sensor_dxy_proxy) # Invertimos EURUSD para simular DXY

        # 2. Lógica de Voto por Armonía
        voto = 0.0
        divergencia = "Ninguna"
        
        # Caso Oro (XAUUSD) vs DXY
        if "XAU" in simbolo_interno:
            # Correlación Inversa: Si DXY sube, Oro debería bajar.
            if var_dxy > 0.30: # Dólar fuerte
                voto = -1.0
                divergencia = "Detectada en DXY (Dólar Fuerte)"
            elif var_dxy < -0.30: # Dólar débil
                voto = 1.0
        
        # Caso GBPJPY vs SPX (Risk-On/Off)
        elif "GBPJPY" in simbolo_interno:
            # Si SPX cae fuerte (Risk-Off), el Yen se fortalece (GBPJPY cae)
            if var_spx < -0.50:
                voto = -1.0
                divergencia = "Detectada en SPX (Risk-Off)"
            elif var_spx > 0.50:
                voto = 1.0

        # Caso NASDAQ (USTEC) vs SPX
        elif "USTEC" in simbolo_interno:
            if var_spx > 0:
                voto = 1.0 if var_spx > 0.20 else 0.5
            else:
                voto = -1.0 if var_spx < -0.20 else -0.5

        # 3. Detección de Black Swan (DXY Proxy > 1%)
        black_swan = abs(var_dxy) > 1.0
        
        return {
            "voto": round(voto, 2),
            "var_spx": round(var_spx, 2),
            "var_dxy": round(var_dxy, 2),
            "divergencia": divergencia,
            "black_swan": black_swan,
            "ajuste": "Aportando Confianza" if voto > 0 else ("Restando Confianza" if voto < 0 else "Neutral")
        }

    def _obtener_variacion(self, simbolo_broker: str) -> float:
        """Calcula la variación porcentual simplificada de las últimas 100 velas M1."""
        df = self.mt5.obtener_velas(simbolo_broker, 100)
        if df is None or df.empty:
            return 0.0
        
        precio_inicial = df['cierre'].iloc[0]
        precio_final = df['cierre'].iloc[-1]
        
        if precio_inicial == 0: return 0.0
        return ((precio_final - precio_inicial) / precio_inicial) * 100

# Test
if __name__ == "__main__":
    from config.db_connector import DBConnector
    from config.mt5_connector import MT5Connector
    db = DBConnector()
    mt5 = MT5Connector()
    if db.conectar() and mt5.conectar():
        spy = CrossWorker(db, mt5)
        print(spy.analizar("XAUUSD"))
        db.desconectar()
        mt5.desconectar()
