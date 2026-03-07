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
        Trae las últimas `cantidad` velas del símbolo.
        Incluye lógica de suscripción forzada para evitar 'puntos ciegos' en índices.
        """
        # 1. Asegurar que el símbolo esté en el Market Watch
        if not mt5.symbol_select(simbolo, True):
            # print(f"[MT5] No se pudo seleccionar/suscribir a {simbolo}")
            return pd.DataFrame()

        # 1.5 Check if symbol is actually visible/active
        if mt5.symbol_info_tick(simbolo) is None:
            print(f"[MT5] 🚨 ALERTA: {simbolo} no es visible en Market Watch.")
            # La alerta real a Telegram se dispara desde el Manager/Notifier
            return pd.DataFrame()

        # 2. Intentar obtener tasas (Mínimo 1,000 barras para estabilidad)
        n_velas = max(cantidad, 1000)
        rates = mt5.copy_rates_from_pos(simbolo, timeframe, 0, n_velas)
        
        # 3. Si falla y es un índice/volátil, intentar forzar descarga sincronizando
        if rates is None or len(rates) == 0:
            print(f"[MT5] Reintentando captura forzada de {simbolo}...")
            # Forzamos una pequeña espera para sincronización de terminal
            import time
            time.sleep(0.5)
            rates = mt5.copy_rates_from_pos(simbolo, timeframe, 0, cantidad)

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            print(f"[MT5] ERROR final obteniendo velas de {simbolo}: {error}")
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

    def obtener_ticks_24h(self, simbolo: str) -> pd.DataFrame | None:
        """
        Descarga todos los ticks de las últimas 24 horas para un símbolo.
        Útil para Volume Profile de alta precisión.
        """
        from datetime import datetime, timedelta
        
        # Suscripción forzada si no está en Market Watch
        if not mt5.symbol_select(simbolo, True):
            # print(f"[MT5] No se pudo seleccionar/suscribir a {simbolo} para ticks.")
            return None

        ahora = datetime.now()
        hace_24h = ahora - timedelta(hours=24)
        
        ticks = mt5.copy_ticks_from(simbolo, hace_24h, 1000000, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            print(f"[MT5] No se pudieron obtener ticks para {simbolo}")
            return None
        
        df = pd.DataFrame(ticks)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def obtener_precio_actual(self, simbolo: str) -> dict | None:
        """Retorna el bid y ask actuales del símbolo."""
        tick = mt5.symbol_info_tick(simbolo)
        if tick is None:
            print(f"[MT5] No se pudo obtener precio de {simbolo}")
            return None
        return {"bid": tick.bid, "ask": tick.ask, "spread": round(tick.ask - tick.bid, 5)}

    def obtener_atr(self, simbolo: str, periodo: int = 14, timeframe=mt5.TIMEFRAME_M15) -> float | None:
        """
        Calcula el ATR (Average True Range) del símbolo.
        Por defecto: 14 periodos en M15.
        """
        # Pedimos periodo + 1 para calcular las diferencias
        rates = mt5.copy_rates_from_pos(simbolo, timeframe, 0, periodo + 1)
        if rates is None or len(rates) < periodo:
            return None
        
        df = pd.DataFrame(rates)
        # TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['prev_close']).abs(),
            (df['low'] - df['prev_close']).abs()
        ], axis=1).max(axis=1)
        
        atr = df['tr'].rolling(window=periodo).mean().iloc[-1]
        return float(atr) if not pd.isna(atr) else None

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

    def mover_sl(self, ticket: int, nuevo_sl: float) -> bool:
        """
        Modifica el Stop Loss de una posición abierta.
        Utilizado para la lógica de Breakeven.
        """
        posiciones = mt5.positions_get(ticket=ticket)
        if not posiciones:
            return False
        
        pos = posiciones[0]
        simbolo_info = mt5.symbol_info(pos.symbol)
        if simbolo_info is None:
            return False
            
        nuevo_sl = round(nuevo_sl, simbolo_info.digits)
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": nuevo_sl,
            "tp": pos.tp,
            "symbol": pos.symbol
        }
        
        resultado = mt5.order_send(request)
        if resultado is None or resultado.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[MT5] ERROR moviendo SL ticket {ticket}: {resultado.comment if resultado else 'N/A'}")
            return False
        return True

    def cerrar_todas_las_posiciones(self):
        """
        Cierra TODAS las posiciones abiertas por mercado.
        Procedimiento de emergencia para Kill-Switch.
        """
        posiciones = mt5.positions_get()
        if not posiciones:
            return
        
        for pos in posiciones:
            tipo_cierre = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            precio = mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY \
                     else mt5.symbol_info_tick(pos.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": tipo_cierre,
                "price": precio,
                "deviation": 20,
                "magic": 20250101,
                "comment": "Aurum Kill-Switch",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5.order_send(request)
            print(f"[MT5] Kill-Switch: Cerrada posicion {pos.ticket} {pos.symbol}")
