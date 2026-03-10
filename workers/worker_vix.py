import time
import logging
import MetaTrader5 as mt5

logger = logging.getLogger("aurum.vix")


class VIXWorker:
    """
    Obrero de Volatilidad Implícita (proxy ATR).
    Calcula el ATR(14) en H4 y lo normaliza contra la media de 50 períodos.
    Actúa como moderador de convicción: en alta volatilidad, el sistema reduce
    confianza para proteger capital; en baja volatilidad extrema, advierte de
    mercado estancado.

    Retorna un dict con 'ajuste' (aplicado al veredicto), 'nivel' y métricas.
    Niveles: CALMA, NORMAL, ELEVADA, ALTA, EXTREMA.
    """

    _CACHE_TTL   = 300  # 5 minutos (H4 cambia lento)
    _PERIODO_ATR = 14
    _PERIODO_MA  = 50   # Ventana de normalización

    def __init__(self, db, mt5_conn):
        self.db  = db
        self.mt5 = mt5_conn
        self._cache = {}

    def analizar(self, simbolo_interno: str) -> dict:
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            return self._neutro()

        ahora = time.time()
        if simbolo_broker in self._cache:
            if ahora - self._cache[simbolo_broker]['time'] < self._CACHE_TTL:
                return self._cache[simbolo_broker]['result']

        # ATR(14) en H4 para el período actual
        atr_actual = self.mt5.obtener_atr(simbolo_broker, self._PERIODO_ATR,
                                          timeframe=mt5.TIMEFRAME_H4)
        if atr_actual is None or atr_actual == 0:
            return self._neutro()

        # ATR medio de los últimos 50 períodos H4 para normalizar
        rates = mt5.copy_rates_from_pos(simbolo_broker, mt5.TIMEFRAME_H4,
                                        0, self._PERIODO_ATR + self._PERIODO_MA + 5)
        if rates is None or len(rates) < self._PERIODO_ATR + 10:
            return self._neutro()

        import pandas as pd
        import numpy as np
        df = pd.DataFrame(rates)
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['prev_close']).abs(),
            (df['low']  - df['prev_close']).abs(),
        ], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(self._PERIODO_ATR).mean()
        df.dropna(inplace=True)

        if len(df) < self._PERIODO_MA:
            return self._neutro()

        # Media móvil del ATR para los últimos _PERIODO_MA períodos
        atr_ma = df['atr'].iloc[-self._PERIODO_MA:].mean()
        if atr_ma == 0:
            return self._neutro()

        ratio = atr_actual / atr_ma

        # Clasificación y ajuste al veredicto
        if ratio > 3.0:
            ajuste = -0.20
            nivel  = "EXTREMA"
        elif ratio > 2.0:
            ajuste = -0.12
            nivel  = "ALTA"
        elif ratio > 1.5:
            ajuste = -0.06
            nivel  = "ELEVADA"
        elif ratio < 0.4:
            ajuste = -0.05  # Mercado estancado — movimiento improbable
            nivel  = "CALMA"
        else:
            ajuste = 0.0
            nivel  = "NORMAL"

        res = {
            "ajuste":     round(ajuste, 3),
            "nivel":      nivel,
            "atr_actual": round(atr_actual, 6),
            "atr_ma":     round(atr_ma, 6),
            "ratio":      round(ratio, 2),
        }

        self._cache[simbolo_broker] = {'time': ahora, 'result': res}
        logger.info(f"[VIX] {simbolo_interno} | ATR_ratio={ratio:.2f}x | {nivel} | Ajuste={ajuste:+.2f}")
        print(f"[VIX]    {simbolo_interno} | ATR_ratio={ratio:.2f}x | {nivel} | Ajuste={ajuste:+.2f}")
        return res

    def _neutro(self) -> dict:
        return {
            "ajuste":     0.0,
            "nivel":      "SIN_DATOS",
            "atr_actual": 0.0,
            "atr_ma":     0.0,
            "ratio":      1.0,
        }
