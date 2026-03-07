import MetaTrader5 as mt5
if mt5.initialize():
    symbols = mt5.symbols_get()
    print("Potential Nasdaq symbols:")
    for s in symbols:
        if "TEC" in s.name or "NAS" in s.name or "NDX" in s.name or "100" in s.name:
            print(f"Name: {s.name}, Path: {s.path}, Description: {s.description}")
    
    print("\nPotential S&P 500 symbols:")
    for s in symbols:
        if "500" in s.name or "SPX" in s.name:
            print(f"Name: {s.name}, Path: {s.path}, Description: {s.description}")
            
    mt5.shutdown()
else:
    print("Failed to initialize MT5")
