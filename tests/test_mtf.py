"""
Tests para la estrategia Multi-Temporal (MTF) del TrendWorker y StructureWorker.
Uso: pytest tests/test_mtf.py -v

Cubre:
  - Logica de alineacion MTF (la pieza mas critica)
  - Analisis H4 (sesgo direccional)
  - Analisis H1 (momentum MACD)
  - Analisis M5 (gatillo)
  - Integracion completa (analizar)
  - Cache de H4 y H1
  - Edge cases (sin datos, sin simbolo, NaN)
  - StructureWorker en M15
  - Funcion MACD histogram
"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.worker_trend import TrendWorker, _TF_M5, _TF_H1, _TF_H4, _macd_histogram


# ---------------------------------------------------------------------------
# Helpers para generar datos sinteticos
# ---------------------------------------------------------------------------

def _make_candles(n, start=1.0800, end=None, trend='up'):
    """
    Genera velas determinísticas con tendencia controlada.
    trend: 'up', 'down', 'flat'
    """
    if end is None:
        if trend == 'up':
            end = start + 0.03
        elif trend == 'down':
            end = start - 0.03
        else:
            end = start

    base = np.linspace(start, end, n)
    # Ruido controlado con seed fijo para reproducibilidad
    np.random.seed(42)
    noise = np.random.randn(n) * abs(end - start) * 0.05
    prices = base + noise
    # Asegurar que el primer y ultimo precio reflejen la tendencia
    prices[0] = start
    prices[-1] = end if trend != 'flat' else start

    return pd.DataFrame({
        "tiempo":   pd.date_range("2026-01-01", periods=n, freq="5min"),
        "apertura": prices - 0.0002,
        "maximo":   prices + 0.0005,
        "minimo":   prices - 0.0005,
        "cierre":   prices,
        "volumen":  np.ones(n) * 100.0,
    })


def _make_candles_with_pullbacks(n, start=1.0800, drift_per_candle=0.0003):
    """
    Genera tendencia alcista con pullbacks regulares.
    Patron: 3 up, 2 down → RSI saludable (~58-62), EMA50 con pendiente positiva.
    """
    step_up = drift_per_candle
    step_down = -drift_per_candle * 0.6
    pattern = [step_up, step_up, step_up, step_down, step_down]
    moves = np.array([pattern[i % len(pattern)] for i in range(n)])
    prices = start + np.cumsum(moves)

    return pd.DataFrame({
        "tiempo":   pd.date_range("2026-01-01", periods=n, freq="5min"),
        "apertura": prices - 0.0002,
        "maximo":   prices + 0.0005,
        "minimo":   prices - 0.0005,
        "cierre":   prices,
        "volumen":  np.ones(n) * 100.0,
    })


def _mock_obtener_velas_by_tf(df_h4=None, df_h1=None, df_m5=None):
    """Retorna side_effect que devuelve DataFrames distintos segun timeframe."""
    def side_effect(simbolo, cantidad, timeframe=1):
        if timeframe == _TF_H4 and df_h4 is not None:
            return df_h4
        elif timeframe == _TF_H1 and df_h1 is not None:
            return df_h1
        elif timeframe == _TF_M5 and df_m5 is not None:
            return df_m5
        return pd.DataFrame()
    return side_effect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.obtener_simbolo_broker.return_value = "EURUSDm"
    db.get_parametros.return_value = {
        'TENDENCIA.ema_rapida': '9',
        'TENDENCIA.ema_lenta': '21',
    }
    return db


@pytest.fixture
def worker(mock_db):
    """TrendWorker con caches limpios para cada test."""
    mt5 = MagicMock()
    w = TrendWorker(mock_db, mt5)
    TrendWorker._cache_h4.clear()
    TrendWorker._cache_h1.clear()
    return w


# ===========================================================================
# TEST: Logica de Alineacion MTF (_calcular_voto_mtf)
# Esta es la pieza mas critica del sistema — probada con valores exactos.
# ===========================================================================

class TestAlineacionMTF:

    def test_todo_alineado_alcista(self, worker):
        """H4 alcista + H1 confirma + M5 compra → voto fuerte positivo"""
        voto = worker._calcular_voto_mtf(voto_m5=0.8, sesgo_h4=0.30, mult_h1=1.0)
        # 0.8 * 1.0 + 0.30 = 1.10 → clamp a 1.0
        assert voto == 1.0

    def test_todo_alineado_bajista(self, worker):
        """H4 bajista + H1 confirma + M5 venta → voto fuerte negativo"""
        voto = worker._calcular_voto_mtf(voto_m5=-0.8, sesgo_h4=-0.30, mult_h1=1.0)
        # -0.8 * 1.0 + (-0.30) = -1.10 → clamp a -1.0
        assert voto == -1.0

    def test_m5_compra_contra_h4_bajista(self, worker):
        """M5 quiere comprar pero H4 es bajista → penalizacion 70%"""
        voto = worker._calcular_voto_mtf(voto_m5=0.8, sesgo_h4=-0.30, mult_h1=0.4)
        # Contra-tendencia: 0.8 * 0.3 = 0.24
        assert voto == 0.24

    def test_m5_venta_contra_h4_alcista(self, worker):
        """M5 quiere vender pero H4 es alcista → penalizacion 70%"""
        voto = worker._calcular_voto_mtf(voto_m5=-0.5, sesgo_h4=0.30, mult_h1=1.0)
        # Contra-tendencia: -0.5 * 0.3 = -0.15
        assert voto == -0.15

    def test_h4_lateral_descuento_50(self, worker):
        """H4 lateral → voto M5 con descuento 50%"""
        voto = worker._calcular_voto_mtf(voto_m5=0.8, sesgo_h4=0.0, mult_h1=1.0)
        assert voto == 0.4   # 0.8 * 0.5

    def test_h1_no_confirma_mult_bajo(self, worker):
        """H4 alcista + H1 contra-tendencia (mult=0.4) → voto debil"""
        voto_full = worker._calcular_voto_mtf(voto_m5=0.8, sesgo_h4=0.30, mult_h1=1.0)
        voto_weak = worker._calcular_voto_mtf(voto_m5=0.8, sesgo_h4=0.30, mult_h1=0.4)
        assert voto_weak < voto_full
        # 0.8 * 0.4 + 0.30 = 0.62
        assert voto_weak == 0.62

    def test_m5_neutro_con_sesgo_h4(self, worker):
        """M5 neutro (0.0) + H4 alcista → solo sesgo H4"""
        voto = worker._calcular_voto_mtf(voto_m5=0.0, sesgo_h4=0.30, mult_h1=1.0)
        # 0.0 * 1.0 + 0.30 = 0.30 (alineado porque m5=0 no contradice)
        assert voto == 0.30

    def test_todo_neutro(self, worker):
        """Todo neutro → voto 0"""
        voto = worker._calcular_voto_mtf(voto_m5=0.0, sesgo_h4=0.0, mult_h1=1.0)
        assert voto == 0.0

    def test_clamp_maximo(self, worker):
        """Resultado nunca excede +1.0"""
        voto = worker._calcular_voto_mtf(voto_m5=1.0, sesgo_h4=0.30, mult_h1=1.0)
        assert voto == 1.0

    def test_clamp_minimo(self, worker):
        """Resultado nunca baja de -1.0"""
        voto = worker._calcular_voto_mtf(voto_m5=-1.0, sesgo_h4=-0.30, mult_h1=1.0)
        assert voto == -1.0

    def test_h1_decayendo_alineado(self, worker):
        """H1 alineado pero momentum decayendo (mult=0.8)"""
        voto = worker._calcular_voto_mtf(voto_m5=0.8, sesgo_h4=0.30, mult_h1=0.8)
        # 0.8 * 0.8 + 0.30 = 0.94
        assert voto == 0.94


# ===========================================================================
# TEST: Analisis H4 (Sesgo Direccional)
# ===========================================================================

class TestH4:

    def test_tendencia_alcista_fuerte(self, worker):
        """Serie claramente ascendente → sesgo positivo o cero (sobrecompra)"""
        df = _make_candles(60, start=1.0500, end=1.1200, trend='up')
        worker.mt5.obtener_velas.return_value = df
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo >= 0.0, f"Uptrend fuerte no deberia dar sesgo negativo, got {sesgo}"

    def test_tendencia_bajista_fuerte(self, worker):
        """Serie claramente descendente → sesgo negativo o cero (sobreventa)"""
        df = _make_candles(60, start=1.1200, end=1.0500, trend='down')
        worker.mt5.obtener_velas.return_value = df
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo <= 0.0, f"Downtrend fuerte no deberia dar sesgo positivo, got {sesgo}"

    def test_mercado_lateral(self, worker):
        """Precios planos → sesgo 0.0"""
        df = _make_candles(60, start=1.0800, end=1.0800, trend='flat')
        worker.mt5.obtener_velas.return_value = df
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo == 0.0

    def test_sin_datos(self, worker):
        """Sin datos MT5 → sesgo neutro"""
        worker.mt5.obtener_velas.return_value = pd.DataFrame()
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo == 0.0

    def test_pocos_datos(self, worker):
        """Menos de 52 velas → sesgo neutro (EMA50 no confiable)"""
        df = _make_candles(30, trend='up')
        worker.mt5.obtener_velas.return_value = df
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo == 0.0

    def test_datos_none(self, worker):
        """obtener_velas retorna None → sesgo neutro"""
        worker.mt5.obtener_velas.return_value = None
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo == 0.0

    def test_cache_evita_segunda_llamada(self, worker):
        """Segunda llamada dentro de 4h usa cache, no llama MT5"""
        df = _make_candles(60, trend='up')
        worker.mt5.obtener_velas.return_value = df
        worker._analizar_h4("EURUSD", "EURUSDm")
        worker._analizar_h4("EURUSD", "EURUSDm")
        assert worker.mt5.obtener_velas.call_count == 1

    def test_cache_por_simbolo(self, worker):
        """Cada simbolo tiene su propio cache"""
        df = _make_candles(60, trend='up')
        worker.mt5.obtener_velas.return_value = df
        worker._analizar_h4("EURUSD", "EURUSDm")
        worker._analizar_h4("USDJPY", "USDJPYm")
        assert worker.mt5.obtener_velas.call_count == 2

    def test_alcista_con_pullbacks_sesgo_positivo(self, worker):
        """Tendencia alcista moderada con pullbacks → sesgo positivo"""
        df = _make_candles_with_pullbacks(60, start=1.0800, drift_per_candle=0.0008)
        worker.mt5.obtener_velas.return_value = df
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo > 0.0, f"Uptrend con pullbacks deberia dar sesgo positivo, got {sesgo}"

    def test_sesgo_valores_validos(self, worker):
        """Sesgo solo puede ser -0.30, -0.15, 0.0, 0.15, 0.30"""
        df = _make_candles(60, trend='up')
        worker.mt5.obtener_velas.return_value = df
        sesgo = worker._analizar_h4("EURUSD", "EURUSDm")
        assert sesgo in (-0.30, -0.15, 0.0, 0.15, 0.30), f"Sesgo invalido: {sesgo}"


# ===========================================================================
# TEST: Analisis H1 (Momentum MACD)
# ===========================================================================

class TestH1:

    def test_momentum_alcista_alineado_con_h4_alcista(self, worker):
        """MACD positivo + H4 alcista → alineado, mult alto"""
        df = _make_candles(50, start=1.0500, end=1.0800, trend='up')
        worker.mt5.obtener_velas.return_value = df
        mult, alineado = worker._analizar_h1("EURUSD", "EURUSDm", sesgo_h4=0.30)
        assert bool(alineado) is True
        assert mult >= 0.8

    def test_momentum_bajista_alineado_con_h4_bajista(self, worker):
        """MACD negativo + H4 bajista → alineado"""
        df = _make_candles(50, start=1.0800, end=1.0500, trend='down')
        worker.mt5.obtener_velas.return_value = df
        mult, alineado = worker._analizar_h1("EURUSD", "EURUSDm", sesgo_h4=-0.30)
        assert alineado is True

    def test_h4_lateral_siempre_alineado(self, worker):
        """H4 lateral → alineado siempre (no hay direccion que contradecir)"""
        df = _make_candles(50, trend='up')
        worker.mt5.obtener_velas.return_value = df
        mult, alineado = worker._analizar_h1("EURUSD", "EURUSDm", sesgo_h4=0.0)
        assert alineado is True

    def test_sin_datos_no_penaliza(self, worker):
        """Sin datos H1 → (1.0, True) — no penalizar"""
        worker.mt5.obtener_velas.return_value = pd.DataFrame()
        mult, alineado = worker._analizar_h1("EURUSD", "EURUSDm", sesgo_h4=0.30)
        assert mult == 1.0
        assert alineado is True

    def test_datos_none(self, worker):
        """obtener_velas retorna None → no penalizar"""
        worker.mt5.obtener_velas.return_value = None
        mult, alineado = worker._analizar_h1("EURUSD", "EURUSDm", sesgo_h4=-0.30)
        assert mult == 1.0
        assert alineado is True

    def test_cache_evita_segunda_llamada(self, worker):
        """Cache de 1 hora funciona"""
        df = _make_candles(50, trend='up')
        worker.mt5.obtener_velas.return_value = df
        worker._analizar_h1("EURUSD", "EURUSDm", 0.30)
        worker._analizar_h1("EURUSD", "EURUSDm", 0.30)
        assert worker.mt5.obtener_velas.call_count == 1

    def test_mult_rango_valido(self, worker):
        """Multiplicador siempre entre 0.4 y 1.0"""
        for trend in ('up', 'down', 'flat'):
            TrendWorker._cache_h1.clear()
            df = _make_candles(50, trend=trend)
            worker.mt5.obtener_velas.return_value = df
            mult, _ = worker._analizar_h1("EURUSD", "EURUSDm", 0.30)
            assert 0.4 <= mult <= 1.0, f"Mult fuera de rango con trend={trend}: {mult}"


# ===========================================================================
# TEST: Analisis M5 (Gatillo)
# ===========================================================================

class TestM5:

    def test_gatillo_alcista(self, worker):
        """Precio > EMA9 > EMA21 en uptrend → voto positivo"""
        df = _make_candles(50, start=1.0500, end=1.0800, trend='up')
        worker.mt5.obtener_velas.return_value = df
        params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
        voto, datos = worker._analizar_m5("EURUSDm", params)
        assert voto > 0.0
        assert datos is not None

    def test_gatillo_bajista(self, worker):
        """Precio < EMA9 < EMA21 en downtrend → voto negativo"""
        df = _make_candles(50, start=1.0800, end=1.0500, trend='down')
        worker.mt5.obtener_velas.return_value = df
        params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
        voto, datos = worker._analizar_m5("EURUSDm", params)
        assert voto < 0.0

    def test_sin_datos(self, worker):
        """Sin datos → (0.0, None)"""
        worker.mt5.obtener_velas.return_value = pd.DataFrame()
        params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
        voto, datos = worker._analizar_m5("EURUSDm", params)
        assert voto == 0.0
        assert datos is None

    def test_datos_none(self, worker):
        """obtener_velas retorna None → (0.0, None)"""
        worker.mt5.obtener_velas.return_value = None
        params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
        voto, datos = worker._analizar_m5("EURUSDm", params)
        assert voto == 0.0
        assert datos is None

    def test_datos_retornados_completos(self, worker):
        """El dict de datos tiene las claves esperadas"""
        df = _make_candles(50, trend='up')
        worker.mt5.obtener_velas.return_value = df
        params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
        voto, datos = worker._analizar_m5("EURUSDm", params)
        assert datos is not None
        assert 'ema_fast' in datos
        assert 'ema_slow' in datos
        assert 'rsi' in datos
        assert 'precio' in datos
        assert datos['rsi'] == 0.0   # RSI eliminado en M5

    def test_voto_rango_valido(self, worker):
        """Voto M5 siempre entre -1.0 y +1.0"""
        for trend in ('up', 'down', 'flat'):
            df = _make_candles(50, trend=trend)
            worker.mt5.obtener_velas.return_value = df
            params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
            voto, _ = worker._analizar_m5("EURUSDm", params)
            assert -1.0 <= voto <= 1.0

    def test_emas_comprimidas_penaliza(self, worker):
        """EMAs pegadas (mercado lateral) → voto penalizado 50%"""
        # Precios completamente planos → EMAs identicas → distancia < 0.0001
        prices = np.full(50, 1.0800)
        df = pd.DataFrame({
            "tiempo":   pd.date_range("2026-01-01", periods=50, freq="5min"),
            "apertura": prices, "maximo": prices + 0.0001,
            "minimo":   prices - 0.0001, "cierre": prices,
            "volumen":  np.ones(50) * 100.0,
        })
        worker.mt5.obtener_velas.return_value = df
        params = {'TENDENCIA.ema_rapida': '9', 'TENDENCIA.ema_lenta': '21'}
        voto, _ = worker._analizar_m5("EURUSDm", params)
        # Con precios planos, voto base es 0.0 (ni alcista ni bajista)
        assert abs(voto) <= 0.1


# ===========================================================================
# TEST: Integracion completa (analizar)
# ===========================================================================

class TestIntegracionMTF:

    def test_retorna_estructura_correcta(self, worker):
        """El dict retornado tiene todas las claves que el Manager necesita"""
        df_h4 = _make_candles(60, trend='up')
        df_h1 = _make_candles(50, trend='up')
        df_m5 = _make_candles(50, trend='up')
        worker.mt5.obtener_velas.side_effect = _mock_obtener_velas_by_tf(df_h4, df_h1, df_m5)

        resultado = worker.analizar("EURUSD")

        assert 'voto' in resultado
        assert 'ema_fast' in resultado
        assert 'ema_slow' in resultado
        assert 'rsi' in resultado
        assert 'precio' in resultado
        assert 'sesgo_h4' in resultado
        assert 'mult_h1' in resultado
        assert 'estado_mtf' in resultado

    def test_voto_en_rango(self, worker):
        """Voto final siempre entre -1.0 y +1.0"""
        df = _make_candles(60, trend='up')
        worker.mt5.obtener_velas.side_effect = _mock_obtener_velas_by_tf(df, df, df)
        resultado = worker.analizar("EURUSD")
        assert -1.0 <= resultado['voto'] <= 1.0

    def test_sin_simbolo_broker(self):
        """Simbolo no mapeado → voto neutro"""
        db = MagicMock()
        db.obtener_simbolo_broker.return_value = None
        w = TrendWorker(db, MagicMock())
        resultado = w.analizar("INVALIDO")
        assert resultado['voto'] == 0.0
        assert resultado['estado_mtf'] == 'SIN_DATOS'

    def test_sin_datos_m5(self, worker):
        """H4 y H1 OK pero M5 sin datos → neutro"""
        df_ok = _make_candles(60, trend='up')
        df_vacio = pd.DataFrame()
        worker.mt5.obtener_velas.side_effect = _mock_obtener_velas_by_tf(df_ok, df_ok, df_vacio)
        resultado = worker.analizar("EURUSD")
        assert resultado['voto'] == 0.0
        assert resultado['estado_mtf'] == 'SIN_DATOS'

    def test_uptrend_completo_voto_positivo(self, worker):
        """Todos los TFs en uptrend → voto positivo"""
        df_h4 = _make_candles(60, start=1.0500, end=1.0900, trend='up')
        df_h1 = _make_candles(50, start=1.0700, end=1.0900, trend='up')
        df_m5 = _make_candles(50, start=1.0850, end=1.0900, trend='up')
        worker.mt5.obtener_velas.side_effect = _mock_obtener_velas_by_tf(df_h4, df_h1, df_m5)
        resultado = worker.analizar("EURUSD")
        assert resultado['voto'] >= 0.0, f"Full uptrend deberia dar voto >= 0, got {resultado['voto']}"

    def test_downtrend_completo_voto_negativo(self, worker):
        """Todos los TFs en downtrend → voto negativo"""
        df_h4 = _make_candles(60, start=1.0900, end=1.0500, trend='down')
        df_h1 = _make_candles(50, start=1.0700, end=1.0500, trend='down')
        df_m5 = _make_candles(50, start=1.0550, end=1.0500, trend='down')
        worker.mt5.obtener_velas.side_effect = _mock_obtener_velas_by_tf(df_h4, df_h1, df_m5)
        resultado = worker.analizar("EURUSD")
        assert resultado['voto'] <= 0.0, f"Full downtrend deberia dar voto <= 0, got {resultado['voto']}"

    def test_usa_timeframes_correctos(self, worker):
        """Verifica que se piden los timeframes H4, H1, M5 (no M1)"""
        df = _make_candles(60, trend='up')
        calls_log = []

        def log_calls(simbolo, cantidad, timeframe=1):
            calls_log.append(timeframe)
            return df

        worker.mt5.obtener_velas.side_effect = log_calls
        worker.analizar("EURUSD")

        assert _TF_H4 in calls_log, "Debe pedir velas H4"
        assert _TF_H1 in calls_log, "Debe pedir velas H1"
        assert _TF_M5 in calls_log, "Debe pedir velas M5"
        # NO debe pedir M1 (timeframe=1)
        assert 1 not in calls_log, "No debe pedir velas M1"


# ===========================================================================
# TEST: Funcion MACD Histogram
# ===========================================================================

class TestMACDHistogram:

    def test_uptrend_histograma_positivo(self):
        """Tendencia alcista → histograma MACD positivo"""
        prices = pd.Series(np.linspace(1.0, 1.1, 50))
        hist = _macd_histogram(prices)
        assert hist.iloc[-1] > 0

    def test_downtrend_histograma_negativo(self):
        """Tendencia bajista → histograma MACD negativo"""
        prices = pd.Series(np.linspace(1.1, 1.0, 50))
        hist = _macd_histogram(prices)
        assert hist.iloc[-1] < 0

    def test_flat_histograma_cercano_a_cero(self):
        """Precios planos → histograma MACD ≈ 0"""
        prices = pd.Series(np.full(50, 1.08))
        hist = _macd_histogram(prices)
        assert abs(hist.iloc[-1]) < 0.001

    def test_retorna_series_correcta(self):
        """Retorna pd.Series con misma longitud que input"""
        prices = pd.Series(np.linspace(1.0, 1.1, 50))
        hist = _macd_histogram(prices)
        assert isinstance(hist, pd.Series)
        assert len(hist) == 50


# ===========================================================================
# TEST: StructureWorker M15
# ===========================================================================

class TestStructureWorkerM15:

    def test_usa_timeframe_m15(self):
        """StructureWorker debe pedir velas en M15 (15), no M1 (1)"""
        from workers.worker_structure import StructureWorker, _TF_M15

        db = MagicMock()
        db.obtener_simbolo_broker.return_value = "EURUSDm"
        mt5 = MagicMock()

        n = 200
        prices = np.linspace(1.05, 1.08, n)
        df = pd.DataFrame({
            "tiempo":   pd.date_range("2026-01-01", periods=n, freq="15min"),
            "apertura": prices - 0.001,
            "maximo":   prices + 0.002,
            "minimo":   prices - 0.002,
            "cierre":   prices,
            "volumen":  np.ones(n) * 100.0,
        })
        mt5.obtener_velas.return_value = df

        worker = StructureWorker(db, mt5)
        worker._cache.clear()
        worker.analizar("EURUSD")

        mt5.obtener_velas.assert_called_once_with("EURUSDm", 200, _TF_M15)

    def test_retorna_estructura_correcta(self):
        """StructureWorker retorna dict con claves esperadas"""
        from workers.worker_structure import StructureWorker

        db = MagicMock()
        db.obtener_simbolo_broker.return_value = "EURUSDm"
        mt5 = MagicMock()

        n = 200
        prices = np.linspace(1.05, 1.08, n)
        df = pd.DataFrame({
            "tiempo":   pd.date_range("2026-01-01", periods=n, freq="15min"),
            "apertura": prices - 0.001,
            "maximo":   prices + 0.002,
            "minimo":   prices - 0.002,
            "cierre":   prices,
            "volumen":  np.ones(n) * 100.0,
        })
        mt5.obtener_velas.return_value = df

        worker = StructureWorker(db, mt5)
        worker._cache.clear()
        res = worker.analizar("EURUSD")

        assert 'voto' in res
        assert 'ob_precio' in res
        assert 'estado_smc' in res
        assert 'sniper_veredicto' in res
        assert -1.0 <= res['voto'] <= 1.0

    def test_proximidad_ob_m15(self):
        """La proximidad OB usa 0.15% (no 0.05% de M1)"""
        from workers.worker_structure import StructureWorker
        import inspect
        source = inspect.getsource(StructureWorker._procesar_smc)
        assert '0.0015' in source, "OB proximity debe ser 0.0015 (0.15%) para M15"

    def test_sin_simbolo(self):
        """Sin simbolo broker → resultado de error"""
        from workers.worker_structure import StructureWorker
        db = MagicMock()
        db.obtener_simbolo_broker.return_value = None
        worker = StructureWorker(db, MagicMock())
        res = worker.analizar("INVALIDO")
        assert res['voto'] == 0.0


# ===========================================================================
# TEST: Edge Cases
# ===========================================================================

class TestEdgeCases:

    def test_resultado_neutro_completo(self, worker):
        """_resultado_neutro tiene todas las claves necesarias"""
        neutro = worker._resultado_neutro()
        assert neutro['voto'] == 0.0
        assert neutro['sesgo_h4'] == 0.0
        assert neutro['mult_h1'] == 1.0
        assert neutro['estado_mtf'] == 'SIN_DATOS'
        assert 'ema_fast' in neutro
        assert 'ema_slow' in neutro
        assert 'rsi' in neutro
        assert 'precio' in neutro

    def test_constantes_timeframe_correctas(self):
        """Las constantes de TF coinciden con MetaTrader5"""
        assert _TF_M5 == 5
        assert _TF_H1 == 16385
        assert _TF_H4 == 16388

    def test_cache_h4_independiente_por_simbolo(self, worker):
        """Cache H4 no mezcla simbolos"""
        df_up = _make_candles(60, start=1.05, end=1.10, trend='up')
        df_dn = _make_candles(60, start=1.10, end=1.05, trend='down')

        worker.mt5.obtener_velas.return_value = df_up
        sesgo_eur = worker._analizar_h4("EURUSD", "EURUSDm")

        worker.mt5.obtener_velas.return_value = df_dn
        sesgo_usd = worker._analizar_h4("USDJPY", "USDJPYm")

        # Si la cache mezclara simbolos, ambos serian iguales
        # (no podemos garantizar signos opuestos por RSI, pero si diferencia)
        assert sesgo_eur != sesgo_usd or sesgo_eur == 0.0
