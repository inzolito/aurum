import numpy as np
import pandas as pd
import MetaTrader5 as mt5

class VolumeWorker:
    """
    Obrero El Cartógrafo.
    Mapea la microestructura del mercado usando Volume Profile.
    Calcula POC (Point of Control), VAH (Value Area High) y VAL (Value Area Low).
    """

    def __init__(self, db, mt5):
        self.db  = db
        self.mt5 = mt5
        self._cache = {} # {simbolo: {'time': float, 'price': float, 'result': dict}}

    def analizar(self, simbolo_interno: str) -> dict:
        """
        Analiza el perfil de volumen de las últimas 24 horas.
        Usa caché dinámico para optimizar latencia (Lazy Refresh).
        """
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            return self._datos_vacios()

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
        df_ticks = self.mt5.obtener_ticks_24h(simbolo_broker)
        
        if df_ticks is not None and not df_ticks.empty:
            # Usar 'last' si existe, si no 'bid' + 'ask' / 2
            if 'last' in df_ticks.columns and df_ticks['last'].any():
                precios = df_ticks['last'].values
            else:
                precios = (df_ticks['bid'].values + df_ticks['ask'].values) / 2
            volumenes = df_ticks['volume'].values
        else:
            # Fallback a velas M1 (tick_volume)
            df_m1 = self.mt5.obtener_velas(simbolo_broker, 1440) # 24h en M1
            if df_m1 is None or df_m1.empty:
                return self._datos_vacios()
            precios = df_m1['cierre'].values
            volumenes = df_m1['volumen'].values

        if len(precios) == 0 or np.all(precios == 0):
            return self._datos_vacios()

        # 2. Calcular Perfil de Volumen
        # Definir tamaño del bucket (step) basado en la precisión del símbolo
        info = mt5.symbol_info(simbolo_broker)
        digits = info.digits if info else 2
        point = info.point if info else 0.01
        step = point * 10
        
        min_p, max_p = np.min(precios), np.max(precios)
        
        # Si no hay rango de precio, el POC es el precio único
        if max_p - min_p < step:
            return {
                "voto": 0.0,
                "poc": round(min_p, digits),
                "vah": round(min_p + point, digits),
                "val": round(min_p - point, digits),
                "contexto": "Rango Insuficiente",
                "ajuste": "Neutral"
            }

        bins = np.arange(min_p, max_p + step, step)
        if len(bins) < 2:
            bins = [min_p, max_p]

        hist, bin_edges = np.histogram(precios, bins=bins, weights=volumenes)
        
        if len(hist) == 0:
            return self._datos_vacios()

        # POC: Nivel con más volumen
        idx_poc = np.argmax(hist)
        poc = round(bin_edges[idx_poc], digits)
        
        # Value Area (70%)
        total_vol = np.sum(hist)
        target_vol = total_vol * 0.70
        
        # Expandir desde el POC hasta alcanzar el 70%
        curr_vol = hist[idx_poc]
        low_idx = idx_poc
        high_idx = idx_poc
        
        while curr_vol < target_vol and (low_idx > 0 or high_idx < len(hist) - 1):
            prev_low_vol = hist[low_idx-1] if low_idx > 0 else 0
            next_high_vol = hist[high_idx+1] if high_idx < len(hist) - 1 else 0
            
            if prev_low_vol >= next_high_vol:
                curr_vol += prev_low_vol
                low_idx -= 1
            else:
                curr_vol += next_high_vol
                high_idx += 1
        
        vah = round(bin_edges[high_idx + 1], digits)
        val = round(bin_edges[low_idx], digits)
        
        # 3. Lógica de Voto y Contexto
        precio_actual = precios[-1]
        voto = 0.0
        contexto = "Fuera de Valor"
        ajuste = "Neutral"

        # Zona de Valor (VA)
        if val <= precio_actual <= vah:
            contexto = "Dentro del Área de Valor"
            # Cerca de extremos (Rechazo/Soporte)
            if abs(precio_actual - val) < (vah - val) * 0.15:
                voto = 0.8  # Soporte institucional
                ajuste = "Aumentando confianza (Soporte VAL)"
            elif abs(precio_actual - vah) < (vah - val) * 0.15:
                voto = -0.8 # Resistencia institucional
                ajuste = "Aumentando confianza (Resistencia VAH)"
            elif abs(precio_actual - poc) < (vah - val) * 0.10:
                voto = 0.5  # Atracción al POC (Precio Justo)
                ajuste = "Atracción al POC"
        else:
            # Low Volume Node (LVN) o Descubrimiento de Precio
            # Si el histograma en este nivel es muy bajo (< 5% del max)
            curr_bin = np.digitize(precio_actual, bin_edges) - 1
            if 0 <= curr_bin < len(hist):
                vol_actual = hist[curr_bin]
                if vol_actual < np.max(hist) * 0.05:
                    contexto = "Zona de Vacío (LVN)"
                    voto = 0.0
                    ajuste = "Reduciendo confianza (Falta liquidez)"
            
        res = {
            "voto": round(voto, 2),
            "poc": poc,
            "vah": vah,
            "val": val,
            "contexto": contexto,
            "ajuste": ajuste
        }
        
        # Guardar en caché
        self._cache[simbolo_broker] = {
            'time': ahora,
            'price': precio_actual,
            'result': res
        }
        
        return res

    def _datos_vacios(self):
        return {"voto": 0.0, "poc": 0, "vah": 0, "val": 0, "contexto": "Sin Datos", "ajuste": "N/A"}
