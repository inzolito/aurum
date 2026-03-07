import MetaTrader5 as mt5
if mt5.initialize():
    symbol = "NDXUSD"
    selected = mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    print(f"Symbol: {symbol}")
    print(f"Selected: {selected}")
    print(f"Info: {info}")
    print(f"Tick: {tick}")
    mt5.shutdown()
else:
    print("Failed to initialize MT5")
