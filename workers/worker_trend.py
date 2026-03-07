import pandas as pd
import ta.trend as ta_trend
import ta.momentum as ta_momentum


def _ema(series: pd.Series, length: int) -> pd.Series:
    """Wrapper de EMA usando la librería ta."""
    return ta_trend.EMAIndicator(close=series, window=length).ema_indicator()

def _rsi(series: pd.Series, length: int) -> pd.Series:
    """Wrapper de RSI usando la librería ta."""
    return ta_momentum.RSIIndicator(close=series, window=length).rsi()


class TrendWorker:
    """
    Obrero de Tendencia y Price Action.
    Analiza las últimas velas M1 usando EMAs y RSI para emitir un voto
    entre -1.0 (Venta Fuerte) y +1.0 (Compra Fuerte).
    """

    def __init__(self, db, mt5):
        self.db  = db
        self.mt5 = mt5

    def analizar(self, simbolo_interno: str) -> float:
        # 1. Obtener parámetros de la BD
        params = self.db.get_parametros()
        ema_rapida_p = int(params.get('TENDENCIA.ema_rapida', 9))
        ema_lenta_p  = int(params.get('TENDENCIA.ema_lenta',  21))

        # 2. Traducir símbolo interno al nombre real del broker
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            print(f"[TREND] ERROR: No hay simbolo_broker para '{simbolo_interno}'")
            return 0.0

        # 3. Pedir últimas 100 velas M1
        df = self.mt5.obtener_velas(simbolo_broker, 100)
        if df is None or df.empty:
            print(f"[TREND] ERROR: No se obtuvieron velas de {simbolo_broker}")
            return 0.0

        # 4. Cálculo de Indicadores Técnicos (librería ta)
        df['ema_fast'] = _ema(df['cierre'], ema_rapida_p)
        df['ema_slow'] = _ema(df['cierre'], ema_lenta_p)
        df['rsi']      = _rsi(df['cierre'], 14)

        # Valores de la última vela cerrada
        cierre_actual = df['cierre'].iloc[-1]
        fast_now      = df['ema_fast'].iloc[-1]
        slow_now      = df['ema_slow'].iloc[-1]
        rsi_now       = df['rsi'].iloc[-1]

        # Protección ante NaN (puede ocurrir si hay pocas velas)
        if any(pd.isna(v) for v in [fast_now, slow_now, rsi_now]):
            print(f"[TREND] WARN: Indicadores con NaN en {simbolo_broker}. Voto neutro.")
            return 0.0

        # 5. LÓGICA DE VOTACIÓN (Price Action)
        voto = 0.0

        if "US30" in simbolo_interno:
            # Lógica especial V10.0: Ruptura de EMAs (20, 50, 200)
            ema_20 = _ema(df['cierre'], 20).iloc[-1]
            ema_50 = _ema(df['cierre'], 50).iloc[-1]
            ema_200 = _ema(df['cierre'], 200).iloc[-1]
            
            if not pd.isna(ema_200):
                if cierre_actual < ema_20 and cierre_actual < ema_50 and cierre_actual < ema_200:
                    voto -= 1.0 # Máxima prioridad bajista local
                    print(f"[TREND] {simbolo_interno}: Ruptura bajista EMAs (20, 50, 200) detectada.")
                elif cierre_actual > ema_20 and cierre_actual > ema_50 and cierre_actual > ema_200:
                    voto += 1.0 # Máxima prioridad alcista local
                    print(f"[TREND] {simbolo_interno}: Ruptura alcista EMAs (20, 50, 200) detectada.")

        if voto == 0.0:
            # ESCENARIO ALCISTA (Default)
            if cierre_actual > fast_now and fast_now > slow_now:
                voto += 0.5              # Estructura alcista básica
                if rsi_now < 70:
                    voto += 0.3          # Hay espacio para subir (no sobrecomprado)
                if rsi_now < 30:
                    voto += 0.2          # Rebote en sobreventa extrema
    
            # ESCENARIO BAJISTA
            elif cierre_actual < fast_now and fast_now < slow_now:
                voto -= 0.5              # Estructura bajista básica
                if rsi_now > 30:
                    voto -= 0.3          # Hay espacio para bajar (no sobrevendido)
                if rsi_now > 70:
                    voto -= 0.2          # Rebote en sobrecompra extrema

        # 6. FILTRO DE VOLATILIDAD — Neutralizar en mercado lateral (rango)
        distancia_ema = abs(fast_now - slow_now) / cierre_actual
        if distancia_ema < 0.0001:   # EMAs comprimidas = mercado lateral
            voto = voto * 0.2

        voto_final = round(max(-1.0, min(1.0, voto)), 2)
        print(f"[TREND] {simbolo_interno} | EMA{ema_rapida_p}={fast_now:.2f} EMA{ema_lenta_p}={slow_now:.2f} "
              f"RSI={rsi_now:.1f} | Voto: {voto_final:+.2f}")
        return voto_final


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
        voto = worker.analizar("XAUUSD")
        print(f"\nVoto final del TrendWorker para XAUUSD: {voto:+.2f}")
        mt5.desconectar()
        db.desconectar()
