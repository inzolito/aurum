import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate():
    print("--- AURUM DB MIGRATION: V11.0 FULL DEPLOYMENT ---")
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

        # 1. Execute SQL files from database/migrations in order
        migrations_dir = os.path.join(os.path.dirname(__file__), "database", "migrations")
        if os.path.exists(migrations_dir):
            sql_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
            for sql_file in sql_files:
                print(f"Executing {sql_file}...")
                with open(os.path.join(migrations_dir, sql_file), "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
                print(f"{sql_file} completed.")
        else:
            print("ERROR: Migrations directory not found!")
            return

        # 2. Add V10.0 columns to registro_senales
        v10_columns = [
            ("voto_volume", "NUMERIC(4,3)"),
            ("voto_cross", "NUMERIC(4,3)"),
            ("voto_hurst", "NUMERIC(4,3)"),
            ("voto_sniper", "NUMERIC(4,3)")
        ]
        
        for col_name, col_type in v10_columns:
            cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='registro_senales' AND column_name='{col_name}';")
            if not cursor.fetchone():
                print(f"Adding V10 column {col_name}...")
                cursor.execute(f"ALTER TABLE registro_senales ADD COLUMN {col_name} {col_type};")

        # 3. Add V11.0 columns (hash_contexto, veredicto_apertura)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cache_nlp_impactos' AND column_name='hash_contexto';")
        if not cursor.fetchone():
            print("Adding V11 column hash_contexto to cache_nlp_impactos...")
            cursor.execute("ALTER TABLE cache_nlp_impactos ADD COLUMN hash_contexto VARCHAR(64);")

        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='registro_operaciones' AND column_name='veredicto_apertura';")
        if not cursor.fetchone():
            print("Adding column veredicto_apertura to registro_operaciones...")
            cursor.execute("ALTER TABLE registro_operaciones ADD COLUMN veredicto_apertura NUMERIC(4,3);")

        print("Full V11 Migration completed successfully.")
        
    except Exception as e:
        print(f"Migration FAILED: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()
