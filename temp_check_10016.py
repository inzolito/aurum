import MetaTrader5 as mt5

def check_stops():
    if not mt5.initialize():
        print(f"Error MT5: {mt5.last_error()}")
        return

    symbols = ["EURGBP_i", "USDCHF_i"]
    for s in symbols:
        info = mt5.symbol_info(s)
        if info:
            print(f"[{s}]")
            print(f"  Digits: {info.digits}")
            print(f"  Point: {info.point:.5f}")
            print(f"  Spread: {info.spread} puntos")
            print(f"  Stop Level: {info.trade_stops_level} puntos")
            print(f"  Freeze Level: {info.trade_freeze_level} puntos")
            
            # Simulated ATR distance
            import pandas as pd
            rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M15, 0, 15)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['tr'] = df['high'] - df['low']
                atr = df['tr'].mean()
                dist_sl = atr * 1.5
                dist_pts = int(dist_sl / info.point)
                print(f"  ATR simulado M15: {atr:.5f}")
                print(f"  Distancia SL (1.5x ATR): {dist_sl:.5f} ({dist_pts} puntos)")
                if dist_pts < info.trade_stops_level:
                    print(f"  >>> ERROR: Distancia SL ({dist_pts}) < Stop Level ({info.trade_stops_level})")
                
                # Check MT5 execution rule - minimum distance is often greater of stoplevel or spread
                min_dist = max(info.trade_stops_level, info.spread) * info.point
                print(f"  Distancia Mínima Permitida: {min_dist:.5f}")
        else:
            print(f"Símbolo {s} no encontrado.")

    mt5.shutdown()

if __name__ == "__main__":
    check_stops()
