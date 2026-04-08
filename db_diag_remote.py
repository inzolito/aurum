import psycopg2
import os

try:
    conn = psycopg2.connect(
        host='localhost',
        database='aurum_db',
        user='aurum_admin',
        password='AurumProyect1milion'
    )
    cur = conn.cursor()
    
    print('--- CONTEO DE FILAS ---')
    cur.execute("SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;")
    for row in cur.fetchall():
        print(f'{row[0]:<30} | {row[1]:>10}')
        
    print('\n--- INDICES EN TABLAS CRITICAS ---')
    tables = ['registro_operaciones', 'raw_news_feed', 'sentimiento_noticias', 'autopsias_perdidas']
    for table in tables:
        print(f'\nIndices en {table}:')
        cur.execute(f"SELECT indexname, indexdef FROM pg_indexes WHERE tablename = '{table}';")
        for row in cur.fetchall():
            print(f'  - {row[0]}')
            
    cur.close()
    conn.close()
except Exception as e:
    print(f'ERROR: {e}')
