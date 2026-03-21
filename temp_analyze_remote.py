import psycopg2, json, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('/opt/aurum/.env')

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        port=os.getenv('DB_PORT','5432'),
        dbname=os.getenv('DB_NAME','aurum_db'),
        user=os.getenv('DB_USER','aurum_admin'),
        password=os.getenv('DB_PASS','AurumProyect1milion')
    )
    c = conn.cursor(cursor_factory=RealDictCursor)

    print(":::POSICIONES ACTIVAS:::")
    c.execute("SELECT * FROM registro_operaciones ORDER BY id DESC LIMIT 10")
    ops = c.fetchall()
    for o in ops:
        print(json.dumps(o, default=str))

    print(":::VOTOS OBREROS:::")
    c.execute("SELECT * FROM registro_senales ORDER BY id DESC LIMIT 20")
    sns = c.fetchall()
    for s in sns:
        print(json.dumps(s, default=str))

    print(":::ANALISIS GEMINI:::")
    c.execute("SELECT * FROM cache_nlp_impactos ORDER BY id DESC LIMIT 10")
    nlps = c.fetchall()
    for n in nlps:
         print(json.dumps(n, default=str))

    c.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
