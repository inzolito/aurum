import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config.db_connector import DBConnector
from config.notifier import _enviar_telegram

db = DBConnector()
db.conectar()
query = """
    SELECT DISTINCT ON (razonamiento) simbolo, razonamiento, creado_en 
    FROM cache_nlp_impactos 
    ORDER BY razonamiento, creado_en DESC 
    LIMIT 19;
"""
db.cursor.execute(query)
noticias = db.cursor.fetchall()
if noticias:
    resumen = "🗞️ <b>AURUM: TEST REPORTE DE NOTICIAS</b>\n"
    resumen += "━━━━━━━━━━━━━━━━━━\n\n"
    for n in noticias:
        sim, razon, t = n
        resumen += f"• <b>{sim}:</b> {razon}\n\n"
    _enviar_telegram(resumen)
    print("Test enviado.")
else:
    print("Sin noticias.")
db.desconectar()
