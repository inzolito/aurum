import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate():
    print("--- AURUM DB MIGRATION: V10.0 SEÑALES ---")
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", 5432),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            connect_timeout=10,
        )
        cursor = conn.cursor()
        
        # Add new columns to registro_senales
        columns = [
            ("voto_volume", "NUMERIC(4,3)"),
            ("voto_cross", "NUMERIC(4,3)"),
            ("voto_hurst", "NUMERIC(4,3)"),
            ("voto_sniper", "NUMERIC(4,3)")
        ]
        
        for col_name, col_type in columns:
            print(f"Checking column {col_name}...")
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='registro_senales' AND column_name='{col_name}';
            """)
            if not cursor.fetchone():
                print(f"Adding column {col_name}...")
                cursor.execute(f"ALTER TABLE registro_senales ADD COLUMN {col_name} {col_type};")
            else:
                print(f"Column {col_name} already exists.")
        
        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        print(f"Migration FAILED: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
