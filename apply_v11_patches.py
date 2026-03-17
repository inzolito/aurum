import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def apply_v11():
    print("--- AURUM DB V11.0 PATCHES ---")
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
        conn.autocommit = True
        cursor = conn.cursor()

        # Check and Add V11.0 column hash_contexto to cache_nlp_impactos
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cache_nlp_impactos' AND column_name='hash_contexto';")
        if not cursor.fetchone():
            print("Adding V11 column hash_contexto to cache_nlp_impactos...")
            cursor.execute("ALTER TABLE cache_nlp_impactos ADD COLUMN hash_contexto VARCHAR(64);")
        else:
            print("hash_contexto already exists.")

        # Check and Add veredicto_apertura
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='registro_operaciones' AND column_name='veredicto_apertura';")
        if not cursor.fetchone():
            print("Adding column veredicto_apertura to registro_operaciones...")
            cursor.execute("ALTER TABLE registro_operaciones ADD COLUMN veredicto_apertura NUMERIC(4,3);")
        else:
            print("veredicto_apertura already exists.")

        # Also confirm cache_nlp_impactos exists in case it doesn't
        cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name='cache_nlp_impactos';")
        if not cursor.fetchone():
            print("WARNING: cache_nlp_impactos table missing! Creating it...")
            cursor.execute("""
            CREATE TABLE cache_nlp_impactos (
                id SERIAL PRIMARY KEY,
                simbolo VARCHAR(10) NOT NULL,
                titular_original TEXT NOT NULL,
                impacto_calculado NUMERIC(3, 2) NOT NULL,
                razonamiento TEXT,
                creado_en TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                hash_contexto VARCHAR(64) UNIQUE
            );
            """)

        print("V11 Patches applied successfully.")
        
    except Exception as e:
        print(f"Patch FAILED: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    apply_v11()
