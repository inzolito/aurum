from config.db_connector import DBConnector
import os
from dotenv import load_dotenv

def test_bot_connection():
    load_dotenv()
    print("--- Testing Connection like the Bot ---")
    print(f"Target Host: {os.getenv('DB_HOST')}")
    print(f"Target User: {os.getenv('DB_USER')}")
    
    db = DBConnector()
    if db.conectar():
        print("SUCCESS! The bot connection logic works on this host.")
        if db.test_conexion():
            print("DB version check passed.")
        db.desconectar()
    else:
        print("FAILED! The bot connection logic is failing here too.")

if __name__ == "__main__":
    test_bot_connection()
