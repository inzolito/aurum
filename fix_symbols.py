from config.db_connector import DBConnector
db = DBConnector()
if db.conectar():
    try:
        db.cursor.execute("UPDATE activos SET simbolo_broker = 'SPXUSD' WHERE simbolo = 'US500'")
        db.cursor.execute("UPDATE activos SET simbolo_broker = 'NDXUSD' WHERE simbolo = 'USTEC'")
        db.conn.commit()
        print("[DB] Símbolos de índices normalizados: SPXUSD, NDXUSD.")
    except Exception as e:
        print(f"[DB] Error: {e}")
    finally:
        db.desconectar()
