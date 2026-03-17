import os
import socket
import time
from dotenv import load_dotenv
import asyncio

# Need to handle the fact that _enviar_telegram is async or sync?
# Wait, let's check config/notifier.py
# If we don't know, we can just use the requests library directly to ensure it works.
import requests

load_dotenv()

def enviar_telegram_sync(mensaje: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("No Telegram credentials found.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Fallo enviando a Telegram: {e}")

def tcp_latency_test(host, port, retries=5):
    latencies = []
    for _ in range(retries):
        try:
            start_time = time.time()
            with socket.create_connection((host, port), timeout=2):
                end_time = time.time()
                latencies.append((end_time - start_time) * 1000)
        except Exception as e:
            print(f"Error conectando a {host}:{port} -> {e}")
            return None
        time.sleep(0.5)
        
    avg_latency = sum(latencies) / len(latencies)
    return avg_latency

if __name__ == "__main__":
    host = os.getenv("DB_HOST", "35.239.183.207")
    port = int(os.getenv("DB_PORT", 5432))
    
    print(f"--- TEST DE LATENCIA TCP: {host}:{port} ---")
    latency = tcp_latency_test(host, port)
    
    if latency is not None:
        msg = f"[OK] <b>[V11.0 OMNI]</b> Test de Latencia hacia GCP\nServidor: {host}:{port}\nLatencia TCP Promedio: {latency:.2f} ms"
        print(msg.encode('ascii', 'ignore').decode())
        
        if latency < 100.0:
            print("Latencia OK (< 100ms). Enviando reporte...")
            enviar_telegram_sync(msg)
            print("Reporte enviado.")
        else:
            print("Latencia > 100ms. Enviando alerta...")
            enviar_telegram_sync(f"⚠️ <b>[ALERTA V11.0]</b> Latencia alta detectada.\n{msg}")
    else:
        print("Fallo en la prueba de latencia.")
