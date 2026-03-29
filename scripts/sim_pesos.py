# -*- coding: utf-8 -*-
import psycopg2, json
from itertools import product

conn = psycopg2.connect(host='localhost',dbname='aurum_db',user='aurum_admin',password='AurumProyect1milion')
cur = conn.cursor()

# Semana completa: lunes Mar-16 a viernes Mar-21
cur.execute("""
    SELECT a.simbolo, a.categoria, ro.tipo_orden,
           ro.pnl_usd, ro.resultado_final, ro.tiempo_entrada,
           ro.justificacion_entrada
    FROM registro_operaciones ro
    JOIN activos a ON a.id = ro.activo_id
    WHERE ro.tiempo_entrada >= '2026-03-16'
      AND ro.resultado_final IS NOT NULL
      AND ro.justificacion_entrada IS NOT NULL
    ORDER BY ro.tiempo_entrada ASC
""")
rows = cur.fetchall()
cur.close()
conn.close()

trades = []
for r in rows:
    j = {}
    try: j = json.loads(r[6])
    except: continue
    v = j.get('votos', {})
    cr = j.get('cross', {})
    trend  = v.get('trend', 0)
    nlp    = v.get('nlp', 0)
    sniper = v.get('sniper', 0)
    cspx   = cr.get('spx', 0)
    hora   = int(r[5].strftime('%H'))
    if trend == 0 and nlp == 0 and sniper == 0:
        continue
    trades.append({
        'simbolo': r[0], 'cat': r[1], 'dir': r[2],
        'pnl': float(r[3] or 0), 'resultado': r[4],
        'fecha': r[5].strftime('%m-%d'), 'hora': hora,
        'trend': trend, 'nlp': nlp, 'sniper': sniper, 'cspx': cspx,
    })

print("Trades con datos: {}  |  Semana: Mar-16 a Mar-21".format(len(trades)))
print()

# ---------- dias disponibles ----------
dias_set = sorted(set(t['fecha'] for t in trades))
print("Dias con datos: {}".format(', '.join(dias_set)))
print()

# ---------- funcion de simulacion ----------
def simular(trades, cfg, cat_filter=None):
    entran = ganados = perdidos = 0
    pnl_total = 0
    bm = bb = 0
    for t in trades:
        if cat_filter and t['cat'] != cat_filter:
            continue
        # Asia dead-cat-bounce filter (opcional)
        trend_eff = t['trend']
        if cfg.get('asia_filter') and (0 <= t['hora'] <= 8) and trend_eff >= 0.7 and t['cspx'] < -0.8:
            trend_eff = trend_eff * cfg.get('asia_factor', 0.35)

        if cfg.get('cap') is not None:
            adj = max(-cfg['cap'], min(cfg['cap'], t['cspx'] * 0.10))
            vrd = trend_eff*cfg['wT'] + t['nlp']*cfg['wN'] + t['sniper']*cfg['wS'] + adj
        else:
            vrd = trend_eff*cfg['wT'] + t['nlp']*cfg['wN'] + t['sniper']*cfg['wS'] + t['cspx']*cfg['wC']

        entra = abs(vrd) >= cfg['umbral']
        bueno = t['resultado'] == 'GANADO'
        if entra:
            entran += 1
            pnl_total += t['pnl']
            if bueno: ganados += 1
            else: perdidos += 1
        else:
            if bueno: bb += 1
            else: bm += 1
    wr = round(ganados/entran*100,1) if entran > 0 else 0
    return entran, ganados, perdidos, round(pnl_total,2), bm, bb, wr

# ---------- Seccion 1: configs manuales por dia ----------
configs_manual = [
    {'nombre': 'ACTUAL      ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.45},
    {'nombre': 'CROSS_020   ', 'wT':0.45,'wN':0.30,'wS':0.20,'wC':0.20,'cap':None,'umbral':0.45},
    {'nombre': 'CROSS_025   ', 'wT':0.40,'wN':0.30,'wS':0.20,'wC':0.25,'cap':None,'umbral':0.45},
    {'nombre': 'CROSS_030   ', 'wT':0.40,'wN':0.30,'wS':0.15,'wC':0.30,'cap':None,'umbral':0.45},
    {'nombre': 'UMBRAL_050  ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.50},
    {'nombre': 'UMBRAL_055  ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.55},
    {'nombre': 'UMBRAL_060  ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.60},
    {'nombre': 'NLP_HEAVY   ', 'wT':0.30,'wN':0.50,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.50},
    {'nombre': 'ASIA+CROSS  ', 'wT':0.45,'wN':0.30,'wS':0.20,'wC':0.20,'cap':None,'umbral':0.45,'asia_filter':True,'asia_factor':0.35},
    {'nombre': 'ASIA+UMB050 ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.50,'asia_filter':True,'asia_factor':0.35},
    {'nombre': 'NLP+CROSS   ', 'wT':0.35,'wN':0.40,'wS':0.15,'wC':0.25,'cap':None,'umbral':0.50},
    {'nombre': 'NLP+CROSS+AS', 'wT':0.35,'wN':0.40,'wS':0.15,'wC':0.25,'cap':None,'umbral':0.50,'asia_filter':True,'asia_factor':0.35},
]

dias = [(d, d) for d in dias_set] + [('SEMANA', None)]
print("=" * 85)
print("PARTE 1 — configs manuales (todos los activos)")
print("=" * 85)
print("{:<14} {:<8} {:>5} {:>4} {:>4} {:>6} {:>8} {:>7} {:>7}".format(
    'Config','Dia','Entra','Won','Lost','WR%','PnL','BlkMal','BlkBue'))
print('-' * 85)

for cfg in configs_manual:
    for dnom, dfil in dias:
        t_fil = [t for t in trades if (not dfil or t['fecha'] == dfil)]
        e,g,p,pnl,bm,bb,wr = simular(t_fil, cfg)
        marker = ' <--' if (dnom == 'SEMANA' and pnl > 0) else ''
        print("{:<14} {:<8} {:>5} {:>4} {:>4} {:>6}% {:>8}{}".format(
            cfg['nombre'], dnom, e, g, p, wr, pnl, marker))
    print()

# ---------- Seccion 2: grid search automatico ----------
print()
print("=" * 85)
print("PARTE 2 — grid search (top 20 configs rentables en la semana)")
print("=" * 85)

resultados_grid = []
# Grid: wT, wN, wS, wC, umbral — normalizados
for wT in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
    for wN in [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
        for wC in [0.00, 0.10, 0.15, 0.20, 0.25, 0.30]:
            for umbral in [0.45, 0.50, 0.55, 0.60]:
                # wS = resto, normalizar para que wT+wN+wC+wS ~ libre (no normalizamos, son pesos directos)
                wS = max(0, round(1.0 - wT - wN - wC, 2))
                if wS > 0.35: continue
                for asia in [False, True]:
                    cfg = {'wT':wT,'wN':wN,'wS':wS,'wC':wC,'cap':None,'umbral':umbral,
                           'asia_filter':asia,'asia_factor':0.35}
                    e,g,p,pnl,bm,bb,wr = simular(trades, cfg)
                    if e >= 5:  # minimo 5 trades para ser estadisticamente relevante
                        resultados_grid.append((pnl, wr, e, g, p, bm, bb, wT, wN, wS, wC, umbral, asia))

resultados_grid.sort(reverse=True)  # ordenar por PnL descendente

print("{:<6} {:<6} {:<5} {:<4} {:<4} {:<6} {:<6} {:<6} {:<6} {:<6} {:<5} {:<5}".format(
    'wT','wN','wS','wC','UMB','Entra','Won','Lost','WR%','PnL','Asia','BlkMal'))
print('-' * 85)

for row in resultados_grid[:20]:
    pnl,wr,e,g,p,bm,bb,wT,wN,wS,wC,umb,asia = row
    print("{:<6} {:<6} {:<5} {:<4} {:<4} {:<6} {:<4} {:<4} {:>5}% {:>8} {:<5} {:<5}".format(
        wT, wN, wS, wC, umb, e, g, p, wr, pnl, 'SI' if asia else 'NO', bm))

# ---------- Seccion 3: mejor config por categoria ----------
print()
print("=" * 85)
print("PARTE 3 — mejor config por CATEGORIA (top 5 cada una)")
print("=" * 85)

categorias = sorted(set(t['cat'] for t in trades))
for cat in categorias:
    trades_cat = [t for t in trades if t['cat'] == cat]
    res_cat = []
    for row in resultados_grid:
        pnl,wr,e,g,p,bm,bb,wT,wN,wS,wC,umb,asia = row
        cfg = {'wT':wT,'wN':wN,'wS':wS,'wC':wC,'cap':None,'umbral':umb,'asia_filter':asia,'asia_factor':0.35}
        ec,gc,pc,pnlc,bmc,bbc,wrc = simular(trades_cat, cfg)
        if ec >= 3:
            res_cat.append((pnlc, wrc, ec, gc, pc, wT, wN, wS, wC, umb, asia))
    res_cat.sort(reverse=True)
    n_total = len(trades_cat)
    n_ganados = sum(1 for t in trades_cat if t['resultado'] == 'GANADO')
    print("\n{} ({} trades, {} ganados en bruto):".format(cat, n_total, n_ganados))
    print("  {:<6} {:<6} {:<5} {:<4} {:<4} {:<6} {:<4} {:<4} {:>5}% {:>8} {:<5}".format(
        'wT','wN','wS','wC','UMB','Entra','Won','Lost','WR%','PnL','Asia'))
    for row in res_cat[:5]:
        pnlc,wrc,ec,gc,pc,wT,wN,wS,wC,umb,asia = row
        print("  {:<6} {:<6} {:<5} {:<4} {:<4} {:<6} {:<4} {:<4} {:>5}% {:>8} {:<5}".format(
            wT, wN, wS, wC, umb, ec, gc, pc, wrc, pnlc, 'SI' if asia else 'NO'))
