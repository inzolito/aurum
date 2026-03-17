from config.db_connector import DBConnector

db = DBConnector()
db.conectar()

db.cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [r[0] for r in db.cursor.fetchall()]

for t in tables:
    try:
        db.cursor.execute(f'SELECT COUNT(*) FROM {t}')
        count = db.cursor.fetchone()[0]
        print(f"{t}: {count}")
    except Exception as e:
        print(f"Error checking {t}: {e}")

db.desconectar()
