from config.db_connector import DBConnector

def check_params():
    db = DBConnector()
    db.conectar()
    db.cursor.execute("SELECT nombre_parametro, valor FROM parametros_sistema;")
    rows = db.cursor.fetchall()
    print("--- DB PARAMETERS ---")
    for row in rows:
        print(f"{row[0]}: {row[1]}")
    db.desconectar()

if __name__ == "__main__":
    check_params()
