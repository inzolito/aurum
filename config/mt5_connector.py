import os
import pandas as pd
import MetaTrader5 as mt5
from dotenv import load_dotenv

load_dotenv()


class MT5Connector:
    """
    Puente de comunicación local con la terminal MetaTrader 5.
    Encapsula la librería mt5 para aislar al resto del sistema de su API.
    """

    def __init__(self):
        self.conectado = False

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def conectar(self) -> bool:
        """
        Inicializa y conecta con la terminal MT5.
        Lee credenciales del .env si están definidas.
        Retorna True si la conexión es exitosa.
        """
        login    = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server   = os.getenv("MT5_SERVER")

        # Si hay credenciales en .env, inicializar con ellas
        if login and password and server:
            ok = mt5.initialize(
                login=int(login),
                password=password,
                server=server,
            )
        else:
            # Usar la sesión activa de la terminal abierta en el PC
            ok = mt5.initialize()

        if not ok:
            error = mt5.last_error()
            print(f"[MT5] ERROR al conectar: {error}")
            return False

        info = mt5.terminal_info()
        print(f"[MT5] Conectado -> {info.name} | Build: {info.build}")
        self.conectado = True
        return True

    def desconectar(self):
        """Cierra la conexión con MT5."""
        mt5.shutdown()
        self.conectado = False
        print("[MT5] Desconectado.")

    # ------------------------------------------------------------------
    # Datos de Mercado
    # ------------------------------------------------------------------

    def obtener_velas(self, simbolo: str, cantidad: int = 100,
                      timeframe=mt5.TIMEFRAME_M1) -> pd.DataFrame:
        """
        Trae las últimas `cantidad` velas del símbolo en el timeframe dado.
        Por defecto: velas de 1 minuto (M1).
        Retorna un DataFrame de pandas con columnas OHLCV + tiempo UTC.
        """
        rates = mt5.copy_rates_from_pos(simbolo, timeframe, 0, cantidad)
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            print(f"[MT5] ERROR obteniendo velas de {simbolo}: {error}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.rename(columns={
            "time":      "tiempo",
            "open":      "apertura",
            "high":      "maximo",
            "low":       "minimo",
            "close":     "cierre",
            "tick_volume": "volumen",
        }, inplace=True)
        return df[["tiempo", "apertura", "maximo", "minimo", "cierre", "volumen"]]

    def obtener_order_book(self, simbolo: str) -> dict | None:
        """
        Retorna el Level 2 (libro de órdenes) del símbolo.
        Formato: {'bids': [(precio, volumen), ...], 'asks': [(precio, volumen), ...]}
        """
        book = mt5.market_book_get(simbolo)
        if book is None:
            print(f"[MT5] Order Book no disponible para {simbolo}")
            return None

        bids = [(e.price, e.volume) for e in book if e.type == mt5.BOOK_TYPE_BUY]
        asks = [(e.price, e.volume) for e in book if e.type == mt5.BOOK_TYPE_SELL]
        return {"bids": bids, "asks": asks}

    def obtener_precio_actual(self, simbolo: str) -> dict | None:
        """Retorna el bid y ask actuales del símbolo."""
        tick = mt5.symbol_info_tick(simbolo)
        if tick is None:
            print(f"[MT5] No se pudo obtener precio de {simbolo}")
            return None
        return {"bid": tick.bid, "ask": tick.ask, "spread": round(tick.ask - tick.bid, 5)}

    # ------------------------------------------------------------------
    # Ejecución de Órdenes
    # ------------------------------------------------------------------

    def enviar_orden(self, simbolo: str, direccion: str, lotes: float,
                     sl: float, tp: float, comentario: str = "AurumBot") -> dict:
        """
        Envía una orden de mercado al broker vía MT5.
        direccion: 'COMPRA' | 'VENTA'
        Retorna un diccionario:
            {'status': 'ok', 'ticket': int} si es exitosa.
            {'status': 'error', 'retcode': int, 'comment': str} si falla.
        """
        tipo = mt5.ORDER_TYPE_BUY if direccion == "COMPRA" else mt5.ORDER_TYPE_SELL
        precio = mt5.symbol_info_tick(simbolo).ask if tipo == mt5.ORDER_TYPE_BUY \
                 else mt5.symbol_info_tick(simbolo).bid

        # Determinar el modo de llenado soportado (Filling Mode)
        filling_mode = mt5.ORDER_FILLING_FOK # Por defecto FOK
        simbolo_info = mt5.symbol_info(simbolo)
        if simbolo_info is not None:
            # 1 = FOK, 2 = IOC, 3 = FOK|IOC
            if (simbolo_info.filling_mode & 1):
                filling_mode = mt5.ORDER_FILLING_FOK
            elif (simbolo_info.filling_mode & 2):
                filling_mode = mt5.ORDER_FILLING_IOC
            else:
                filling_mode = mt5.ORDER_FILLING_RETURN
                
            # Normalizar decimales a los permitidos por el broker (evita errores 10030/10016)
            digitos = simbolo_info.digits
            precio  = round(precio, digitos)
            sl      = round(sl, digitos)
            tp      = round(tp, digitos)

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       simbolo,
            "volume":       lotes,
            "type":         tipo,
            "price":        precio,
            "sl":           sl,
            "tp":           tp,
            "deviation":    10,          # Slippage máximo en puntos
            "magic":        20250101,    # ID único del bot
            "comment":      comentario,
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        resultado = mt5.order_send(request)

        if resultado is None or resultado.retcode != mt5.TRADE_RETCODE_DONE:
            error = resultado.retcode if resultado else mt5.last_error()
            msg_error = resultado.comment if resultado else "Failed to send request"
            print(f"[MT5] ERROR al enviar orden {direccion} {simbolo}: retcode={error} ({msg_error})")
            return {"status": "error", "retcode": error, "comment": msg_error}

        print(f"[MT5] Orden ejecutada -> Ticket: {resultado.order} | {direccion} {lotes} lotes {simbolo} @ {precio}")
        return {"status": "ok", "ticket": resultado.order}
