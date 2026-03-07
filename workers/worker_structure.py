import time
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

class StructureWorker:
    """
    Obrero Francotirador (SMC Sniper).
    Detecta Estructura (BOS), Order Blocks (OB) y Fair Value Gaps (FVG).
    """

    _cache = {}

    def __init__(self, db, mt5_conn):
        self.db = db
        self.mt5 = mt5_conn

    def analizar(self, simbolo_interno: str) -> dict:
        """
        Analiza la estructura del mercado y devuelve zonas de interés.
        Retorna: {
            'voto': float (-0.30 a +1.0),
            'ob_precio': float,
            'estado_smc': str,
            ' sniper_varedicto': str
        }
        """
        ahora = time.time()
        
        # 1. Gestión de Caché (15 min)
        if simbolo_interno in self._cache:
            cache = self._cache[simbolo_interno]
            # Si pasaron menos de 15 minutos, usamos el resultado previo
            if ahora - cache['timestamp'] < 900:
                return cache['resultado']

        # 2. Obtener datos
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            return {'voto': 0.0, 'ob_precio': 0.0, 'estado_smc': "Error Config", 'sniper_veredicto': "Simbolo no mapeado"}

        # Pedimos 300 velas para tener suficiente contexto de swings
        df = self.mt5.obtener_velas(simbolo_broker, 300)
        if df is None or df.empty:
            return {'voto': 0.0, 'ob_precio': 0.0, 'estado_smc': "Sin Datos", 'sniper_veredicto': "Error MT5"}

        # 3. Detección de Estructura (SMC)
        analisis = self._procesar_smc(df)
        
        # 4. Guardar en Caché y Retornar
        self._cache[simbolo_interno] = {
            'timestamp': ahora,
            'resultado': analisis
        }
        
        return analisis

    def _procesar_smc(self, df: pd.DataFrame) -> dict:
        # Extraer precios
        highs = df['maximo'].values
        lows = df['minimo'].values
        closes = df['cierre'].values
        opens = df['apertura'].values
        
        precio_actual = closes[-1]
        
        # A. Encontrar Swings (Fractales de 5 velas)
        # Un high es un swing si es mayor que los 2 anteriores y 2 posteriores
        # Para tiempo real, buscamos el más reciente confirmado
        
        last_high = 0.0
        last_low = 999999.0
        idx_high = -1
        idx_low = -1
        
        for i in range(len(highs)-3, 2, -1):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                last_high = highs[i]
                idx_high = i
                break
                
        for i in range(len(lows)-3, 2, -1):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                last_low = lows[i]
                idx_low = i
                break

        bos_bullish = False
        bos_bearish = False
        ob_precio = 0.0
        
        # Buscamos BOS solo DESPUÉS de que se formó el fractal
        if idx_high != -1:
            for i in range(idx_high + 1, len(closes)):
                if closes[i] > last_high:
                    bos_bullish = True
                    # El OB es la última vela bajista antes del impulso
                    # Buscamos hacia atrás desde el BOS, pero no más atrás del fractal anterior
                    limite_atras = max(1, idx_high - 10) 
                    for j in range(i, limite_atras, -1):
                        if closes[j] < opens[j]: # Vela bajista
                            ob_precio = lows[j]
                            break
                    break
            
        if idx_low != -1 and not bos_bullish: # Si ya es bullish, priorizamos ese
            for i in range(idx_low + 1, len(closes)):
                if closes[i] < last_low:
                    bos_bearish = True
                    # El OB es la última vela alcista antes del impulso
                    limite_atras = max(1, idx_low - 10)
                    for j in range(i, limite_atras, -1):
                        if closes[j] > opens[j]: # Vela alcista
                            ob_precio = highs[j]
                            break
                    break

        # C. Detección de FVG (Fair Value Gap)
        fvg_presente = False
        # Solo checkeamos el FVG más reciente (últimas 5 velas)
        for i in range(len(df)-3, len(df)-8, -1):
            if i < 1: break
            # Bullish FVG
            if highs[i-2] < lows[i]:
                fvg_presente = True
                break
            # Bearish FVG
            if lows[i-2] > highs[i]:
                fvg_presente = True
                break

        # D. Lógica de Veredicto (Gatillo Sniper)
        voto = 0.0
        estado_smc = "Rango / Acumulacion"
        veredicto = "Esperando Zona"
        
        if bos_bullish:
            estado_smc = "BOS Alcista Confirmado"
            # ¿Estamos en el OB (o cerca, 0.05%)?
            if ob_precio > 0 and abs(precio_actual - ob_precio) / ob_precio < 0.0005:
                voto = 1.0
                veredicto = "🎯 ENTRADA EN ORDER BLOCK"
            elif fvg_presente:
                voto = 0.5
                veredicto = "🧲 Atraccion por FVG"
            else:
                voto = -0.30
                veredicto = "🚫 En el aire (Riesgo FOMO)"
                
        elif bos_bearish:
            estado_smc = "BOS Bajista Confirmado"
            if ob_precio > 0 and abs(precio_actual - ob_precio) / ob_precio < 0.0005:
                voto = -1.0 # Venta fuerte
                veredicto = "🎯 ENTRADA EN ORDER BLOCK"
            elif fvg_presente:
                voto = -0.5
                veredicto = "🧲 Atraccion por FVG"
            else:
                voto = -0.30 # Negativo por estar en el aire
                veredicto = "🚫 En el aire (Riesgo FOMO)"
        else:
            voto = -0.30 # Si no hay estructura clara, penalizamos
            veredicto = "Sin Estructura Clara"

        return {
            'voto': voto,
            'ob_precio': ob_precio,
            'estado_smc': estado_smc,
            'sniper_veredicto': veredicto
        }
