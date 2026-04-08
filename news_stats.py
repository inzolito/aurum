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
    
    print('--- CONTEO DIARIO DE NOTICIAS (Últimos 7 días) ---')
    cur.execute("""
        SELECT (tiempo AT TIME ZONE 'UTC')::date as fecha, COUNT(*) 
        FROM sentimiento_noticias 
        WHERE tiempo >= (NOW() - INTERVAL '8 days')
        GROUP BY 1 
        ORDER BY 1 DESC;
    """)
    rows = cur.fetchall()
    
    total = 0
    for row in rows:
        print(f'{row[0]} | {row[1]} noticias')
        total += row[1]
        
    if rows:
        print(f'\nPromedio diario: {round(total/len(rows), 1)} noticias/día')
    else:
        print('No se encontraron noticias en el periodo.')
            
    cur.close()
    conn.close()
except Exception as e:
    print(f'ERROR: {e}')
