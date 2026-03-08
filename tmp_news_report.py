from config.db_connector import DBConnector
import json

def get_news_data():
    db = DBConnector()
    if not db.conectar():
        return

    tables = ['raw_news_feed', 'market_catalysts', 'sentimiento_noticias', 'regimenes_mercado']
    data = {}
    
    for t in tables:
        try:
            db.cursor.execute(f"SELECT * FROM {t} ORDER BY 1 DESC LIMIT 3")
            colnames = [desc[0] for desc in db.cursor.description]
            data[t] = [dict(zip(colnames, row)) for row in db.cursor.fetchall()]
        except:
            data[t] = "Not accessible"
            
    print(json.dumps(data, indent=2, default=str))
    db.desconectar()

if __name__ == "__main__":
    get_news_data()
