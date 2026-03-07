import sys
import os
sys.path.append(os.getcwd())
from config.db_connector import DBConnector

db = DBConnector()
if db.conectar():
    db.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='registro_senales';")
    columns = db.cursor.fetchall()
    print("Columnas en registro_senales:")
    for col in columns:
        print(f"- {col[0]}")
    db.desconectar()
