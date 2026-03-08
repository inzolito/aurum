from config.db_connector import DBConnector
import json

def inspect_tables():
    db = DBConnector()
    if not db.conectar():
        print("Error connecting to DB")
        return

    # List all tables
    db.cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [r[0] for r in db.cursor.fetchall()]
    print(f"Tables in DB: {tables}")

    target_tables = ['raw_news_feed', 'market_catalysts', 'sentimiento_noticias', 'regimenes_mercado', 'cache_nlp_impactos']
    results = {}

    for table in target_tables:
        if table in tables:
            try:
                db.cursor.execute(f"SELECT * FROM {table} ORDER BY 1 DESC LIMIT 5")
                colnames = [desc[0] for desc in db.cursor.description]
                rows = [dict(zip(colnames, row)) for row in db.cursor.fetchall()]
                results[table] = rows
            except Exception as e:
                results[table] = f"Error: {str(e)}"
        else:
            results[table] = "Table not found"

    print(json.dumps(results, indent=2, default=str))
    db.desconectar()

if __name__ == "__main__":
    inspect_tables()
