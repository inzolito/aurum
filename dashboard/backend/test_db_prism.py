import sys
import os
from dotenv import load_dotenv

# Path adjust to find DBConnector
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.db_connector import DBConnector

def test_dashboard_connection():
    # Load the local .env we just copied
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    print(f"Loading env from: {dotenv_path}")
    load_dotenv(dotenv_path)
    
    print("--- Testing Dashboard Connection ---")
    print(f"DB_HOST: {os.getenv('DB_HOST')}")
    print(f"DB_NAME: {os.getenv('DB_NAME')}")
    print(f"DB_USER: {os.getenv('DB_USER')}")
    
    db = DBConnector()
    if db.conectar():
        print("SUCCESS! The dashboard can now connect to the DB.")
        if db.test_conexion():
            print("DB version check passed.")
        db.desconectar()
    else:
        print("FAILED! The connection is still failing.")
        
        # Check if localhost works as a fallback
        print("\nTrying fallback to localhost...")
        os.environ["DB_HOST"] = "localhost"
        db_fallback = DBConnector()
        if db_fallback.conectar():
            print("SUCCESS with localhost fallback!")
            db_fallback.desconectar()
        else:
            print("FAILED even with localhost.")

if __name__ == "__main__":
    test_dashboard_connection()
