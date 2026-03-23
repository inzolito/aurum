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
    WHERE ro.tiempo_entrada >= '2026-03-16'
      AND ro.resultado_final IS NOT NULL
      AND ro.justificacion_entrada IS NOT NULL
      AND a.categoria = 'INDICES'
    ORDER BY ro.tiempo_entrada ASC
""")
rows = cur.fetchall()
cur.close(); conn.close()

trades = []
for r in rows:
    try: j = json.loads(r[6])
    except: continue
    v = j.get('votos',{}); cr = j.get('cross',{})
    trend=v.get('trend',0); nlp=v.get('nlp',0); sniper=v.get('sniper',0); cspx=cr.get('spx',0)
    if trend==0 and nlp==0 and sniper==0: continue
    hora = int(r[5].strftime('%H'))
    trades.append({'sim':r[0],'dir':r[2],'pnl':float(r[3] or 0),'res':r[4],
                   'fecha':r[5].strftime('%m-%d'),'hora':hora,
                   'trend':trend,'nlp':nlp,'sniper':sniper,'cspx':cspx})

print('Trades INDICES: {}'.format(len(trades)))
ganados_brutos = sum(1 for t in trades if t['res']=='GANADO')
pnl_bruto = sum(t['pnl'] for t in trades)
print('Ganados brutos: {} / {}  WR={:.1f}%'.format(ganados_brutos, len(trades), ganados_brutos/len(trades)*100 if trades else 0))
print('PnL bruto (si entraras todos): ${:.2f}'.format(pnl_bruto))
print()

# Mostrar todos los trades para entender la data
print('--- TRADES INDIVIDUALES ---')
for t in trades:
    print('{} {} {} T={} N={} S={} SPX={} -> {} ${}'.format(
        t['fecha'], t['hora'], t['sim'], t['trend'], t['nlp'], t['sniper'], t['cspx'], t['res'], t['pnl']))
print()

def sim(ts, cfg):
    e=g=p=0; pnl=0; bm=bb=0
    for t in ts:
        tr = t['trend']
        if cfg.get('asia') and 0<=t['hora']<=8 and tr>=0.7 and t['cspx']<-0.8:
            tr *= cfg.get('af',0.35)
        vrd = tr*cfg['wT'] + t['nlp']*cfg['wN'] + t['sniper']*cfg['wS'] + t['cspx']*cfg['wC']
        entra = abs(vrd) >= cfg['umb']
        bueno = t['res']=='GANADO'
        if entra:
            e+=1; pnl+=t['pnl']
            if bueno: g+=1
            else: p+=1
        else:
            if bueno: bb+=1
            else: bm+=1
    wr = round(g/e*100,1) if e>0 else 0
    return e,g,p,round(pnl,2),bm,bb,wr

print('--- GRID SEARCH (solo indices) ---')
print('{:<6}{:<6}{:<5}{:<6}{:<6} {:>5} {:>4} {:>4} {:>6} {:>9} {:<5}'.format(
    'wT','wN','wS','wC','UMB','Entra','Won','Lost','WR%','PnL','Asia'))
print('-'*78)

resultados = []
wT_opts = [i/100 for i in range(15,70,5)]
wN_opts = [i/100 for i in range(15,60,5)]
wC_opts = [i/100 for i in range(0,50,5)]
umb_opts = [0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70]

for wT in wT_opts:
    for wN in wN_opts:
        for wC in wC_opts:
            wS = round(max(0, 1.0-wT-wN-wC), 2)
            if wS > 0.45: continue
            if wT+wN+wC > 1.0: continue
            for umb in umb_opts:
                for asia in [False, True]:
                    cfg = {'wT':wT,'wN':wN,'wS':wS,'wC':wC,'umb':umb,'asia':asia,'af':0.35}
                    e,g,p,pnl,bm,bb,wr = sim(trades, cfg)
                    if e >= 2:
                        resultados.append((pnl,wr,e,g,p,bm,bb,wT,wN,wS,wC,umb,asia))

resultados.sort(reverse=True)

shown_profit = 0
for row in resultados[:40]:
    pnl,wr,e,g,p,bm,bb,wT,wN,wS,wC,umb,asia = row
    mark = ' <-- PROFIT' if pnl>0 else ''
    if pnl > 0: shown_profit += 1
    print('{:<6}{:<6}{:<5}{:<6}{:<6} {:>5} {:>4} {:>4} {:>6}% {:>9}{}'.format(
        wT,wN,wS,wC,umb,e,g,p,wr,pnl,mark))

print()
print('Configs con profit: {}/{}'.format(shown_profit, len(resultados)))

print()
print('--- ANALISIS POR DIA (actual vs mejor) ---')
dias = sorted(set(t['fecha'] for t in trades))
cfg_actual = {'wT':0.50,'wN':0.30,'wS':0.20,'wC':0.00,'umb':0.45,'asia':False}

if resultados:
    _,_,_,_,_,_,_,wT,wN,wS,wC,umb,asia = resultados[0]
    cfg_mejor = {'wT':wT,'wN':wN,'wS':wS,'wC':wC,'umb':umb,'asia':asia,'af':0.35}
    print('Mejor config: wT={} wN={} wS={} wC={} umb={} asia={}'.format(wT,wN,wS,wC,umb,asia))
    print()
    print('{:<10} {:>6} {:>4} {:>4} {:>6} {:>9}  |  {:>6} {:>4} {:>4} {:>6} {:>9}'.format(
        'Dia','E-act','W','L','WR%','PnL','E-mej','W','L','WR%','PnL'))
    print('-'*78)
    for d in dias:
        tf = [t for t in trades if t['fecha']==d]
        e1,g1,p1,pnl1,_,_,wr1 = sim(tf,cfg_actual)
        e2,g2,p2,pnl2,_,_,wr2 = sim(tf,cfg_mejor)
        print('{:<10} {:>6} {:>4} {:>4} {:>6}% {:>9}  |  {:>6} {:>4} {:>4} {:>6}% {:>9}'.format(
            d,e1,g1,p1,wr1,pnl1,e2,g2,p2,wr2,pnl2))
    # total
    e1,g1,p1,pnl1,_,_,wr1 = sim(trades,cfg_actual)
    e2,g2,p2,pnl2,_,_,wr2 = sim(trades,cfg_mejor)
    print('{:<10} {:>6} {:>4} {:>4} {:>6}% {:>9}  |  {:>6} {:>4} {:>4} {:>6}% {:>9}'.format(
        'TOTAL',e1,g1,p1,wr1,pnl1,e2,g2,p2,wr2,pnl2))
