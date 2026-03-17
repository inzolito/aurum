from config.db_connector import DBConnector
import sys

def recalibrate_v2():
    db = DBConnector()
    if not db.conectar():
        print("Error al conectar a la base de datos")
        sys.exit(1)
    
    try:
        # 1. Ajuste del Umbral de Caza (Nombre corregido: 'umbral_disparo' según esquema inicial)
        db.cursor.execute("UPDATE parametros_sistema SET valor = 0.45 WHERE nombre_parametro = 'umbral_disparo';")
        # Por si acaso existe con el prefijo, lo actualizamos también
        db.cursor.execute("UPDATE parametros_sistema SET valor = 0.45 WHERE nombre_parametro = 'GERENTE.umbral_disparo';")
        
        # 2. Re-balanceo de Pesos (Estos sí tienen prefijos en el esquema inicial)
        db.cursor.execute("UPDATE parametros_sistema SET valor = 0.50 WHERE nombre_parametro = 'TENDENCIA.peso_voto';")
        db.cursor.execute("UPDATE parametros_sistema SET valor = 0.50 WHERE nombre_parametro = 'NLP.peso_voto';")
        db.cursor.execute("UPDATE parametros_sistema SET valor = 0.00 WHERE nombre_parametro = 'ORDER_FLOW.peso_voto';")
        
        db.conn.commit()
        print("Parametros actualizados correctamente en DB (V2).")
        
    except Exception as e:
        print(f"Error durante la recalibración V2: {e}")
        db.conn.rollback()
    finally:
        db.desconectar()

if __name__ == "__main__":
    recalibrate_v2()
