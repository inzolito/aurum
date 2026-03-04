import os
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
import numpy as np
from datetime import datetime

# Usar backend no interactivo para servidores
matplotlib.use('Agg')

class Visualizer:
    """
    Módulo Gráfico de Aurum (V7.5).
    Genera reportes visuales con matplotlib.
    """

    def __init__(self, output_dir="temp/telemetry"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generar_reporte_grafico(self, simbolo: str, df: pd.DataFrame, 
                                votos: dict, ob_precio: float, poc: float) -> str:
        """
        Genera una imagen PNG con:
        1. Gráfico de precios (últimas velas) + OB + POC.
        2. Barra de sentimiento (7 obreros).
        Retorna la ruta del archivo generado.
        """
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), gridspec_kw={'height_ratios': [3, 1]})
        fig.patch.set_facecolor('#0a0a0a')
        
        # --- 1. Gráfico de Precios ---
        # Limitamos a las últimas 50 velas para claridad
        plot_df = df.tail(50).copy()
        x = np.arange(len(plot_df))
        
        # Dibujar velas simples (cuerpo y mecha)
        up = plot_df[plot_df.cierre >= plot_df.apertura]
        down = plot_df[plot_df.cierre < plot_df.apertura]
        
        col1 = '#00ffaa' # Bullish
        col2 = '#ff4444' # Bearish
        
        # Mechas
        ax1.vlines(x[plot_df.cierre >= plot_df.apertura], plot_df.minimo[plot_df.cierre >= plot_df.apertura], 
                   plot_df.maximo[plot_df.cierre >= plot_df.apertura], color=col1, linewidth=1)
        ax1.vlines(x[plot_df.cierre < plot_df.apertura], plot_df.minimo[plot_df.cierre < plot_df.apertura], 
                   plot_df.maximo[plot_df.cierre < plot_df.apertura], color=col2, linewidth=1)
        
        # Cuerpos
        ax1.bar(x[plot_df.cierre >= plot_df.apertura], plot_df.cierre[plot_df.cierre >= plot_df.apertura] - plot_df.apertura[plot_df.cierre >= plot_df.apertura], 
                bottom=plot_df.apertura[plot_df.cierre >= plot_df.apertura], color=col1, width=0.6)
        ax1.bar(x[plot_df.cierre < plot_df.apertura], plot_df.cierre[plot_df.cierre < plot_df.apertura] - plot_df.apertura[plot_df.cierre < plot_df.apertura], 
                bottom=plot_df.apertura[plot_df.cierre < plot_df.apertura], color=col2, width=0.6)

        # Marcar POC (Línea Amarilla discontinua)
        if poc > 0:
            ax1.axhline(poc, color='yellow', linestyle='--', alpha=0.6, label=f"POC: {poc:.2f}")
            
        # Marcar Order Block (Zona Azul)
        if ob_precio > 0:
            ax1.axhline(ob_precio, color='#00aaff', alpha=0.4, linewidth=10, label=f"OB: {ob_precio:.2f}")

        ax1.set_title(f"CENTINELA OMNI - {simbolo} (M1/M15)", color='white', fontsize=14, pad=20)
        ax1.grid(color='gray', linestyle='--', alpha=0.2)
        ax1.legend(loc='upper left', fontsize=10)
        
        # --- 2. Barra de Sentimiento ---
        nombres = list(votos.keys())
        valores = list(votos.values())
        colores = ['#00ffaa' if v > 0 else '#ff4444' if v < 0 else '#888888' for v in valores]
        
        ax2.barh(nombres, valores, color=colores)
        ax2.set_xlim(-1, 1)
        ax2.axvline(0, color='white', linewidth=0.8)
        ax2.set_title("Veredicto de la Cuadrilla (-1.0 a +1.0)", color='white', fontsize=10)
        ax2.grid(axis='x', color='gray', linestyle='--', alpha=0.2)

        plt.tight_layout()
        
        # Guardado
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"report_{simbolo}_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)
        fig.savefig(filepath, dpi=100, facecolor=fig.get_facecolor())
        plt.close(fig)
        
        return os.path.abspath(filepath)
