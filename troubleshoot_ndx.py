import MetaTrader5 as mt5
import pandas as pd
if mt5.initialize():
    symbol = "NDXUSD"
    mt5.symbol_select(symbol, True)
    
    info = mt5.symbol_info(symbol)
    if info:
        print(f"Name: {info.name}")
        print(f"Trade Mode: {info.trade_mode}")
        print(f"Visible: {info.visible}")
        print(f"Digits: {info.digits}")
        print(f"Session: {info.session_deals}")
        
    tick = mt5.symbol_info_tick(symbol)
    print(f"Tick: {tick}")
    
    # Try getting a few candles to see if data exists
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 10)
    if rates is not None:
        print(f"Got {len(rates)} candles.")
        print(pd.DataFrame(rates))
    else:
        print("Failed to get candles.")
        
    mt5.shutdown()
else:
    print("Failed to initialize MT5")
