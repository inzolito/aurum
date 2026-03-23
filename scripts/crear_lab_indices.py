# -*- coding: utf-8 -*-
# Crea Lab Indices con la mejor config encontrada en el grid search
# Mejor config: wT=0.25 wN=0.15 wS=0.15 wC=0.45 umbral=0.70 asia_filter=True
# Resultado simulacion: 4 trades, 3W/1L, 75% WR (mejor encontrada en 9462 configs)

import psycopg2

conn = psycopg2.connect(host='localhost',dbname='aurum_db',user='aurum_admin',password='AurumProyect1milion')
cur = conn.cursor()

# 1. Crear el laboratorio
cur.execute("""
    INSERT INTO laboratorios (nombre, categoria, estado, capital_virtual, balance_virtual, version, notas)
    VALUES ('Lab Indices', 'INDICES', 'ACTIVO', 3000.00, 3000.00, 1,
            'Config optimizada via grid search Mar-18/19/20. wT=0.25 wN=0.15 wS=0.15 wC=0.45 umb=0.70 + filtro Asia dead-cat-bounce. 9462 configs probadas, mejor WR encontrada.')
    RETURNING id
""")
lab_id = cur.fetchone()[0]
print('Lab creado con id={}'.format(lab_id))

# 2. Asignar activos de indices (los que operan activamente)
# US30=11, US500=7, USTEC=9, GER40=20, UK100=21, JP225=17
activos_indices = [11, 7, 9, 20, 21, 17]
for activo_id in activos_indices:
    cur.execute("INSERT INTO lab_activos (lab_id, activo_id, estado) VALUES (%s, %s, 'ACTIVO')", (lab_id, activo_id))
print('Activos asignados: {}'.format(activos_indices))

# 3. Insertar parametros con la mejor config
parametros = [
    ('TENDENCIA.peso_voto',     '0.25',  'Peso del TrendWorker — reducido, evita seguir micro-rebotes en crash'),
    ('NLP.peso_voto',           '0.15',  'Peso del NLPWorker'),
    ('SNIPER.peso_voto',        '0.15',  'Peso del SniperWorker'),
    ('CROSS.peso_voto',         '0.45',  'Peso del Cross SPX como votante directo — principal filtro macro'),
    ('LAB.umbral_disparo',      '0.70',  'Umbral alto para filtrar entradas dudosas en indices'),
    ('LAB.riesgo_trade_pct',    '20.0',  'Capital virtual por trade (%)'),
    ('LAB.ratio_tp',            '2.5',   'Ratio TP/SL'),
    ('LAB.sl_atr_multiplier',   '4.0',   'Multiplicador ATR para SL'),
    ('LAB.spread_pips_default', '30',    'Spread simulado en pips'),
    ('LAB.usar_filtro_correlacion', '1', 'Activar filtro de correlacion entre activos'),
    ('LAB.asia_filter',         '1',     'Filtro Asia: si hora 0-8 UTC + Trend>=0.7 + SPX<-0.8, reducir Trend a 35%'),
]
for nombre, valor, desc in parametros:
    cur.execute("""
        INSERT INTO lab_parametros (lab_id, nombre_parametro, valor, descripcion)
        VALUES (%s, %s, %s, %s)
    """, (lab_id, nombre, valor, desc))
print('Parametros insertados: {}'.format(len(parametros)))

conn.commit()
cur.close(); conn.close()

print()
print('=== Lab Indices creado y habilitado ===')
print('ID: {}'.format(lab_id))
print('Estado: ACTIVO')
print('Config: wT=0.25 wN=0.15 wS=0.15 wC=0.45 umbral=0.70 + filtro Asia')
print('Activos: US30, US500, USTEC, GER40, UK100, JP225')
