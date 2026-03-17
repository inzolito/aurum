"""
MetaTrader5 Shim para Linux/Cloud
===================================
Implementa la misma interfaz del módulo MetaTrader5 de Python pero
delega todas las operaciones a MetaAPI Cloud via REST/WebSocket.

Permite correr Aurum en Linux (GCP VM) sin instalar la terminal MT5.
Python encuentra este paquete local antes que cualquier pip package.

Requiere en .env:
    METAAPI_TOKEN    = tu token JWT de MetaAPI
    METAAPI_ACCOUNT_ID = UUID de la cuenta en MetaAPI
"""

import os
import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
#  Constantes — valores exactos del módulo MetaTrader5 original
# ─────────────────────────────────────────────────────────────────────────────

TIMEFRAME_M1  = 1;   TIMEFRAME_M2  = 2;   TIMEFRAME_M3  = 3
TIMEFRAME_M4  = 4;   TIMEFRAME_M5  = 5;   TIMEFRAME_M6  = 6
TIMEFRAME_M10 = 10;  TIMEFRAME_M12 = 12;  TIMEFRAME_M15 = 15
TIMEFRAME_M20 = 20;  TIMEFRAME_M30 = 30
TIMEFRAME_H1  = 16385; TIMEFRAME_H2  = 16386; TIMEFRAME_H3  = 16387
TIMEFRAME_H4  = 16388; TIMEFRAME_H6  = 16390; TIMEFRAME_H8  = 16392
TIMEFRAME_H12 = 16396; TIMEFRAME_D1  = 16408
TIMEFRAME_W1  = 32769; TIMEFRAME_MN1 = 49153

SYMBOL_TRADE_MODE_DISABLED  = 0
SYMBOL_TRADE_MODE_CLOSEONLY = 1
SYMBOL_TRADE_MODE_LONGSONLY = 2
SYMBOL_TRADE_MODE_SHORTSONLY = 3
SYMBOL_TRADE_MODE_FULL      = 4

ORDER_TYPE_BUY  = 0;  ORDER_TYPE_SELL = 1
ORDER_FILLING_FOK = 0; ORDER_FILLING_IOC = 1; ORDER_FILLING_RETURN = 2

TRADE_ACTION_DEAL = 1; TRADE_ACTION_SLTP = 6; TRADE_ACTION_MODIFY = 6
ORDER_TIME_GTC = 0;    TRADE_RETCODE_DONE = 10009

BOOK_TYPE_BUY  = 1;    BOOK_TYPE_SELL = 0
COPY_TICKS_ALL = 1;    COPY_TICKS_INFO = 2; COPY_TICKS_TRADE = 4

# Mapeo de TIMEFRAME_* (int) a string de MetaAPI
_TF_MAP = {
    1: '1m', 2: '2m', 3: '3m', 4: '4m', 5: '5m', 6: '6m',
    10: '10m', 12: '12m', 15: '15m', 20: '20m', 30: '30m',
    16385: '1h', 16386: '2h', 16387: '3h', 16388: '4h',
    16390: '6h', 16392: '8h', 16396: '12h',
    16408: '1d', 32769: '1w', 49153: '1mn',
}

# ─────────────────────────────────────────────────────────────────────────────
#  Event Loop dedicado en hilo daemon
# ─────────────────────────────────────────────────────────────────────────────

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True, name="MetaAPILoop").start()


def _run(coro, timeout=30):
    """Ejecuta una coroutine async de forma síncrona desde cualquier hilo."""
    try:
        future = asyncio.run_coroutine_threadsafe(coro, _loop)
        return future.result(timeout=timeout)
    except asyncio.TimeoutError:
        _set_last_error(1, "MetaAPI timeout")
        return None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Estado global del shim
# ─────────────────────────────────────────────────────────────────────────────

_api        = None
_connection = None
_connected  = False
_last_error = (0, "Success")

_TOKEN      = os.getenv("METAAPI_TOKEN", "")
_ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID", "")


def _set_last_error(code: int, msg: str):
    global _last_error
    _last_error = (code, msg)


def last_error() -> tuple:
    return _last_error


# ─────────────────────────────────────────────────────────────────────────────
#  Conexión / Inicialización
# ─────────────────────────────────────────────────────────────────────────────

async def _conectar_async():
    global _api, _connection, _connected
    from metaapi_cloud_sdk import MetaApi
    _api = MetaApi(_TOKEN)
    account = await _api.metatrader_account.get_account(_ACCOUNT_ID)
    _connection = account.get_rpc_connection()
    await _connection.connect()
    await _connection.wait_synchronized({'timeoutInSeconds': 60})
    _connected = True
    print("[MetaAPI-Shim] Conectado y sincronizado con MetaAPI Cloud.")


def initialize(login=None, password=None, server=None) -> bool:
    """Equivalente a mt5.initialize() — conecta con MetaAPI Cloud."""
    global _connected
    if _connected:
        return True
    print("[MetaAPI-Shim] Conectando a MetaAPI Cloud...")
    _run(_conectar_async(), timeout=90)
    return _connected


def shutdown():
    """Equivalente a mt5.shutdown()."""
    global _connected
    _connected = False
    print("[MetaAPI-Shim] Conexión cerrada.")


def terminal_info():
    """Retorna info de terminal (simulada para compatibilidad)."""
    if not _connected:
        return None
    return SimpleNamespace(
        name="MetaAPI Cloud Bridge",
        build=1000,
        connected=True,
        connected_to_server=True,
        path="cloud",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Información de Símbolo
# ─────────────────────────────────────────────────────────────────────────────

_symbol_specs_cache: dict = {}
_symbol_specs_ttl:   dict = {}
_SPEC_CACHE_TTL = 300  # 5 minutos


async def _get_spec_async(symbol: str):
    return await _connection.get_symbol_specification(symbol)


def symbol_info(symbol: str):
    """Retorna información del símbolo (specs del broker)."""
    if not _connected:
        return None
    try:
        now = time.time()
        if symbol not in _symbol_specs_cache or now - _symbol_specs_ttl.get(symbol, 0) > _SPEC_CACHE_TTL:
            spec = _run(_get_spec_async(symbol))
            if spec:
                _symbol_specs_cache[symbol] = spec
                _symbol_specs_ttl[symbol] = now
        spec = _symbol_specs_cache.get(symbol)
        if not spec:
            return None
        return SimpleNamespace(
            symbol=symbol,
            digits=int(spec.get('digits', 5)),
            trade_mode=SYMBOL_TRADE_MODE_FULL,  # Siempre operable en MetaAPI
            filling_mode=3,                     # Soporta FOK e IOC
            spread=int(spec.get('spread', 0)),
            point=float(spec.get('point', 0.00001)),
            contract_size=float(spec.get('contractSize', 100000)),
            volume_min=float(spec.get('minVolume', 0.01)),
            volume_max=float(spec.get('maxVolume', 100.0)),
            volume_step=float(spec.get('volumeStep', 0.01)),
        )
    except Exception as e:
        _set_last_error(1, str(e))
        return None


async def _get_price_async(symbol: str):
    return await _connection.get_symbol_price(symbol)


def symbol_info_tick(symbol: str):
    """Retorna bid/ask actual del símbolo."""
    if not _connected:
        return None
    try:
        price = _run(_get_price_async(symbol))
        if not price:
            return None
        bid = float(price.get('bid', 0.0))
        ask = float(price.get('ask', 0.0))
        return SimpleNamespace(
            bid=bid,
            ask=ask,
            time=datetime.now(timezone.utc),
            last=float(price.get('last', (bid + ask) / 2.0)),
            volume=0,
            spread=round(ask - bid, 5),
        )
    except Exception as e:
        _set_last_error(1, str(e))
        return None


def symbol_select(symbol: str, enable: bool = True) -> bool:
    """En MetaAPI todos los símbolos están siempre disponibles."""
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Datos de Mercado (Velas, Ticks, Order Book)
# ─────────────────────────────────────────────────────────────────────────────

async def _get_candles_async(symbol: str, tf_str: str, start_time: datetime, count: int):
    return await _connection.get_historical_candles(symbol, tf_str, start_time, count)


def copy_rates_from_pos(symbol: str, timeframe: int, from_pos: int, count: int):
    """
    Equivalente a mt5.copy_rates_from_pos().
    Retorna lista de dicts compatible con pd.DataFrame().
    """
    if not _connected:
        return None
    try:
        tf_str = _TF_MAP.get(timeframe, '1m')
        total = count + from_pos
        start_time = datetime.now(timezone.utc)
        candles = _run(_get_candles_async(symbol, tf_str, start_time, total), timeout=30)
        if not candles:
            return None
        # Descartar las from_pos velas más recientes (simula el offset)
        if from_pos > 0 and len(candles) > from_pos:
            candles = candles[:-from_pos]
        result = []
        for c in candles:
            t = c.get('time', datetime.now(timezone.utc))
            ts = int(t.timestamp()) if hasattr(t, 'timestamp') else int(t)
            result.append({
                'time':        ts,
                'open':        float(c.get('open',  0)),
                'high':        float(c.get('high',  0)),
                'low':         float(c.get('low',   0)),
                'close':       float(c.get('close', 0)),
                'tick_volume': int(c.get('tickVolume', 0)),
                'spread':      int(c.get('spread', 0)),
                'real_volume': int(c.get('volume', 0)),
            })
        return result if result else None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


async def _get_ticks_async(symbol: str, from_date: datetime, count: int):
    try:
        return await _connection.get_historical_ticks(symbol, from_date, count)
    except Exception:
        return []


def copy_ticks_from(symbol: str, from_date, count: int, flags: int):
    """Equivalente a mt5.copy_ticks_from(). Retorna lista de dicts."""
    if not _connected:
        return None
    try:
        ticks = _run(_get_ticks_async(symbol, from_date, count), timeout=30)
        if not ticks:
            return None
        result = []
        for t in ticks:
            ts_raw = t.get('time', datetime.now(timezone.utc))
            ts = int(ts_raw.timestamp()) if hasattr(ts_raw, 'timestamp') else int(ts_raw)
            result.append({
                'time':   ts,
                'bid':    float(t.get('bid', 0)),
                'ask':    float(t.get('ask', 0)),
                'last':   float(t.get('last', 0)),
                'volume': float(t.get('volume', 0)),
                'flags':  0,
            })
        return result if result else None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


async def _get_book_async(symbol: str):
    return await _connection.get_order_book(symbol)


def market_book_get(symbol: str):
    """Equivalente a mt5.market_book_get(). Retorna tuple de entradas."""
    if not _connected:
        return None
    try:
        book = _run(_get_book_async(symbol))
        if not book:
            return None
        entries = []
        for bid in book.get('bids', []):
            entries.append(SimpleNamespace(
                type=BOOK_TYPE_BUY,
                price=float(bid.get('price', 0)),
                volume=float(bid.get('volume', 0)),
            ))
        for ask in book.get('asks', []):
            entries.append(SimpleNamespace(
                type=BOOK_TYPE_SELL,
                price=float(ask.get('price', 0)),
                volume=float(ask.get('volume', 0)),
            ))
        return tuple(entries) if entries else None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Cuenta y Posiciones
# ─────────────────────────────────────────────────────────────────────────────

async def _get_account_info_async():
    return await _connection.get_account_information()


def account_info():
    """Equivalente a mt5.account_info()."""
    if not _connected:
        return None
    try:
        info = _run(_get_account_info_async())
        if not info:
            return None
        return SimpleNamespace(
            balance=float(info.get('balance', 0)),
            equity=float(info.get('equity', 0)),
            profit=float(info.get('profit', 0)),
            margin=float(info.get('margin', 0)),
            margin_free=float(info.get('freeMargin', 0)),
            margin_level=float(info.get('marginLevel', 0)),
            currency=info.get('currency', 'USD'),
            leverage=int(info.get('leverage', 100)),
            name=info.get('name', ''),
            server=info.get('broker', ''),
            login=0,
        )
    except Exception as e:
        _set_last_error(1, str(e))
        return None


class _Position:
    """Objeto posición compatible con MT5 TradePosition."""
    def __init__(self, data: dict):
        pos_id = str(data.get('id', '0'))
        try:
            self.ticket = int(pos_id)
        except (ValueError, TypeError):
            # UUID o string no numérico → hash estable
            self.ticket = abs(hash(pos_id)) % (10 ** 9)
        self._metaapi_id = pos_id
        self.symbol      = data.get('symbol', '')
        self.type        = ORDER_TYPE_BUY if data.get('type') == 'POSITION_TYPE_BUY' else ORDER_TYPE_SELL
        self.volume      = float(data.get('volume', 0))
        self.price_open  = float(data.get('openPrice', 0))
        self.price_current = float(data.get('currentPrice', data.get('openPrice', 0)))
        self.profit      = float(data.get('profit', 0))
        self.sl          = float(data.get('stopLoss') or 0)
        self.tp          = float(data.get('takeProfit') or 0)
        self.magic       = int(data.get('magic', 0))
        self.comment     = data.get('comment', '')
        self.time        = int(datetime.now(timezone.utc).timestamp())


async def _get_all_positions_async():
    return await _connection.get_positions()


async def _get_position_by_ticket_async(ticket: int):
    try:
        pos = await _connection.get_position(str(ticket))
        return [pos] if pos else []
    except Exception:
        # Fallback: filtrar de todas las posiciones
        all_pos = await _connection.get_positions()
        return [p for p in all_pos if str(p.get('id', '')) == str(ticket)]


async def _get_positions_by_symbol_async(symbol: str):
    all_pos = await _connection.get_positions()
    return [p for p in all_pos if p.get('symbol') == symbol]


def positions_get(symbol: str = None, ticket: int = None):
    """
    Equivalente a mt5.positions_get().
    Retorna tuple de objetos _Position compatibles con MT5.
    """
    if not _connected:
        return ()
    try:
        if ticket is not None:
            data = _run(_get_position_by_ticket_async(ticket))
        elif symbol is not None:
            data = _run(_get_positions_by_symbol_async(symbol))
        else:
            data = _run(_get_all_positions_async())
        if not data:
            return ()
        return tuple(_Position(p) for p in data)
    except Exception as e:
        _set_last_error(1, str(e))
        return ()


def positions_total() -> int:
    return len(positions_get())


# ─────────────────────────────────────────────────────────────────────────────
#  Envío de Órdenes
# ─────────────────────────────────────────────────────────────────────────────

async def _send_deal_async(request: dict):
    """Ejecuta una orden de mercado nueva o cierre de posición."""
    symbol   = request.get('symbol')
    volume   = float(request.get('volume', 0.01))
    sl       = request.get('sl') or None
    tp       = request.get('tp') or None
    comment  = request.get('comment', 'AurumBot')
    slippage = int(request.get('deviation', 10))
    magic    = str(request.get('magic', 0))
    position_ticket = request.get('position')
    order_type      = request.get('type')

    options = {'comment': comment, 'clientId': magic, 'slippage': slippage}

    if position_ticket is not None:
        # Cierre de posición existente
        result = await _connection.close_position(str(position_ticket), options)
    elif order_type == ORDER_TYPE_BUY:
        result = await _connection.create_market_buy_order(symbol, volume, sl, tp, options)
    else:
        result = await _connection.create_market_sell_order(symbol, volume, sl, tp, options)
    return result


async def _send_sltp_async(request: dict):
    """Modifica SL/TP de una posición existente."""
    position_ticket = str(request.get('position', ''))
    sl = request.get('sl') or None
    tp = request.get('tp') or None
    await _connection.modify_position(position_ticket, sl, tp)


def order_send(request: dict):
    """
    Equivalente a mt5.order_send().
    Retorna objeto con .retcode y .order (ticket).
    """
    if not _connected:
        _set_last_error(6, "No conectado a MetaAPI")
        return None
    try:
        action = request.get('action')

        if action == TRADE_ACTION_SLTP:
            _run(_send_sltp_async(request))
            return SimpleNamespace(
                retcode=TRADE_RETCODE_DONE,
                order=int(request.get('position', 0)),
                comment="",
            )

        if action == TRADE_ACTION_DEAL:
            result = _run(_send_deal_async(request))
            if result is None:
                return SimpleNamespace(retcode=10004, order=0, comment="MetaAPI error")

            # El positionId de MetaAPI → ticket MT5
            order_id = result.get('positionId') or result.get('orderId') or '0'
            try:
                ticket = int(order_id)
            except (ValueError, TypeError):
                ticket = abs(hash(str(order_id))) % (10 ** 9)

            return SimpleNamespace(
                retcode=TRADE_RETCODE_DONE,
                order=ticket,
                comment="",
            )

        _set_last_error(10006, f"Acción desconocida: {action}")
        return None

    except Exception as e:
        _set_last_error(10004, str(e))
        return SimpleNamespace(retcode=10004, order=0, comment=str(e))
