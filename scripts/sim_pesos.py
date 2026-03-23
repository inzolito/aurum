# -*- coding: utf-8 -*-
import psycopg2, json

conn = psycopg2.connect(host='localhost',dbname='aurum_db',user='aurum_admin',password='AurumProyect1milion')
cur = conn.cursor()
cur.execute("""
    SELECT a.simbolo, a.categoria, ro.tipo_orden,
           ro.pnl_usd, ro.resultado_final, ro.tiempo_entrada,
           ro.justificacion_entrada
    FROM registro_operaciones ro
    JOIN activos a ON a.id = ro.activo_id
    WHERE ro.tiempo_entrada >= '2026-03-18'
      AND ro.resultado_final IS NOT NULL
      AND ro.justificacion_entrada IS NOT NULL
    ORDER BY ro.tiempo_entrada ASC
""")
rows = cur.fetchall()

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
    if trend == 0 and nlp == 0 and sniper == 0:
        continue
    trades.append({
        'simbolo': r[0], 'cat': r[1], 'dir': r[2],
        'pnl': float(r[3] or 0), 'resultado': r[4],
        'fecha': r[5].strftime('%m-%d %H:%M'),
        'trend': trend, 'nlp': nlp, 'sniper': sniper, 'cspx': cspx,
    })

print("Trades con datos: {}".format(len(trades)))
print()

configs = [
    {'nombre': 'ACTUAL      ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.45},
    {'nombre': 'CAP_030     ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.30,'umbral':0.45},
    {'nombre': 'CROSS_015   ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.15,'cap':None,'umbral':0.45},
    {'nombre': 'CROSS_020   ', 'wT':0.45,'wN':0.30,'wS':0.20,'wC':0.20,'cap':None,'umbral':0.45},
    {'nombre': 'CROSS_025   ', 'wT':0.40,'wN':0.30,'wS':0.20,'wC':0.25,'cap':None,'umbral':0.45},
    {'nombre': 'CROSS_030   ', 'wT':0.40,'wN':0.30,'wS':0.15,'wC':0.30,'cap':None,'umbral':0.45},
    {'nombre': 'UMBRAL_050  ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.50},
    {'nombre': 'UMBRAL_055  ', 'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'cap':0.15,'umbral':0.55},
    {'nombre': 'BALANCED    ', 'wT':0.40,'wN':0.35,'wS':0.15,'wC':0.20,'cap':None,'umbral':0.48},
    {'nombre': 'CONSERVATIVE', 'wT':0.35,'wN':0.35,'wS':0.15,'wC':0.25,'cap':None,'umbral':0.50},
]

def simular(trades, cfg, dia=None):
    entran = ganados = perdidos = 0
    pnl_total = 0
    bm = bb = 0
    for t in trades:
        if dia and not t['fecha'].startswith(dia):
            continue
        if cfg['cap'] is not None:
            adj = max(-cfg['cap'], min(cfg['cap'], t['cspx'] * 0.10))
            vrd = t['trend']*cfg['wT'] + t['nlp']*cfg['wN'] + t['sniper']*cfg['wS'] + adj
        else:
            vrd = t['trend']*cfg['wT'] + t['nlp']*cfg['wN'] + t['sniper']*cfg['wS'] + t['cspx']*cfg['wC']

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

print("{:<13} {:<8} {:>5} {:>4} {:>4} {:>6} {:>8} {:>7} {:>7}".format(
    'Config','Dia','Entra','Won','Lost','WR%','PnL','BlkMal','BlkBue'))
print('-'*75)

dias = [('Mar-18','03-18'), ('Mar-19','03-19'), ('Mar-20','03-20'), ('TOTAL',None)]
for cfg in configs:
    for dnom, dfil in dias:
        e,g,p,pnl,bm,bb,wr = simular(trades, cfg, dfil)
        print("{} {:<8} {:>5} {:>4} {:>4} {:>6}% {:>8} {:>7} {:>7}".format(
            cfg['nombre'], dnom, e, g, p, wr, pnl, bm, bb))
    print()
