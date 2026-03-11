import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(r'c:\www\Aurum\.env')

def get_db_data():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS')
    )
    cur = conn.cursor()
    
    # 1. Active Assets
    cur.execute("SELECT simbolo, nombre, categoria, estado_operativo FROM activos ORDER BY simbolo;")
    activos = cur.fetchall()
    
    # 2. Parameters (Voting weights)
    cur.execute("SELECT nombre_parametro, valor FROM parametros_sistema WHERE nombre_parametro LIKE '%peso_voto' OR nombre_parametro = 'umbral_disparo';")
    params = cur.fetchall()
    
    # 3. Last 5 signals
    cur.execute("""
        SELECT s.tiempo, a.simbolo, s.voto_tendencia, s.voto_nlp, s.voto_order_flow, s.voto_final_ponderado, s.decision_gerente 
        FROM registro_senales s
        JOIN activos a ON s.activo_id = a.id
        ORDER BY s.tiempo DESC LIMIT 5;
    """)
    signals = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return activos, params, signals

try:
    activos, params, signals = get_db_data()
    
    print("--- ACTIVOS EN BASE DE DATOS ---")
    for a in activos:
        status = "[ACTIVE]" if a[3] == 'ACTIVO' else "[LIMIT]" if a[3] == 'SOLO_CIERRAR' else "[PAUSED]"
        print(f"{status} {a[0]} ({a[1]}) - {a[2]} [{a[3]}]")
        
    print("\n--- PESOS DE VOTACION (CONFIGURACION) ---")
    for p in params:
        print(f"PARAM {p[0]}: {p[1]}")
        
    print("\n--- ULTIMAS 5 SENALES (SISTEMA DE VOTACION) ---")
    for s in signals:
        print(f"TIME {s[0]} | {s[1]} | T:{s[2]} NLP:{s[3]} FLOW:{s[4]} | FINAL:{s[5]} | DECISION: {s[6]}")

except Exception as e:
    print(f"Error: {e}")
