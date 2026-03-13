import os
import time
from datetime import datetime, timezone
import requests
import psycopg2
from dotenv import load_dotenv

def enviar_alerta(mensaje: str, token: str, chat_id: str):
    print(f"ENVIANDO ALERTA: {mensaje}")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def main():
    # Cargar variables de entorno locales (si se ejecuta localmente)
    # En la nube (CPython / Cloud Run), estas se leen del sistema
    load_dotenv()
    
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_PORT = os.getenv("DB_PORT", "5432")
    
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([DB_HOST, DB_NAME, DB_USER, DB_PASS, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        print("Faltan variables de entorno necesarias para el Centinela.")
        return

    MAX_INACTIVO_MINUTOS = 5
    VERIFICAR_CADA_MINUTOS = 2

    print("="*60)
    print(" ☁️ CENTINELA EN LA NUBE - DEAD MAN'S SWITCH")
    print(f" Monitoreando desconexiones cada {VERIFICAR_CADA_MINUTOS} mins.")
    print("="*60)
    
    alerta_enviada = False
    
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT,
                connect_timeout=10
            )
            cursor = conn.cursor()
            cursor.execute("SELECT tiempo FROM estado_bot WHERE id = 1;")
            fila = cursor.fetchone()
            
            if fila:
                ultimo_latido = fila[0]
                ahora = datetime.now(timezone.utc)
                minutos_inactivo = (ahora - ultimo_latido).total_seconds() / 60.0
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Último latido hace {minutos_inactivo:.1f} min.")
                
                # Le damos un pequeño margen extra para evitar falsos positivos
                if minutos_inactivo > (MAX_INACTIVO_MINUTOS + 1):  
                    if not alerta_enviada:
                        msg = (
                            "🚨 <b>¡ALERTA CRÍTICA: AURUM DESCONECTADO!</b> 🚨\n\n"
                            f"El motor principal no ha enviado señales de vida a la base de datos en los últimos {minutos_inactivo:.1f} minutos.\n\n"
                            "⚠️ <b>Causas probables:</b>\n"
                            "• El ordenador local (Windows) se apagó o hibernó.\n"
                            "• Se cortó la conexión a Internet en la casa.\n"
                            "• Proceso de background finalizado forzosamente.\n\n"
                            "<i>Por favor, revisa el equipo host lo antes posible para reanudar la operativa.</i>"
                        )
                        enviar_alerta(msg, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
                        alerta_enviada = True
                else:
                    if alerta_enviada:
                        msg_recover = "✅ <b>Aurum ha vuelto a conectarse.</b> El ordenador está en línea y operando nuevamente."
                        enviar_alerta(msg_recover, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
                        alerta_enviada = False
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Error de conexión a DB desde el Centinela: {e}")
            
        time.sleep(VERIFICAR_CADA_MINUTOS * 60)

if __name__ == "__main__":
    main()
