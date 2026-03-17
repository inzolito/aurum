import pandas as pd
import numpy as np
from datetime import datetime

class CrossWorker:
    """
    Obrero Espía Global.
    Analiza correlaciones intermarket y sensores de riesgo global.
    Sensores: SPXUSD (Riesgo), EURUSD_i (Proxy DXY).
    FIX-CROSS-02 (2026-03-11): Sensores unificados con sufijo _i del broker.
    """

    # Sensores con sufijo _i del broker. Si el broker los tiene sin sufijo,
    # _obtener_variacion prueba ambas variantes automáticamente.
    def __init__(self, db, mt5):
        self.db = db
        self.mt5 = mt5
        # US500 usa 'SPXUSD' (sin _i) confirmado en tabla activos. Se mantiene fallback automático.
        self.sensor_spx = "SPXUSD"
        self.sensor_dxy_proxy = "EURUSD_i"
        self.sensor_oil = "XTIUSD_i"  # V10.0: Sensor Petróleo

    def analizar(self, simbolo_interno: str) -> dict:
        """
        Analiza la armonía global y retorna el voto (-1.0 a 1.0) y telemetría.
        """
        # 1. Obtener variaciones de los sensores (V8.0: Exception Safe)
        try:
            var_spx = self._obtener_variacion(self.sensor_spx)
            var_dxy = -self._obtener_variacion(self.sensor_dxy_proxy) 
            var_oil = self._obtener_variacion(self.sensor_oil)
        except Exception as e:
            print(f"[CROSS] ERROR obteniendo sensores: {e}")
            var_spx, var_dxy, var_oil = 0.0, 0.0, 0.0

        # 2. Lógica de Voto por Armonía
        # FIX-CROSS-01 (2026-03-10): Cobertura extendida a todos los activos del portfolio.
        # Antes solo XAU, GBPJPY y USTEC/US30 tenían reglas; el resto retornaba 0.0 siempre.
        voto = 0.0
        divergencia = "Ninguna"

        # --- METALES PRECIOSOS: correlación inversa con DXY ---
        if "XAU" in simbolo_interno or "XAG" in simbolo_interno:
            # Si DXY sube → metales bajan (dólar fuerte = refugio en USD, no en oro/plata)
            if var_dxy > 0.30:
                voto = -1.0
                divergencia = "Detectada en DXY (Dólar Fuerte)"
            elif var_dxy < -0.30:
                voto = 1.0
                divergencia = "Detectada en DXY (Dólar Débil)"

        # --- PETRÓLEO: correlación directa con var_oil del sensor ---
        elif "XTI" in simbolo_interno or "XBR" in simbolo_interno:
            if var_oil > 0.40:
                voto = 1.0
                divergencia = "Momentum alcista en Petróleo"
            elif var_oil < -0.40:
                voto = -1.0
                divergencia = "Momentum bajista en Petróleo"
            elif var_oil > 0.15:
                voto = 0.5
            elif var_oil < -0.15:
                voto = -0.5

        # --- FOREX vs DXY: EURUSD y GBPUSD — correlación inversa al dólar ---
        elif "EURUSD" in simbolo_interno or "GBPUSD" in simbolo_interno:
            # DXY sube → EUR/GBP caen (el par cotiza moneda vs USD)
            if var_dxy > 0.30:
                voto = -1.0
                divergencia = "Detectada en DXY (Dólar Fuerte)"
            elif var_dxy < -0.30:
                voto = 1.0
                divergencia = "Detectada en DXY (Dólar Débil)"

        # --- USDJPY: Risk-On/Off via SPX (Yen = refugio en Risk-Off) ---
        elif "USDJPY" in simbolo_interno:
            # SPX sube (Risk-On) → USDJPY sube (Yen se debilita)
            if var_spx > 0.50:
                voto = 1.0
                divergencia = "Risk-On en SPX (Yen débil)"
            elif var_spx < -0.50:
                voto = -1.0
                divergencia = "Risk-Off en SPX (Yen fuerte)"

        # --- GBPJPY: híbrido Risk-On/Off via SPX ---
        elif "GBPJPY" in simbolo_interno:
            if var_spx < -0.50:
                voto = -1.0
                divergencia = "Detectada en SPX (Risk-Off)"
            elif var_spx > 0.50:
                voto = 1.0

        # --- ÍNDICES: USTEC (Nasdaq) y US30 (Dow) vs SPX ---
        elif "USTEC" in simbolo_interno or "US30" in simbolo_interno or "US500" in simbolo_interno:
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
            "var_oil": round(var_oil, 2),
            "divergencia": divergencia,
            "black_swan": black_swan,
            "ajuste": "Aportando Confianza" if voto > 0 else ("Restando Confianza" if voto < 0 else "Neutral")
        }

    def _obtener_variacion(self, simbolo_broker: str) -> float:
        """
        Calcula la variación porcentual de las últimas 100 velas M1.
        FIX-CROSS-02: Prueba primero el símbolo dado; si falla, prueba sin '_i'
        y sin sufijo para máxima compatibilidad con distintos brokers.
        """
        candidatos = [simbolo_broker]
        # Probar alternativas si el principal no tiene datos
        if simbolo_broker.endswith("_i"):
            candidatos.append(simbolo_broker[:-2])  # sin _i
        else:
            candidatos.append(simbolo_broker + "_i")  # con _i

        for sym in candidatos:
            df = self.mt5.obtener_velas(sym, 100)
            if df is not None and not df.empty:
                precio_inicial = df['cierre'].iloc[0]
                precio_final = df['cierre'].iloc[-1]
                if precio_inicial == 0:
                    continue
                variacion = ((precio_final - precio_inicial) / precio_inicial) * 100
                if sym != simbolo_broker:
                    print(f"[CROSS] ⚠️ Sensor '{simbolo_broker}' vacío, usando '{sym}' como fallback.")
                return variacion

        print(f"[CROSS] Sin datos para sensor '{simbolo_broker}'. Retornando 0.0.")
        return 0.0

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
