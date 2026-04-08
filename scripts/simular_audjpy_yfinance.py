import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import pytz

try:
    print("Obteniendo datos de mercado para AUDJPY=X...")
    df = yf.download(tickers='AUDJPY=X', period='1d', interval='1m')
    
    if df.empty:
        print("No se encontraron datos.")
        exit(1)
        
    print(f"Total velas obtenidas: {len(df)}")
    
    tz_target = pytz.timezone('America/Santiago')
    dt_target_scl = tz_target.localize(datetime(2026, 3, 31, 17, 38, 0))
    dt_target_utc = dt_target_scl.astimezone(pytz.utc)
    
    # yfinance devuelve index en timezone local o tz-aware dependiendo del broker, probemos convertir a UTC directo
    try:
        df.index = df.index.tz_convert('UTC')
    except TypeError:
        df.index = df.index.tz_localize('UTC')

    mask = (df.index >= dt_target_utc)
    df_after = df[mask].copy()
    
    if not df_after.empty:
        precio_entrada = float(df_after.iloc[0]['Open'].iloc[0])
        print(f'\\n[{df_after.index[0]}] Precio Entrada (Apertura 17:38 SCL): {precio_entrada:.3f}')
        
        atr_15m = 0.15 
        sl = precio_entrada - atr_15m * 1.5
        tp = precio_entrada + (precio_entrada - sl) * 2.0
        
        print(f'Riesgo Estimado: SL={sl:.3f}, TP={tp:.3f}\\n')
        
        hit_tp = False
        hit_sl = False
        
        for index, row in df_after.iterrows():
            low = float(row['Low'].iloc[0])
            high = float(row['High'].iloc[0])
            
            if low <= sl:
                print(f'[{index}] 🔴 STOP LOSS HIT @ {sl:.3f} (Vela Low: {low:.3f})')
                hit_sl = True
                break
            if high >= tp:
                print(f'[{index}] 🟢 TAKE PROFIT HIT @ {tp:.3f} (Vela High: {high:.3f})')
                hit_tp = True
                break
                
        if not hit_tp and not hit_sl:
            last_close = float(df_after.iloc[-1]['Close'].iloc[0])
            max_high = float(df_after['High'].max())
            min_low = float(df_after['Low'].min())
            print(f'Aun abierta. Precio actual: {last_close:.3f}. SL y TP no han sido alcanzados aún.')
            print(f'Max alcanzado: {max_high:.3f}. Min alcanzado: {min_low:.3f}')
    else:
        print('No se encontro data desde las 17:38 SCL.')
        print("Ultimas velas disponibles:")
        print(df.tail(5))
except Exception as e:
    print(f"Error general: {e}")
