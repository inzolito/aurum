import psycopg2

try:
    conn = psycopg2.connect(
        host="35.239.183.207",
        port=5432,
        dbname="aurum_db",
        user="aurum_admin",
        password="AurumProyect1milion"
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute("SELECT tableowner FROM pg_tables WHERE tablename='cache_nlp_impactos';")
    owner = cur.fetchone()[0]
    print(f"Table owner is: {owner}")
    
    cur.execute(f"SET ROLE {owner};")
    cur.execute("ALTER TABLE cache_nlp_impactos ADD COLUMN IF NOT EXISTS hash_contexto TEXT;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hash_contexto ON cache_nlp_impactos (hash_contexto);")
    cur.execute("GRANT ALL PRIVILEGES ON TABLE cache_nlp_impactos TO aurum_admin;")
    print("Migración completada exitosamente usando SET ROLE.")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
