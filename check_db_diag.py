from config.db_connector import DBConnector
import json

db = DBConnector()
db.conectar()

tables = [
    'sentimiento_noticias',
    'regimenes_mercado',
    'cache_nlp_impactos',
    'log_sistema',
    'registro_senales',
    'noticias_notificadas'
]

for table in tables:
    try:
        db.cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = db.cursor.fetchone()[0]
        print(f"Table: {table} | Count: {count}")
        if count > 0:
            db.cursor.execute(f"SELECT * FROM {table} LIMIT 2")
            print(f"  Sample: {db.cursor.fetchall()}")
    except Exception as e:
        print(f"Error in {table}: {e}")

db.desconectar()
