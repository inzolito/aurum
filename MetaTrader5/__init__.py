"""
MetaTrader5 Shim para Linux/Cloud — SDK v29
=============================================
Implementa la misma interfaz del módulo MetaTrader5 de Python pero
delega todas las operaciones a MetaAPI Cloud.

API correcta para metaapi-cloud-sdk v29:
  - Candles/Ticks    → _account.get_historical_candles / get_historical_ticks
  - Precios, Pos,
    Account info     → _connection._websocket_client.<method>(_account.id, ...)
  - Órdenes          → _connection.<method>(...)
"""

import os
import asyncio
import threading
import time
import concurrent.futures
from datetime import datetime, timezone
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
POSITION_TYPE_BUY = 0; POSITION_TYPE_SELL = 1
ORDER_FILLING_FOK = 0; ORDER_FILLING_IOC = 1; ORDER_FILLING_RETURN = 2

TRADE_ACTION_DEAL = 1; TRADE_ACTION_SLTP = 6
ORDER_TIME_GTC = 0;    TRADE_RETCODE_DONE = 10009

BOOK_TYPE_BUY  = 1;    BOOK_TYPE_SELL = 0
COPY_TICKS_ALL = 1;    COPY_TICKS_INFO = 2; COPY_TICKS_TRADE = 4

_TF_MAP = {
    1: '1m', 2: '2m', 3: '3m', 4: '4m', 5: '5m', 6: '6m',
    10: '10m', 12: '12m', 15: '15m', 20: '20m', 30: '30m',
    16385: '1h', 16386: '2h', 16387: '3h', 16388: '4h',
    16390: '6h', 16392: '8h', 16396: '12h',
    16408: '1d', 32769: '1w', 49153: '1mn',
}

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _g(obj, key, default=None):
    """Obtiene un valor de dict o de objeto con atributos."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ─────────────────────────────────────────────────────────────────────────────
#  Event Loop dedicado en hilo daemon
# ─────────────────────────────────────────────────────────────────────────────

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True, name="MetaAPILoop").start()


def _run(coro, timeout=30):
    """Ejecuta una coroutine async de forma síncrona."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    try:
        return future.result(timeout=timeout)
    except (concurrent.futures.TimeoutError, asyncio.TimeoutError):
        future.cancel()
        _set_last_error(1, "MetaAPI timeout")
        return None
    except Exception as e:
        future.cancel()
        detail = getattr(e, 'details', None)
        msg = str(e) + " | details: " + str(detail) if detail else str(e)
        _set_last_error(1, msg)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Estado global
# ─────────────────────────────────────────────────────────────────────────────

_api        = None
_account    = None   # MetatraderAccount — para candles/ticks e info de login
_connection = None   # RpcMetaApiConnectionInstance — para órdenes
_ws         = None   # _connection._websocket_client — para precios/posiciones
_account_id = None   # str — _account.id
_connected  = False
_last_error = (0, "Success")

_TOKEN      = os.getenv("METAAPI_TOKEN", "")
_ACCOUNT_ID = os.getenv("METAAPI_ACCOUNT_ID", "")


def _set_last_error(code, msg):
    global _last_error
    _last_error = (code, msg)


def last_error():
    return _last_error


# ─────────────────────────────────────────────────────────────────────────────
#  Conexión
# ─────────────────────────────────────────────────────────────────────────────

async def _conectar_async():
    global _api, _account, _connection, _ws, _account_id, _connected
    from metaapi_cloud_sdk import MetaApi
    _api = MetaApi(_TOKEN, opts={
        'requestTimeout': 10,
        'historicalMarketDataRequestTimeout': 10,
    })
    _account = await _api.metatrader_account_api.get_account(_ACCOUNT_ID)
    _connection = _account.get_rpc_connection()
    await _connection.connect()
    await _connection.wait_synchronized()
    _ws = _connection._websocket_client
    _account_id = _account.id
    _connected = True
    print("[MetaAPI-Shim] Conectado y sincronizado con MetaAPI Cloud.")


def initialize(login=None, password=None, server=None) -> bool:
    global _connected
    if _connected:
        return True
    print("[MetaAPI-Shim] Conectando a MetaAPI Cloud...")
    _run(_conectar_async(), timeout=90)
    return _connected


def shutdown():
    global _connected
    _connected = False
    print("[MetaAPI-Shim] Conexión cerrada.")


def terminal_info():
    if not _connected:
        return None
    return SimpleNamespace(name="MetaAPI Cloud Bridge", build=1000, connected=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Información de Símbolo
# ─────────────────────────────────────────────────────────────────────────────

_symbol_specs_cache = {}
_symbol_specs_ttl   = {}
_SPEC_TTL = 300


async def _get_spec_async(symbol):
    return await _ws.get_symbol_specification(_account_id, symbol)


def symbol_info(symbol):
    if not _connected:
        return None
    try:
        now = time.time()
        if symbol not in _symbol_specs_cache or now - _symbol_specs_ttl.get(symbol, 0) > _SPEC_TTL:
            print(f"[SHIM] spec_start {symbol}", flush=True)
            spec = _run(_get_spec_async(symbol))
            print(f"[SHIM] spec_end {symbol} got={'ok' if spec else 'none'}", flush=True)
            if spec:
                _symbol_specs_cache[symbol] = spec
                _symbol_specs_ttl[symbol] = now
        spec = _symbol_specs_cache.get(symbol)
        if not spec:
            return None
        return SimpleNamespace(
            symbol=symbol,
            digits=int(_g(spec, 'digits', 5)),
            trade_mode=SYMBOL_TRADE_MODE_FULL,
            filling_mode=3,
            spread=int(_g(spec, 'Spread', 0) or _g(spec, 'spread', 0)),
            point=float(_g(spec, 'points', 0) or _g(spec, 'point', 0)) or 10 ** (-int(_g(spec, 'digits', 5))),
            contract_size=float(_g(spec, 'contractSize', 100000)),
            volume_min=float(_g(spec, 'minVolume', 0.01)),
            volume_max=float(_g(spec, 'maxVolume', 100.0)),
            trade_stops_level=int(_g(spec, 'stopsLevel', 0) or 0),
            volume_step=float(_g(spec, 'volumeStep', 0.01)),
        )
    except Exception as e:
        _set_last_error(1, str(e))
        return None


async def _get_price_async(symbol):
    return await _ws.get_symbol_price(_account_id, symbol)


def symbol_info_tick(symbol):
    if not _connected:
        return None
    try:
        print(f"[SHIM] tick_start {symbol}", flush=True)
        price = _run(_get_price_async(symbol))
        print(f"[SHIM] tick_end {symbol} got={'ok' if price else 'none'}", flush=True)
        if not price:
            return None
        bid = float(_g(price, 'bid', 0.0))
        ask = float(_g(price, 'ask', 0.0))
        return SimpleNamespace(
            bid=bid, ask=ask,
            time=datetime.now(timezone.utc),
            last=float(_g(price, 'last', (bid + ask) / 2.0)),
            volume=0,
            spread=round(ask - bid, 5),
        )
    except Exception as e:
        _set_last_error(1, str(e))
        return None


def symbol_select(symbol, enable=True):
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Datos de Mercado
# ─────────────────────────────────────────────────────────────────────────────

async def _get_candles_async(symbol, tf_str, start_time, count):
    return await _account.get_historical_candles(symbol, tf_str, start_time, limit=count)


def copy_rates_from_pos(symbol, timeframe, from_pos, count):
    if not _connected:
        return None
    try:
        tf_str = _TF_MAP.get(timeframe, '1m')
        total = count + from_pos
        start_time = datetime.now(timezone.utc)
        _t0 = time.time()
        print(f"[SHIM] rates_start {symbol} {tf_str} n={total}", flush=True)
        candles = _run(_get_candles_async(symbol, tf_str, start_time, total), timeout=15)
        print(f"[SHIM] rates_end {symbol} {tf_str} got={len(candles) if candles else 0} in {time.time()-_t0:.1f}s", flush=True)
        if not candles:
            return None
        if from_pos > 0 and len(candles) > from_pos:
            candles = candles[:-from_pos]
        result = []
        for c in candles:
            t = _g(c, 'time', datetime.now(timezone.utc))
            ts = int(t.timestamp()) if hasattr(t, 'timestamp') else int(t)
            result.append({
                'time':        ts,
                'open':        float(_g(c, 'open',  0)),
                'high':        float(_g(c, 'high',  0)),
                'low':         float(_g(c, 'low',   0)),
                'close':       float(_g(c, 'close', 0)),
                'tick_volume': int(_g(c, 'tickVolume', 0)),
                'spread':      int(_g(c, 'spread', 0)),
                'real_volume': int(_g(c, 'volume', 0)),
            })
        return result if result else None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


async def _get_ticks_async(symbol, from_date, count):
    try:
        return await _account.get_historical_ticks(symbol, from_date, count)
    except Exception:
        return []


def copy_ticks_from(symbol, from_date, count, flags):
    if not _connected:
        return None
    try:
        _t0 = time.time()
        print(f"[SHIM] ticks_start {symbol}", flush=True)
        ticks = _run(_get_ticks_async(symbol, from_date, count), timeout=15)
        print(f"[SHIM] ticks_end {symbol} got={len(ticks) if ticks else 0} in {time.time()-_t0:.1f}s", flush=True)
        if not ticks:
            return None
        result = []
        for t in ticks:
            ts_raw = _g(t, 'time', datetime.now(timezone.utc))
            ts = int(ts_raw.timestamp()) if hasattr(ts_raw, 'timestamp') else int(ts_raw)
            result.append({
                'time': ts, 'bid': float(_g(t, 'bid', 0)),
                'ask': float(_g(t, 'ask', 0)), 'last': float(_g(t, 'last', 0)),
                'volume': float(_g(t, 'volume', 0)), 'flags': 0,
            })
        return result if result else None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


async def _get_book_async(symbol):
    try:
        return await _ws.get_order_book(_account_id, symbol)
    except Exception:
        return None


def market_book_get(symbol):
    if not _connected:
        return None
    try:
        book = _run(_get_book_async(symbol))
        if not book:
            return None
        entries = []
        bids = _g(book, 'bids', []) or []
        asks = _g(book, 'asks', []) or []
        for bid in bids:
            entries.append(SimpleNamespace(type=BOOK_TYPE_BUY,
                price=float(_g(bid, 'price', 0)), volume=float(_g(bid, 'volume', 0))))
        for ask in asks:
            entries.append(SimpleNamespace(type=BOOK_TYPE_SELL,
                price=float(_g(ask, 'price', 0)), volume=float(_g(ask, 'volume', 0))))
        return tuple(entries) if entries else None
    except Exception as e:
        _set_last_error(1, str(e))
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Cuenta y Posiciones
# ─────────────────────────────────────────────────────────────────────────────

async def _get_account_info_async():
    return await _ws.get_account_information(_account_id)


def account_info():
    if not _connected:
        return None
    try:
        info = _run(_get_account_info_async())
        if not info:
            return None
        # _account.login es el número de cuenta MT5 (string)
        mt5_login = 0
        try:
            mt5_login = int(_account.login) if _account and _account.login else 0
        except (ValueError, TypeError):
            mt5_login = int(os.getenv('MT5_LOGIN', '0'))
        return SimpleNamespace(
            balance=float(_g(info, 'balance', 0)),
            equity=float(_g(info, 'equity', 0)),
            profit=float(_g(info, 'profit', 0)),
            margin=float(_g(info, 'margin', 0)),
            margin_free=float(_g(info, 'freeMargin', 0)),
            margin_level=float(_g(info, 'marginLevel', 0)),
            currency=_g(info, 'currency', 'USD'),
            leverage=int(_g(info, 'leverage', 100)),
            login=mt5_login,
        )
    except Exception as e:
        _set_last_error(1, str(e))
        return None


class _Position:
    def __init__(self, data):
        pos_id = str(_g(data, 'id', '0'))
        try:
            self.ticket = int(pos_id)
        except (ValueError, TypeError):
            self.ticket = abs(hash(pos_id)) % (10 ** 9)
        self._metaapi_id = pos_id
        self.symbol      = _g(data, 'symbol', '')
        pos_type         = _g(data, 'type', '')
        self.type        = ORDER_TYPE_BUY if pos_type == 'POSITION_TYPE_BUY' else ORDER_TYPE_SELL
        self.volume      = float(_g(data, 'volume', 0))
        self.price_open  = float(_g(data, 'openPrice', 0))
        self.price_current = float(_g(data, 'currentPrice', _g(data, 'openPrice', 0)))
        self.profit      = float(_g(data, 'profit', 0))
        self.sl          = float(_g(data, 'stopLoss') or 0)
        self.tp          = float(_g(data, 'takeProfit') or 0)
        self.magic       = int(_g(data, 'magic', 0))
        self.comment     = _g(data, 'comment', '')
        self.time        = int(datetime.now(timezone.utc).timestamp())


async def _get_all_positions_async():
    return await _ws.get_positions(_account_id)


async def _get_position_by_ticket_async(ticket):
    try:
        pos = await _ws.get_position(_account_id, str(ticket))
        return [pos] if pos else []
    except Exception:
        all_pos = await _ws.get_positions(_account_id)
        if not all_pos:
            return []
        return [p for p in all_pos if str(_g(p, 'id', '')) == str(ticket)]


async def _get_positions_by_symbol_async(symbol):
    all_pos = await _ws.get_positions(_account_id)
    if not all_pos:
        return []
    return [p for p in all_pos if _g(p, 'symbol', '') == symbol]


def positions_get(symbol=None, ticket=None):
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


def positions_total():
    return len(positions_get())


# ─────────────────────────────────────────────────────────────────────────────
#  Envío de Órdenes
# ─────────────────────────────────────────────────────────────────────────────

async def _send_deal_async(request):
    symbol   = request.get('symbol')
    volume   = float(request.get('volume', 0.01))
    sl       = request.get('sl') or None
    tp       = request.get('tp') or None
    comment  = request.get('comment', 'AurumBot')
    slippage = int(request.get('deviation', 10))
    magic    = str(request.get('magic', 0))
    position_ticket = request.get('position')
    order_type      = request.get('type')

    options = {'comment': comment, 'slippage': slippage}

    if position_ticket is not None:
        result = await _connection.close_position(str(position_ticket), options)
    elif order_type == ORDER_TYPE_BUY:
        result = await _connection.create_market_buy_order(symbol, volume, sl, tp, options)
    else:
        result = await _connection.create_market_sell_order(symbol, volume, sl, tp, options)
    return result


async def _send_sltp_async(request):
    await _connection.modify_position(
        str(request.get('position', '')),
        request.get('sl') or None,
        request.get('tp') or None,
    )


def order_send(request):
    if not _connected:
        _set_last_error(6, "No conectado a MetaAPI")
        return None
    try:
        action = request.get('action')
        if action == TRADE_ACTION_SLTP:
            _run(_send_sltp_async(request))
            return SimpleNamespace(retcode=TRADE_RETCODE_DONE,
                                   order=int(request.get('position', 0)), comment="")
        if action == TRADE_ACTION_DEAL:
            result = _run(_send_deal_async(request))
            if result is None:
                err_msg = _last_error[1] if _last_error[0] != 0 else "MetaAPI error"
                return SimpleNamespace(retcode=10004, order=0, comment=err_msg)
            order_id = _g(result, 'positionId') or _g(result, 'orderId') or '0'
            try:
                ticket = int(order_id)
            except (ValueError, TypeError):
                ticket = abs(hash(str(order_id))) % (10 ** 9)
            return SimpleNamespace(retcode=TRADE_RETCODE_DONE, order=ticket, comment="")
        _set_last_error(10006, f"Acción desconocida: {action}")
        return None
    except Exception as e:
        _set_last_error(10004, str(e))
        return SimpleNamespace(retcode=10004, order=0, comment=str(e))
