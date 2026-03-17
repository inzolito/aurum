import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.absolute()))
from config.db_connector import DBConnector

db = DBConnector()
if db.conectar():
    db.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'registro_operaciones';")
    print("registro_operaciones columns:", [r[0] for r in db.cursor.fetchall()])
    
    db.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'parametros_sistema';")
    print("parametros_sistema columns:", [r[0] for r in db.cursor.fetchall()])
    db.desconectar()
