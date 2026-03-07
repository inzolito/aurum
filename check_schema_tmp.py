import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def check_schema():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            dbname=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()
        print("--- NULLABILITY registro_senales ---")
        cursor.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'registro_senales' ORDER BY ordinal_position;")
        for col in cursor.fetchall():
            print(f"{col[0]}: {col[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Error checking schema: {e}")

if __name__ == "__main__":
    check_schema()
