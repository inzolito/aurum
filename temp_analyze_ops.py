import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import json

load_dotenv('c:/www/Aurum/.env')

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    print("--- OPEN POSITIONS ---")
    cursor.execute("""
        SELECT * FROM operaciones 
        WHERE estado IN ('ABIERTA', 'PENDIENTE') 
        ORDER BY fecha_apertura DESC LIMIT 10
    """)
    ops = cursor.fetchall()
    for op in ops:
        print(json.dumps(op, default=str, indent=2))

    print("\n--- RECENT WORKER VOTES (senales) ---")
    cursor.execute("""
        SELECT * FROM senales 
        ORDER BY timestamp DESC LIMIT 20
    """)
    votes = cursor.fetchall()
    for v in votes:
         print(json.dumps(v, default=str, indent=2))

    print("\n--- GEMINI NLP ANALYSIS ---")
    cursor.execute("""
        SELECT * FROM nlp_cache 
        ORDER BY created_at DESC LIMIT 10
    """)
    nlp = cursor.fetchall()
    for n in nlp:
         print(json.dumps(n, default=str, indent=2))

    print("\n--- RECENT AUDIT LOGS ---")
    cursor.execute("""
        SELECT * FROM audit_logs 
        ORDER BY timestamp DESC LIMIT 20
    """)
    logs = cursor.fetchall()
    for l in logs:
         print(json.dumps(l, default=str, indent=2))

    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
