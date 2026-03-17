import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config.db_connector import DBConnector
from config.notifier import _enviar_telegram

def test_news_report():
    db = DBConnector()
    if not db.conectar():
        print("Error conectando a la base de datos")
        return

    try:
        query = """
            SELECT titular, impacto_nlp, razonamiento_ia, tiempo 
            FROM sentimiento_noticias 
            ORDER BY tiempo DESC 
            LIMIT 19;
        """
        db.cursor.execute(query)
        noticias = db.cursor.fetchall()

        if not noticias:
            print("No se encontraron noticias en la base de datos.")
            return

        resumen = "🗞️ <b>REPORTE HORARIO: ÚLTIMAS 19 NOTICIAS</b>\n"
        resumen += "━━━━━━━━━━━━━━━━━━\n\n"

        for n in noticias:
            titular, impacto, razon, tiempo = n
            emoji = "🔴" if impacto < -0.3 else "🟢" if impacto > 0.3 else "⚪"
            resumen += f"{emoji} <b>{titular}</b>\n"
            resumen += f"<i>{razon[:150]}...</i>\n\n"

        print("Enviando reporte a Telegram...")
        _enviar_telegram(resumen)
        print("Hecho.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.desconectar()

if __name__ == "__main__":
    test_news_report()
