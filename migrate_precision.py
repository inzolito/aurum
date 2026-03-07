from config.db_connector import DBConnector
import sys

def migrate_precision():
    db = DBConnector()
    if not db.conectar():
        print("Error al conectar a la base de datos")
        sys.exit(1)
    
    try:
        # 1. Agregar columnas para precisar la entrada
        db.cursor.execute("ALTER TABLE registro_operaciones ADD COLUMN IF NOT EXISTS veredicto_apertura NUMERIC(4,3);")
        db.cursor.execute("ALTER TABLE registro_operaciones ADD COLUMN IF NOT EXISTS probabilidad_est NUMERIC(4,1);")
        
        # 2. Agregar columnas para la divergencia de precisión al cierre
        db.cursor.execute("ALTER TABLE registro_operaciones ADD COLUMN IF NOT EXISTS resultado_final VARCHAR(10);") # GANADO, PERDIDO
        db.cursor.execute("ALTER TABLE registro_operaciones ADD COLUMN IF NOT EXISTS divergencia_precision NUMERIC(5,2);")
        
        db.conn.commit()
        print("Migración de precisión completada.")
        
    except Exception as e:
        print(f"Error durante la migración: {e}")
        db.conn.rollback()
    finally:
        db.desconectar()

if __name__ == "__main__":
    migrate_precision()
