import time
import logging
import MetaTrader5 as mt5

logger = logging.getLogger("aurum.spread")


class SpreadWorker:
    """
    Obrero de Spread Dinámico.
    Compara el spread bid-ask actual contra el spread típico del símbolo.
    Un spread anómalamente alto indica mercado ilíquido → penaliza convicción.
    Un spread comprimido indica actividad institucional → boost leve.

    Retorna un dict con 'ajuste' (aplicado al veredicto final como penalización),
    'estado' y métricas de diagnóstico.
    """

    # Segundos de vigencia del caché por símbolo
    _CACHE_TTL = 90

    def __init__(self, db, mt5_conn):
        self.db  = db
        self.mt5 = mt5_conn
        self._cache = {}  # {simbolo_broker: {'time': float, 'result': dict}}

    def analizar(self, simbolo_interno: str) -> dict:
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            return self._neutro()

        ahora = time.time()
        if simbolo_broker in self._cache:
            if ahora - self._cache[simbolo_broker]['time'] < self._CACHE_TTL:
                return self._cache[simbolo_broker]['result']

        # Spread actual en precio (ask - bid)
        tick_data = self.mt5.obtener_precio_actual(simbolo_broker)
        if not tick_data:
            return self._neutro()

        spread_actual = tick_data.get('spread', 0.0)
        if spread_actual <= 0:
            return self._neutro()

        # Spread de referencia: usa el campo 'spread' de symbol_info (puntos típicos × point)
        info = mt5.symbol_info(simbolo_broker)
        if info is None:
            return self._neutro()

        spread_tipico = info.spread * info.point  # en unidades de precio
        if spread_tipico <= 0:
            return self._neutro()

        ratio = spread_actual / spread_tipico

        # Clasificación y ajuste al veredicto
        if ratio > 5.0:
            ajuste = -0.25
            estado = "ILIQUIDEZ_EXTREMA"
        elif ratio > 3.0:
            ajuste = -0.15
            estado = "SPREAD_ALTO"
        elif ratio > 2.0:
            ajuste = -0.08
            estado = "SPREAD_ELEVADO"
        elif ratio < 0.5:
            ajuste = +0.05
            estado = "SPREAD_COMPRIMIDO"
        else:
            ajuste = 0.0
            estado = "SPREAD_NORMAL"

        res = {
            "ajuste":         round(ajuste, 3),
            "estado":         estado,
            "spread_actual":  round(spread_actual, 6),
            "spread_tipico":  round(spread_tipico, 6),
            "ratio":          round(ratio, 2),
        }

        self._cache[simbolo_broker] = {'time': ahora, 'result': res}
        logger.info(f"[SPREAD] {simbolo_interno} | Ratio={ratio:.2f}x | Estado={estado} | Ajuste={ajuste:+.2f}")
        print(f"[SPREAD] {simbolo_interno} | Ratio={ratio:.2f}x | {estado} | Ajuste={ajuste:+.2f}")
        return res

    def _neutro(self) -> dict:
        return {
            "ajuste":        0.0,
            "estado":        "SIN_DATOS",
            "spread_actual": 0.0,
            "spread_tipico": 0.0,
            "ratio":         1.0,
        }
