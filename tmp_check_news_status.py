from config.db_connector import DBConnector
import json

def get_detailed_news_status():
    db = DBConnector()
    if not db.conectar():
        return

    # 1. Regimenes Activos (Estados de mercado)
    try:
        db.cursor.execute("SELECT id, titulo, clasificacion, estado, fecha_inicio FROM regimenes_mercado WHERE estado = 'ACTIVO'")
        regimes = [dict(zip(['id', 'titulo', 'tipo', 'estado', 'fecha'], row)) for row in db.cursor.fetchall()]
    except Exception as e:
        regimes = f"Error: {e}"

    # 2. Ultimas noticias crudas para ver frescura
    try:
        db.cursor.execute("SELECT id, title, creado_en FROM raw_news_feed ORDER BY creado_en DESC LIMIT 10")
        raw = [dict(zip(['id', 'title', 'fecha'], row)) for row in db.cursor.fetchall()]
    except Exception as e:
        raw = f"Error: {e}"

    print(json.dumps({'regimes': regimes, 'raw_news': raw}, indent=2, default=str))
    db.desconectar()

if __name__ == "__main__":
    get_detailed_news_status()
