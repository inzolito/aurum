# -*- coding: utf-8 -*-
insertion = '''
# Historial de Deals
class _Deal:
    def __init__(self, data):
        self.ticket  = int(_g(data, "id", 0) or 0)
        self.order   = int(_g(data, "positionId", _g(data, "orderId", 0)) or 0)
        self.symbol  = _g(data, "symbol", "")
        self.type    = DEAL_TYPE_BUY if _g(data, "type", "") in ("DEAL_TYPE_BUY",) else DEAL_TYPE_SELL
        entry_raw    = _g(data, "entryType", "")
        if entry_raw == "DEAL_ENTRY_OUT":
            self.entry = DEAL_ENTRY_OUT
        elif entry_raw == "DEAL_ENTRY_INOUT":
            self.entry = DEAL_ENTRY_INOUT
        else:
            self.entry = DEAL_ENTRY_IN
        self.profit  = float(_g(data, "profit", 0) or 0)
        self.volume  = float(_g(data, "volume", 0) or 0)
        self.price   = float(_g(data, "price", 0) or 0)
        self.comment = _g(data, "comment", "")
        self.magic   = int(_g(data, "magic", 0) or 0)

async def _get_deals_async(from_date, to_date):
    try:
        result = await _connection.get_deals_by_time_range(from_date, to_date, 0, 1000)
        raw = result.get("deals", []) if isinstance(result, dict) else (result or [])
        return tuple(_Deal(d) for d in raw)
    except Exception as e:
        _set_last_error(1, "history_deals_get: " + str(e))
        return tuple()

def history_deals_get(date_from, date_to):
    if not _connected:
        return tuple()
    return _run(_get_deals_async(date_from, date_to)) or tuple()

'''

target = "# " + chr(0x2500)*77 + "\n#  Envio de Ordenes"

with open("/opt/aurum/MetaTrader5/__init__.py", "r", encoding="utf-8") as f:
    content = f.read()

if "history_deals_get" in content:
    print("Ya existe - nada que hacer")
else:
    # Buscar el bloque de Envio de Ordenes con los guiones especiales
    import re
    pattern = r'# \u2500{3,}\n#  Env.o de .rdenes'
    match = re.search(pattern, content)
    if match:
        pos = match.start()
        content = content[:pos] + insertion + content[pos:]
        with open("/opt/aurum/MetaTrader5/__init__.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("OK - insertado antes de Envio de Ordenes")
    else:
        # Fallback: insertar antes de 'async def _send_deal_async'
        fallback = "async def _send_deal_async"
        if fallback in content:
            pos = content.index(fallback)
            content = content[:pos] + insertion + content[pos:]
            with open("/opt/aurum/MetaTrader5/__init__.py", "w", encoding="utf-8") as f:
                f.write(content)
            print("OK - insertado (fallback)")
        else:
            print("ERROR - no se encontro punto de insercion")
