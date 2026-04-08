import time
import pandas as pd
import ta.trend as ta_trend
import ta.momentum as ta_momentum


# MT5 Timeframe constants (evita importar MetaTrader5 directamente en el worker)
_TF_M5 = 5
_TF_H1 = 16385
_TF_H4 = 16388


def _ema(series: pd.Series, length: int) -> pd.Series:
    """Wrapper de EMA usando la librería ta."""
    return ta_trend.EMAIndicator(close=series, window=length).ema_indicator()


def _rsi(series: pd.Series, length: int) -> pd.Series:
    """Wrapper de RSI usando la librería ta."""
    return ta_momentum.RSIIndicator(close=series, window=length).rsi()


def _macd_histogram(series: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    """Calcula el histograma MACD (MACD line - Signal line). Implementación directa."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


class TrendWorker:
    """
    Obrero de Tendencia Multi-Temporal (MTF 3-Pantallas).

    Cascada Top-Down:
      H4  → Sesgo direccional (EMA50 pendiente + RSI14)
      H1  → Momentum de sesión (MACD 12,26,9 histograma)
      M5  → Gatillo de entrada (EMA9 + vela direccional)

    Regla cardinal: H4 siempre manda la dirección.
    Si H4 y H1 no están alineados, el voto se penaliza severamente.
    M5 solo confirma timing, nunca decide dirección.
    """

    # Cachés de clase — persisten entre ciclos del motor (60s)
    _cache_h4 = {}   # {simbolo: {'timestamp': float, 'sesgo': float, ...}}
    _cache_h1 = {}   # {simbolo: {'timestamp': float, 'mult': float, 'alineado': bool}}

    _CACHE_H4_SEC = 4 * 3600   # Recalcular cada 4 horas
    _CACHE_H1_SEC = 3600        # Recalcular cada 1 hora

    def __init__(self, db, mt5):
        self.db  = db
        self.mt5 = mt5

    # ==================================================================
    # MÉTODO PRINCIPAL — Interfaz compatible con Manager.evaluar()
    # ==================================================================

    def analizar(self, simbolo_interno: str) -> dict:
        params = self.db.get_parametros()
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            print(f"[TREND] ERROR: No hay simbolo_broker para '{simbolo_interno}'")
            return self._resultado_neutro()

        # Cascada Top-Down: H4 → H1 → M5
        sesgo_h4 = self._analizar_h4(simbolo_interno, simbolo_broker)
        mult_h1, h1_alineado = self._analizar_h1(simbolo_interno, simbolo_broker, sesgo_h4)
        voto_m5, datos_m5 = self._analizar_m5(simbolo_broker, params)

        if datos_m5 is None:
            return self._resultado_neutro()

        # Combinar las 3 pantallas
        voto_final = self._calcular_voto_mtf(voto_m5, sesgo_h4, mult_h1)

        dir_h4 = "ALCISTA" if sesgo_h4 > 0 else ("BAJISTA" if sesgo_h4 < 0 else "LATERAL")
        estado = f"H4:{dir_h4}({sesgo_h4:+.2f}) H1:x{mult_h1:.1f} M5:{voto_m5:+.2f}"
        print(f"[TREND-MTF] {simbolo_interno} | {estado} | Voto: {voto_final:+.2f}")

        return {
            'voto': voto_final,
            'ema_fast': datos_m5['ema_fast'],
            'ema_slow': datos_m5['ema_slow'],
            'rsi': datos_m5.get('rsi', 0.0),
            'precio': datos_m5['precio'],
            'sesgo_h4': sesgo_h4,
            'mult_h1': mult_h1,
            'estado_mtf': estado,
        }

    # ==================================================================
    # PANTALLA 1 — H4: Sesgo Estructural (La Marea)
    # EMA50 pendiente + RSI14. Caché de 4 horas.
    # ==================================================================

    def _analizar_h4(self, simbolo_interno: str, simbolo_broker: str) -> float:
        ahora = time.time()
        cache = self._cache_h4.get(simbolo_interno)
        if cache and (ahora - cache['timestamp'] < self._CACHE_H4_SEC):
            return cache['sesgo']

        df = self.mt5.obtener_velas(simbolo_broker, 60, _TF_H4)
        if df is None or len(df) < 52:
            print(f"[TREND-H4] {simbolo_interno}: Sin datos H4 suficientes ({0 if df is None else len(df)} velas)")
            return 0.0

        cierre = df['cierre']
        ema50 = _ema(cierre, 50)
        rsi = _rsi(cierre, 14)

        ema50_now  = ema50.iloc[-1]
        ema50_prev = ema50.iloc[-5]   # 5 velas H4 = 20 horas de pendiente
        rsi_now    = rsi.iloc[-1]

        if any(pd.isna(v) for v in [ema50_now, ema50_prev, rsi_now]):
            print(f"[TREND-H4] {simbolo_interno}: Indicadores NaN")
            return 0.0

        # Pendiente normalizada (% de cambio en 20 horas)
        slope = (ema50_now - ema50_prev) / ema50_prev * 100

        sesgo = 0.0
        if slope > 0.01:                       # EMA50 subiendo
            if rsi_now < 65:
                sesgo = 0.30                    # Tendencia alcista sana
            elif rsi_now < 78:
                sesgo = 0.15                    # Tendencia alcista madura
            else:
                sesgo = 0.0                     # Sobrecompra — bloqueo soft
                print(f"[TREND-H4] {simbolo_interno}: SOBRECOMPRA H4 RSI={rsi_now:.1f}")
        elif slope < -0.01:                     # EMA50 bajando
            if rsi_now > 35:
                sesgo = -0.30                   # Tendencia bajista sana
            elif rsi_now > 22:
                sesgo = -0.15                   # Tendencia bajista madura
            else:
                sesgo = 0.0                     # Sobreventa — bloqueo soft
                print(f"[TREND-H4] {simbolo_interno}: SOBREVENTA H4 RSI={rsi_now:.1f}")
        # else: slope entre -0.01 y +0.01 → lateral → sesgo 0.0

        self._cache_h4[simbolo_interno] = {
            'timestamp': ahora, 'sesgo': sesgo,
            'rsi': round(float(rsi_now), 2),
            'ema50': round(float(ema50_now), 4),
            'slope': round(slope, 4),
        }

        print(f"[TREND-H4] {simbolo_interno}: EMA50={ema50_now:.4f} slope={slope:.4f}% "
              f"RSI={rsi_now:.1f} → sesgo={sesgo:+.2f}")
        return sesgo

    # ==================================================================
    # PANTALLA 2 — H1: Momentum de Sesión (La Ola)
    # MACD (12,26,9) histograma. Caché de 1 hora.
    # H1 es el TF óptimo para MACD en Forex intraday (26h respuesta).
    # ==================================================================

    def _analizar_h1(self, simbolo_interno: str, simbolo_broker: str,
                     sesgo_h4: float) -> tuple:
        """Retorna (multiplicador: float, alineado_con_h4: bool)."""
        ahora = time.time()
        cache = self._cache_h1.get(simbolo_interno)
        if cache and (ahora - cache['timestamp'] < self._CACHE_H1_SEC):
            return cache['mult'], cache['alineado']

        df = self.mt5.obtener_velas(simbolo_broker, 50, _TF_H1)
        if df is None or len(df) < 30:
            print(f"[TREND-H1] {simbolo_interno}: Sin datos H1 suficientes")
            return 1.0, True   # Sin datos → no penalizar

        hist = _macd_histogram(df['cierre'])
        hist_now  = hist.iloc[-1]
        hist_prev = hist.iloc[-2]

        if any(pd.isna(v) for v in [hist_now, hist_prev]):
            return 1.0, True

        hist_creciendo = hist_now > hist_prev
        hist_positivo  = hist_now > 0

        # ¿H1 alineado con la dirección de H4?
        if sesgo_h4 > 0:
            # H4 alcista: H1 alineado si histograma positivo O creciendo hacia positivo
            alineado = hist_positivo or hist_creciendo
        elif sesgo_h4 < 0:
            # H4 bajista: H1 alineado EXCEPTO si histograma positivo Y creciendo
            # (máxima señal bullish en H1 = única contradicción real)
            alineado = (not hist_positivo) or (not hist_creciendo)
        else:
            # H4 lateral: no hay dirección que contradecir
            alineado = True

        # Multiplicador según alineación + dirección del momentum
        if alineado:
            mult = 1.0 if hist_creciendo else 0.8    # Alineado, momentum activo vs decayendo
        else:
            mult = 0.7 if hist_creciendo else 0.4    # Divergencia temprana vs contra-tendencia

        dir_hist = "+" if hist_creciendo else "-"
        signo_hist = "+" if hist_positivo else "-"
        print(f"[TREND-H1] {simbolo_interno}: MACD hist={hist_now:.6f}({signo_hist}{dir_hist}) "
              f"Alineado={alineado} → mult={mult:.1f}")

        self._cache_h1[simbolo_interno] = {
            'timestamp': ahora, 'mult': mult, 'alineado': alineado,
        }
        return mult, alineado

    # ==================================================================
    # PANTALLA 3 — M5: Gatillo de Entrada
    # EMA9 + vela direccional. Sin caché (se ejecuta cada ciclo de 60s).
    # M5 NO decide dirección — solo confirma timing.
    # ==================================================================

    def _analizar_m5(self, simbolo_broker: str, params: dict) -> tuple:
        """Retorna (voto_crudo: float, datos: dict | None)."""
        ema_rapida_p = int(params.get('TENDENCIA.ema_rapida', 9))
        ema_lenta_p  = int(params.get('TENDENCIA.ema_lenta',  21))

        df = self.mt5.obtener_velas(simbolo_broker, 50, _TF_M5)
        if df is None or df.empty:
            print(f"[TREND-M5] ERROR: Sin velas M5 para {simbolo_broker}")
            return 0.0, None

        cierre = df['cierre']
        ema_fast_series = _ema(cierre, ema_rapida_p)
        ema_slow_series = _ema(cierre, ema_lenta_p)

        cierre_actual = cierre.iloc[-1]
        cierre_prev   = cierre.iloc[-2]
        fast_now      = ema_fast_series.iloc[-1]
        slow_now      = ema_slow_series.iloc[-1]

        if any(pd.isna(v) for v in [fast_now, slow_now, cierre_prev]):
            print(f"[TREND-M5] {simbolo_broker}: Indicadores NaN")
            return 0.0, None

        # Lógica de gatillo simplificada (solo timing, no dirección)
        voto = 0.0

        # Estructura alcista: precio > EMA9 > EMA21
        if cierre_actual > fast_now and fast_now > slow_now:
            voto = 0.5
            if cierre_actual > cierre_prev:   # Vela direccional alcista
                voto = 0.8

        # Estructura bajista: precio < EMA9 < EMA21
        elif cierre_actual < fast_now and fast_now < slow_now:
            voto = -0.5
            if cierre_actual < cierre_prev:   # Vela direccional bajista
                voto = -0.8

        # Señal débil: precio entre EMAs (sin stack completo)
        elif cierre_actual > fast_now:
            voto = 0.20
        elif cierre_actual < fast_now:
            voto = -0.20

        # Filtro de compresión (EMAs pegadas = mercado lateral en M5)
        distancia_ema = abs(fast_now - slow_now) / cierre_actual
        if distancia_ema < 0.0001:
            voto *= 0.5

        datos = {
            'ema_fast': round(float(fast_now), 4),
            'ema_slow': round(float(slow_now), 4),
            'rsi': 0.0,   # RSI eliminado de M5 — es ruido en esta temporalidad
            'precio': round(float(cierre_actual), 4),
        }

        return round(voto, 2), datos

    # ==================================================================
    # LÓGICA DE ALINEACIÓN MTF
    # Combina las 3 pantallas en un voto final [-1.0, +1.0]
    # ==================================================================

    def _calcular_voto_mtf(self, voto_m5: float, sesgo_h4: float,
                           mult_h1: float) -> float:
        if sesgo_h4 != 0:
            # ¿M5 va en dirección contraria a H4?
            if (voto_m5 > 0 and sesgo_h4 < 0) or (voto_m5 < 0 and sesgo_h4 > 0):
                # Contra-tendencia: penalización del 70%
                voto = voto_m5 * 0.3
            else:
                # Alineado: aplicar multiplicador H1 + sesgo H4
                voto = voto_m5 * mult_h1 + sesgo_h4
        else:
            # H4 lateral: M5 opera con descuento del 30% (V19.4 — era 50%, demasiado agresivo)
            voto = voto_m5 * 0.7

        return round(max(-1.0, min(1.0, voto)), 2)

    # ==================================================================
    # HELPERS
    # ==================================================================

    def _resultado_neutro(self) -> dict:
        return {
            'voto': 0.0, 'ema_fast': 0.0, 'ema_slow': 0.0,
            'rsi': 0.0, 'precio': 0.0,
            'sesgo_h4': 0.0, 'mult_h1': 1.0, 'estado_mtf': 'SIN_DATOS',
        }


# ------------------------------------------------------------------
# TEST DE CAMPO
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config.db_connector import DBConnector
    from config.mt5_connector import MT5Connector

    db  = DBConnector()
    mt5 = MT5Connector()

    if db.conectar() and mt5.conectar():
        worker = TrendWorker(db, mt5)
        for sym in ["EURUSD", "XAUUSD", "USDJPY"]:
            print(f"\n{'='*60}")
            res = worker.analizar(sym)
            print(f"Resultado MTF {sym}:")
            for k, v in res.items():
                print(f"  {k}: {v}")
        mt5.desconectar()
        db.desconectar()
