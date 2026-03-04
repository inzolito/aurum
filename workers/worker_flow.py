class OrderFlowWorker:
    """
    Obrero de Flujo Institucional (Order Book Imbalance).
    Analiza el desequilibrio entre presión compradora (Bids) y vendedora (Asks)
    en los niveles inmediatos de precio del Level 2.
    Devuelve un voto entre -1.0 (presión vendedora) y +1.0 (presión compradora).

    Nota arquitectónica: acepta `db` para traducir el símbolo interno al nombre
    del broker (misma convención que TrendWorker).
    """

    def __init__(self, db, mt5):
        self.db  = db
        self.mt5 = mt5

    def analizar(self, simbolo_interno: str) -> float:
        # 1. Traducir símbolo interno al nombre real del broker
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            print(f"[FLOW] ERROR: No hay simbolo_broker para '{simbolo_interno}'")
            return 0.0

        # 2. Pedir el Order Book (Level 2)
        book = self.mt5.obtener_order_book(simbolo_broker)

        if not book or not book.get("bids") or not book.get("asks"):
            # Si el broker no provee Level 2, el obrero es neutral (no penaliza)
            print(f"[FLOW] Order Book no disponible para {simbolo_broker}. Voto neutral.")
            return 0.0

        # 3. Sumar volúmenes de los primeros 10 niveles
        # book['bids'] y book['asks'] son listas de tuplas (precio, volumen)
        vol_bids = sum(vol for _, vol in book["bids"][:10])
        vol_asks = sum(vol for _, vol in book["asks"][:10])

        total = vol_bids + vol_asks
        if total == 0:
            return 0.0

        # 4. Calcular el Imbalance (-1.0 a +1.0)
        # +1.0 = 100% presión compradora | -1.0 = 100% presión vendedora
        imbalance = (vol_bids - vol_asks) / total

        # 5. Multiplicador de sensibilidad para amplificar señales moderadas
        voto = imbalance * 1.5

        voto_final = round(max(-1.0, min(1.0, voto)), 2)
        print(f"[FLOW] {simbolo_interno} | Vol Bids={vol_bids:.1f}  Vol Asks={vol_asks:.1f} "
              f"| OBI={imbalance:+.3f} | Voto: {voto_final:+.2f}")
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
