import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config.db_connector import DBConnector

def fix_db():
    db = DBConnector()
    if not db.conectar():
        print("Failed to connect")
        return
        
    print("Conectado a la BD...")
    
    query = """
    ALTER TABLE cache_nlp_impactos ADD COLUMN IF NOT EXISTS hash_contexto TEXT;
    CREATE INDEX IF NOT EXISTS idx_hash_contexto ON cache_nlp_impactos (hash_contexto);
    GRANT ALL PRIVILEGES ON TABLE cache_nlp_impactos TO aurum_admin;
    """
    
    try:
        db.cursor.execute(query)
        db.conn.commit()
        print("Migración completada exitosamente.")
    except Exception as e:
        print(f"Error al migrar: {e}")
        db.conn.rollback()
    
    db.desconectar()

if __name__ == "__main__":
    fix_db()
