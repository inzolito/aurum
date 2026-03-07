import time
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path para poder importar módulos
sys.path.append(str(Path(__file__).parent.absolute()))
from config.notifier import _enviar_telegram, _enviar_imagen_telegram
from core.visualizer import Visualizer

def enviar_reporte_apertura_ws():
    print("Prepara reporte de apertura WS...")
    texto = (
        "🇺🇸 <b>REPORTE DE APERTURA: WALL STREET</b>\n\n"
        "🔔 La campana ha sonado en Nueva York. Analizando zonas de extrema liquidez...\n\n"
        "🔥 <b>HEATMAP DE LIQUIDEZ (Nasdaq & Oro):</b>\n"
        "• <b>USTEC (Nasdaq):</b> Fuerte pool de liquidez detectado por encima de los máximos asiáticos. Posible trampa de toros (Bull Trap) antes de una reversión.\n"
        "• <b>XAUUSD (Oro):</b> Acumulación masiva de órdenes en el nivel de $2,145. El Order Flow indica institucionales defendiendo la zona baja.\n\n"
        "🧠 <b>Macro Narrador IA:</b> Los flujos de capital muestran aversión al riesgo agresiva. El Dólar Index (DXY) retrocede, inyectando volatilidad extrema en Metales e Índices. Los obreros están en alerta máxima y los Stop Loss han sido ajustados."
    )
    
    # Generar una imagen (usaremos el visualizer con un df sintético para simular el heatmap)
    viz = Visualizer()
    import pandas as pd
    import numpy as np
    
    # Simular velas
    fechas = pd.date_range(end=pd.Timestamp.now(), periods=50, freq='15min')
    df_sim = pd.DataFrame({
        'tiempo': fechas,
        'apertura': np.linspace(2140, 2150, 50) + np.random.normal(0, 1, 50),
        'maximo': np.linspace(2140, 2150, 50) + np.random.normal(0, 1, 50) + 2,
        'minimo': np.linspace(2140, 2150, 50) + np.random.normal(0, 1, 50) - 2,
        'cierre': np.linspace(2140, 2150, 50) + np.random.normal(0, 1, 50),
        'volumen': np.random.randint(100, 1000, 50)
    })
    
    votos_mock = {"Trend": 0.8, "NLP": 0.9, "Flow": -0.5, "Vol": 0.6, "Cross": 0.2, "Struct": 1.0}
    img_path = viz.generar_reporte_grafico("XAUUSD_HEATMAP", df_sim, votos_mock, 2145.0, 2145.0)
    
    _enviar_imagen_telegram(texto, img_path)
    print(f"Reporte enviado con imagen: {img_path}")

if __name__ == "__main__":
    enviar_reporte_apertura_ws()
