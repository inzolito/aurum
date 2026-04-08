import psycopg2
import os
from datetime import datetime, timedelta

try:
    conn = psycopg2.connect(
        host='localhost',
        database='aurum_db',
        user='aurum_admin',
        password='AurumProyect1milion'
    )
    cur = conn.cursor()
    
    print('--- DESGLOSE DIARIO DE NOTICIAS (Últimos 7 días) ---')
    print('Fecha      | Relevantes | Descartadas | Totales')
    print('-----------|------------|-------------|---------')
    
    cur.execute("""
        SELECT (published_at AT TIME ZONE 'UTC')::date as fecha, 
               COUNT(*) FILTER (WHERE content_summary LIKE '%Impacto:%') as relevantes,
               COUNT(*) FILTER (WHERE content_summary LIKE '%Descargada%') as descartadas,
               COUNT(*) as totales
        FROM raw_news_feed
        WHERE published_at >= (NOW() - INTERVAL '8 days')
        GROUP BY 1 
        ORDER BY 1 DESC;
    """)
    rows = cur.fetchall()
    
    for row in rows:
        fecha, rel, desc, tot = row
        print(f'{fecha} | {rel:>10} | {desc:>11} | {tot:>7}')
            
    cur.close()
    conn.close()
except Exception as e:
    print(f'ERROR: {e}')
