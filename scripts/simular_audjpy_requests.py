import requests
import json
from datetime import datetime
import pytz

try:
    print("Obteniendo datos de mercado para AUDJPY=X desde Yahoo Finance API...")
    url = "https://query1.finance.yahoo.com/v8/finance/chart/AUDJPY=X?range=1d&interval=1m"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    data = response.json()
    
    result = data['chart']['result'][0]
    timestamps = result['timestamp']
    quotes = result['indicators']['quote'][0]
    
    opens = quotes['open']
    highs = quotes['high']
    lows = quotes['low']
    closes = quotes['close']
    
    tz_target = pytz.timezone('America/Santiago')
    dt_target_scl = tz_target.localize(datetime(2026, 3, 31, 17, 38, 0))
    dt_target_utc = dt_target_scl.astimezone(pytz.utc).timestamp()
    
    post_1738_data = []
    
    for i in range(len(timestamps)):
        if timestamps[i] >= dt_target_utc and opens[i] is not None:
            post_1738_data.append({
                'time': datetime.fromtimestamp(timestamps[i], tz=pytz.utc),
                'open': opens[i],
                'high': highs[i],
                'low': lows[i],
                'close': closes[i]
            })
            
    if not post_1738_data:
        print("No se encontró data desde las 17:38 SCL.")
        exit(1)
        
    precio_entrada = post_1738_data[0]['open']
    time_entrada = post_1738_data[0]['time'].astimezone(tz_target).strftime('%H:%M:%S')
    print(f'\\n[{time_entrada} SCL] Precio Entrada (Apertura 17:38 SCL): {precio_entrada:.3f}')
    
    atr_15m = 0.15 
    sl = precio_entrada - atr_15m * 1.5
    tp = precio_entrada + (precio_entrada - sl) * 2.0
    
    print(f'Riesgo Estimado: SL={sl:.3f}, TP={tp:.3f}\\n')
    
    hit_tp = False
    hit_sl = False
    
    for row in post_1738_data:
        low = row['low']
        high = row['high']
        t_str = row['time'].astimezone(tz_target).strftime('%H:%M:%S')
        
        if low <= sl:
            print(f'[{t_str} SCL] 🔴 STOP LOSS HIT @ {sl:.3f} (Vela Low: {low:.3f})')
            hit_sl = True
            break
        if high >= tp:
            print(f'[{t_str} SCL] 🟢 TAKE PROFIT HIT @ {tp:.3f} (Vela High: {high:.3f})')
            hit_tp = True
            break
            
    if not hit_tp and not hit_sl:
        last_close = post_1738_data[-1]['close']
        max_high = max(r['high'] for r in post_1738_data)
        min_low = min(r['low'] for r in post_1738_data)
        print(f'Aun abierta. Precio actual: {last_close:.3f}. SL y TP no han sido alcanzados aún.')
        print(f'Max alcanzado: {max_high:.3f}. Min alcanzado: {min_low:.3f}')

except Exception as e:
    print(f"Error general: {e}")
