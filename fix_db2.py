import psycopg2

try:
    conn = psycopg2.connect(
        host="35.239.183.207",
        port=5432,
        dbname="aurum_db",
        user="postgres",
        password="AurumProyect1milion"
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute("ALTER TABLE cache_nlp_impactos ADD COLUMN IF NOT EXISTS hash_contexto TEXT;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hash_contexto ON cache_nlp_impactos (hash_contexto);")
    cur.execute("GRANT ALL PRIVILEGES ON TABLE cache_nlp_impactos TO aurum_admin;")
    
    # Try doing it as aurum_admin just to grant in case it's needed, actually just owner postgres should work.
    
    print("Migración completada exitosamente.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error as postgres: {e}")
    # Fallback to aurum_admin and try to hijack ownership if possible? Or skip.
    try:
         conn2 = psycopg2.connect(
             host="35.239.183.207",
             port=5432,
             dbname="aurum_db",
             user="aurum_admin",
             password="AurumProyect1milion"
         )
         conn2.autocommit = True
         cur2 = conn2.cursor()
         cur2.execute("ALTER TABLE cache_nlp_impactos ADD COLUMN IF NOT EXISTS hash_contexto TEXT;")
         cur2.execute("CREATE INDEX IF NOT EXISTS idx_hash_contexto ON cache_nlp_impactos (hash_contexto);")
         print("Migración completada exitosamente (con aurum_admin).")
         cur2.close()
         conn2.close()
    except Exception as e2:
         print(f"Error as aurum_admin: {e2}")

