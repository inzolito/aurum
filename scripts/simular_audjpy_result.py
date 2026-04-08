import sys, os
from datetime import datetime, timezone
import pytz
import pandas as pd
sys.path.append('/opt/aurum')
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector

db = DBConnector()
mt5 = MT5Connector()
if not db.conectar() or not mt5.conectar():
    print("Cannot connect.")
    exit(1)

sb = db.obtener_simbolo_broker('AUDJPY')
print('Simbolo broker:', sb)

# Calcular Riesgo Real usando RiskModule
from core.risk_module import RiskModule
risk = RiskModule(db, mt5)
lotes, sl, tp = risk.calcular_riesgo_completo(sb, 'COMPRA', 0.478)
print(f'\\nRiesgo Planificado: Lotes={lotes}, SL={sl:.4f}, TP={tp:.4f}\\n')

velas = mt5.obtener_velas(sb, 150)
if not velas.empty:
    # 17:38 Santiago -> 20:38 UTC target.
    tz_target = pytz.timezone('America/Santiago')
    dt_target_scl = tz_target.localize(datetime(2026, 3, 31, 17, 38, 0))
    dt_target_utc = dt_target_scl.astimezone(pytz.utc)
    
    # Encontrar vela de las 17:38 (asumiendo que df['time'] ya es datetime UTC)
    # df ya viene parseado en MT5Connector.
    df = velas.copy()
    
    # Mostar datos alrededor de las 20:38 UTC (17:38 SCL)
    mask = (df['time'] >= dt_target_utc)
    df_after = df[mask].copy()
    
    if not df_after.empty:
        precio_entrada = df_after.iloc[0]['open']
        print(f'[{df_after.iloc[0]["time"]}] Precio Entrada (Apertura 17:38 SCL): {precio_entrada:.3f}')
        
        # Simular SL/TP hit
        max_high = df_after['high'].max()
        min_low = df_after['low'].min()
        
        hit_tp = False
        hit_sl = False
        
        for index, row in df_after.iterrows():
            if row['low'] <= sl:
                print(f'\\n[{row["time"]}] 🔴 STOP LOSS HIT @ {sl:.3f} (Vela Low: {row["low"]:.3f})')
                hit_sl = True
                break
            if row['high'] >= tp:
                print(f'\\n[{row["time"]}] 🟢 TAKE PROFIT HIT @ {tp:.3f} (Vela High: {row["high"]:.3f})')
                hit_tp = True
                break
                
        if not hit_tp and not hit_sl:
            last_close = df_after.iloc[-1]['close']
            print(f'\\nAun abierta. Precio actual: {last_close:.3f}. SL y TP no han sido alcanzados aún.')
            
    else:
        print('No se encontró data desde las 17:38. Ajustar rango.')
        print(df.tail(10)[['time', 'open', 'high', 'low', 'close']])

mt5.desconectar()
db.desconectar()
