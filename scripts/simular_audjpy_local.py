import sys
import pandas as pd
from datetime import datetime, timezone
import pytz

sys.path.append('c:\\www\\Aurum')
from config.mt5_connector import MT5Connector

mt5 = MT5Connector()
if not mt5.conectar():
    print('No se pudo conectar a MT5')
    sys.exit(1)

sb = 'AUDJPY_i'
velas = mt5.obtener_velas(sb, 150)

if velas is not None and not velas.empty:
    tz_target = pytz.timezone('America/Santiago')
    dt_target_scl = tz_target.localize(datetime(2026, 3, 31, 17, 38, 0))
    dt_target_utc = dt_target_scl.astimezone(pytz.utc).replace(tzinfo=None)
    
    df = velas.copy()
    mask = (df['time'] >= dt_target_utc)
    df_after = df[mask].copy()
    
    if not df_after.empty:
        precio_entrada = df_after.iloc[0]['open']
        print(f'[{df_after.iloc[0]["time"]}] Precio Entrada (Apertura 17:38 SCL): {precio_entrada:.3f}')
        
        atr_15m = 0.15 
        sl = precio_entrada - atr_15m * 1.5
        tp = precio_entrada + (precio_entrada - sl) * 2.0
        
        print(f'Riesgo Estimado: SL={sl:.3f}, TP={tp:.3f}')
        
        hit_tp = False
        hit_sl = False
        
        for index, row in df_after.iterrows():
            if row['low'] <= sl:
                print(f'[{row["time"]}] 🔴 STOP LOSS HIT @ {sl:.3f} (Vela Low: {row["low"]:.3f})')
                hit_sl = True
                break
            if row['high'] >= tp:
                print(f'[{row["time"]}] 🟢 TAKE PROFIT HIT @ {tp:.3f} (Vela High: {row["high"]:.3f})')
                hit_tp = True
                break
                
        if not hit_tp and not hit_sl:
            last_close = df_after.iloc[-1]['close']
            max_high = df_after['high'].max()
            min_low = df_after['low'].min()
            print(f'Aun abierta. Precio actual: {last_close:.3f}. SL y TP no han sido alcanzados aún.')
            print(f'Max alcanzado: {max_high:.3f}. Min alcanzado: {min_low:.3f}')
    else:
        print('No se encontro data desde las 17:38.')
else:
    print('No se obtuvieron velas')
mt5.desconectar()
