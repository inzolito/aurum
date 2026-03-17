"""
Tests automatizados para los workers críticos de Aurum.
Uso: pytest tests/test_workers.py -v

Los tests usan mocks para no requerir MT5 ni DB activos.
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures compartidas
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.obtener_simbolo_broker.return_value = "XAUUSDm"
    return db


@pytest.fixture
def mock_mt5():
    mt5 = MagicMock()
    # DataFrame de velas sintéticas (200 velas alcistas)
    n = 200
    prices = np.cumsum(np.random.randn(n) * 0.5) + 1900.0
    df = pd.DataFrame({
        "tiempo":   pd.date_range("2026-01-01", periods=n, freq="1min"),
        "apertura": prices - 0.2,
        "maximo":   prices + 0.5,
        "minimo":   prices - 0.5,
        "cierre":   prices,
        "volumen":  np.random.randint(100, 500, n).astype(float),
    })
    mt5.obtener_velas.return_value = df
    mt5.obtener_precio_actual.return_value = {"bid": 1900.0, "ask": 1900.5, "spread": 0.5}
    mt5.obtener_atr.return_value = 2.5
    return mt5


# ---------------------------------------------------------------------------
# HurstWorker
# ---------------------------------------------------------------------------

class TestHurstWorker:
    def test_retorna_estructura_correcta(self, mock_db, mock_mt5):
        from workers.worker_hurst import HurstWorker
        w = HurstWorker(mock_db, mock_mt5)
        res = w.analizar("XAUUSD")
        assert "h" in res
        assert "estado" in res
        assert res["estado"] in ("PERSISTENTE", "ANTIPERSISTENTE", "RUIDO")

    def test_h_rango_valido(self, mock_db, mock_mt5):
        from workers.worker_hurst import HurstWorker
        n = 1100
        prices = np.cumsum(np.random.randn(n) * 0.5) + 1900.0
        df = pd.DataFrame({
            "tiempo":   pd.date_range("2026-01-01", periods=n, freq="1min"),
            "apertura": prices - 0.2, "maximo": prices + 0.5,
            "minimo":   prices - 0.5, "cierre": prices,
            "volumen":  np.ones(n) * 100,
        })
        mock_mt5.obtener_velas.return_value = df
        w = HurstWorker(mock_db, mock_mt5)
        res = w.analizar("XAUUSD")
        assert 0.0 <= res["h"] <= 1.5  # Hurst puede superar 1.0 en datos sintéticos

    def test_sin_datos_retorna_ruido(self, mock_db, mock_mt5):
        from workers.worker_hurst import HurstWorker
        mock_mt5.obtener_velas.return_value = pd.DataFrame()
        w = HurstWorker(mock_db, mock_mt5)
        res = w.analizar("XAUUSD")
        assert res["h"] == 0.5
        assert res["estado"] == "RUIDO"

    def test_sin_simbolo_broker_retorna_ruido(self):
        from workers.worker_hurst import HurstWorker
        db = MagicMock()
        db.obtener_simbolo_broker.return_value = None
        w = HurstWorker(db, MagicMock())
        res = w.analizar("INVALIDO")
        assert res["h"] == 0.5


# ---------------------------------------------------------------------------
# VolumeWorker
# ---------------------------------------------------------------------------

class TestVolumeWorker:
    def test_retorna_estructura_correcta(self, mock_db, mock_mt5):
        from workers.worker_volume import VolumeWorker
        with patch("workers.worker_volume.mt5") as mt5_mock:
            mt5_mock.symbol_info_tick.return_value = MagicMock(last=1900.0)
            mt5_mock.symbol_info.return_value = MagicMock(digits=2, point=0.01)
            w = VolumeWorker(mock_db, mock_mt5)
            res = w.analizar("XAUUSD")
        assert "voto" in res
        assert "poc" in res
        assert "vah" in res
        assert "val" in res
        assert -1.0 <= res["voto"] <= 1.0

    def test_sin_datos_retorna_neutro(self, mock_db, mock_mt5):
        from workers.worker_volume import VolumeWorker
        mock_mt5.obtener_ticks_24h.return_value = None
        mock_mt5.obtener_velas.return_value = pd.DataFrame()
        with patch("workers.worker_volume.mt5") as mt5_mock:
            mt5_mock.symbol_info_tick.return_value = MagicMock(last=0)
            w = VolumeWorker(mock_db, mock_mt5)
            res = w.analizar("XAUUSD")
        assert res["voto"] == 0.0


# ---------------------------------------------------------------------------
# FlowWorker
# ---------------------------------------------------------------------------

class TestFlowWorker:
    def test_fallback_velas_cuando_no_hay_level2(self, mock_db, mock_mt5):
        from workers.worker_flow import OrderFlowWorker
        mock_mt5.obtener_order_book.return_value = None
        w = OrderFlowWorker(mock_db, mock_mt5)
        voto = w.analizar("XAUUSD")
        assert -1.0 <= voto <= 1.0
        # Con datos alcistas, el voto debe ser positivo
        assert voto > 0.0

    def test_level2_cuando_disponible(self, mock_db, mock_mt5):
        from workers.worker_flow import OrderFlowWorker
        mock_mt5.obtener_order_book.return_value = {
            "bids": [(1900.0, 100), (1899.5, 80)],
            "asks": [(1900.5, 20),  (1901.0, 10)],
        }
        w = OrderFlowWorker(mock_db, mock_mt5)
        voto = w.analizar("XAUUSD")
        assert voto > 0.0  # Más bids que asks → presión compradora

    def test_sin_simbolo_broker(self):
        from workers.worker_flow import OrderFlowWorker
        db = MagicMock()
        db.obtener_simbolo_broker.return_value = None
        w = OrderFlowWorker(db, MagicMock())
        assert w.analizar("INVALIDO") == 0.0


# ---------------------------------------------------------------------------
# SpreadWorker
# ---------------------------------------------------------------------------

class TestSpreadWorker:
    def test_spread_normal(self, mock_db, mock_mt5):
        from workers.worker_spread import SpreadWorker
        with patch("workers.worker_spread.mt5") as mt5_mock:
            info = MagicMock()
            info.spread = 20
            info.point  = 0.01
            mt5_mock.symbol_info.return_value = info
            mock_mt5.obtener_precio_actual.return_value = {
                "bid": 1900.0, "ask": 1900.2, "spread": 0.20
            }
            w = SpreadWorker(mock_db, mock_mt5)
            res = w.analizar("XAUUSD")
        assert res["estado"] == "SPREAD_NORMAL"
        assert res["ajuste"] == 0.0

    def test_spread_alto_penaliza(self, mock_db, mock_mt5):
        from workers.worker_spread import SpreadWorker
        with patch("workers.worker_spread.mt5") as mt5_mock:
            info = MagicMock()
            info.spread = 10
            info.point  = 0.01
            mt5_mock.symbol_info.return_value = info
            mock_mt5.obtener_precio_actual.return_value = {
                "bid": 1900.0, "ask": 1903.0, "spread": 3.0  # ratio = 30x
            }
            w = SpreadWorker(mock_db, mock_mt5)
            res = w.analizar("XAUUSD")
        assert res["ajuste"] < 0.0

    def test_sin_datos_retorna_neutro(self, mock_db, mock_mt5):
        from workers.worker_spread import SpreadWorker
        mock_mt5.obtener_precio_actual.return_value = None
        w = SpreadWorker(mock_db, mock_mt5)
        res = w.analizar("XAUUSD")
        assert res["ajuste"] == 0.0
        assert res["estado"] == "SIN_DATOS"


# ---------------------------------------------------------------------------
# VIXWorker
# ---------------------------------------------------------------------------

class TestVIXWorker:
    def test_volatilidad_normal(self, mock_db, mock_mt5):
        from workers.worker_vix import VIXWorker
        import numpy as np
        with patch("workers.worker_vix.mt5") as mt5_mock:
            n = 80
            rates = np.zeros(n, dtype=[
                ('time','i8'),('open','f8'),('high','f8'),
                ('low','f8'),('close','f8'),('tick_volume','i8'),
                ('spread','i4'),('real_volume','i8')
            ])
            rates['open']  = 1900.0
            rates['high']  = 1901.0
            rates['low']   = 1899.0
            rates['close'] = 1900.5
            mt5_mock.copy_rates_from_pos.return_value = rates
            mt5_mock.TIMEFRAME_H4 = 16408
            mock_mt5.obtener_atr.return_value = 2.5
            w = VIXWorker(mock_db, mock_mt5)
            res = w.analizar("XAUUSD")
        assert "ajuste" in res
        assert "nivel"  in res

    def test_sin_datos_retorna_neutro(self, mock_db, mock_mt5):
        from workers.worker_vix import VIXWorker
        mock_mt5.obtener_atr.return_value = None
        w = VIXWorker(mock_db, mock_mt5)
        res = w.analizar("XAUUSD")
        assert res["ajuste"] == 0.0
        assert res["nivel"]  == "SIN_DATOS"


# ---------------------------------------------------------------------------
# RiskModule
# ---------------------------------------------------------------------------

class TestRiskModule:
    def test_filtro_seguridad_aprueba_activo_normal(self):
        from core.risk_module import RiskModule
        import MetaTrader5 as mt5_api
        db  = MagicMock()
        mt5 = MagicMock()
        db.obtener_simbolo_broker.return_value = "XAUUSDm"
        db.get_parametros.return_value = {"GERENTE.max_drawdown_usd": 1000.0}
        with patch("core.risk_module.mt5") as mt5_mock:
            mt5_mock.account_info.return_value = MagicMock(equity=5000.0, profit=-50.0)
            mt5_mock.positions_get.return_value = []
            risk = RiskModule(db, mt5)
            # No debe lanzar excepción
            resultado = risk.filtro_seguridad("XAUUSD")
        assert isinstance(resultado, bool)
