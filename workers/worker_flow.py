class OrderFlowWorker:
    """
    Obrero de Flujo Institucional (Order Book Imbalance).
    Estrategia primaria: Level 2 real via mt5.market_book_get().
    Fallback automático: Presión de velas (bull/bear volume delta) en M1 últimas 4h
    cuando el broker no provee datos de libro de órdenes.
    Devuelve un voto entre -1.0 (presión vendedora) y +1.0 (presión compradora).
    """

    # Número de velas M1 para el fallback (~4 horas)
    _VELAS_FALLBACK = 240

    def __init__(self, db, mt5):
        self.db  = db
        self.mt5 = mt5

    def analizar(self, simbolo_interno: str) -> float:
        # 1. Traducir símbolo interno al nombre real del broker
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            print(f"[FLOW] ERROR: No hay simbolo_broker para '{simbolo_interno}'")
            return 0.0

        # 2. Intentar Level 2 real
        book = self.mt5.obtener_order_book(simbolo_broker)

        if book and book.get("bids") and book.get("asks"):
            return self._calcular_obi_level2(simbolo_interno, simbolo_broker, book)

        # 3. Fallback: OBI sintético desde presión de velas M1
        print(f"[FLOW] Level 2 no disponible para {simbolo_broker}. Usando fallback de presión de velas.")
        return self._calcular_obi_velas(simbolo_interno, simbolo_broker)

    def _calcular_obi_level2(self, simbolo_interno: str, simbolo_broker: str, book: dict) -> float:
        """Calcula OBI usando datos reales de Level 2."""
        vol_bids = sum(vol for _, vol in book["bids"][:10])
        vol_asks = sum(vol for _, vol in book["asks"][:10])

        total = vol_bids + vol_asks
        if total == 0:
            return 0.0

        imbalance = (vol_bids - vol_asks) / total
        voto = round(max(-1.0, min(1.0, imbalance * 1.5)), 2)
        print(f"[FLOW/L2] {simbolo_interno} | Bids={vol_bids:.1f} Asks={vol_asks:.1f} | OBI={imbalance:+.3f} | Voto: {voto:+.2f}")
        return voto

    def _calcular_obi_velas(self, simbolo_interno: str, simbolo_broker: str) -> float:
        """
        OBI sintético: compara volumen de velas alcistas vs bajistas en las
        últimas N velas M1. Una vela es alcista si cierre > apertura.
        bull_vol = suma de volumen de velas alcistas
        bear_vol = suma de volumen de velas bajistas
        OBI = (bull_vol - bear_vol) / (bull_vol + bear_vol) * 1.5
        """
        df = self.mt5.obtener_velas(simbolo_broker, self._VELAS_FALLBACK)
        if df is None or df.empty:
            print(f"[FLOW/FB] Sin datos de velas para {simbolo_broker}. Voto neutral.")
            return 0.0

        bull_mask = df['cierre'] > df['apertura']
        # Convertir a int para evitar overflow en numpy uint64 (MT5 retorna tick_volume como uint64)
        bull_vol = int(df.loc[bull_mask, 'volumen'].sum())
        bear_vol = int(df.loc[~bull_mask, 'volumen'].sum())

        total = bull_vol + bear_vol
        if total == 0:
            return 0.0

        imbalance = (bull_vol - bear_vol) / total
        voto = round(max(-1.0, min(1.0, imbalance * 1.5)), 2)
        print(f"[FLOW/FB] {simbolo_interno} | BullVol={bull_vol:.0f} BearVol={bear_vol:.0f} | OBI={imbalance:+.3f} | Voto: {voto:+.2f}")
        return voto


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
        worker = OrderFlowWorker(db, mt5)

        print("\n" + "=" * 55)
        print("  OrderFlowWorker — Test de Campo")
        print("=" * 55)

        for simbolo in ["XAUUSD", "XAGUSD", "EURUSD"]:
            print(f"\n--- {simbolo} ---")
            voto = worker.analizar(simbolo)
            print(f">>> Voto final: {voto:+.2f}")

        mt5.desconectar()
        db.desconectar()
