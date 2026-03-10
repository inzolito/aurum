import feedparser
import json
import hashlib
import time
import os
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich import box

from config.db_connector import DBConnector
from config.notifier import _enviar_telegram

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Lista de palabras clave para el filtro mecánico
KEYWORDS = [
    "FED", "JEROME POWELL", "INFLACION", "CPI", "IPC", "RATE CUT", "INTEREST RATE",
    "PETROLEO", "OIL", "ARAMCO", "SAUDI", "IRAN", "GUERRA", "ATAQUE", "MISIL",
    "XAU", "GOLD", "ORO", "RECESION", "PMI", "NFP", "UNEMPLOYMENT", "VIX",
    "NVIDIA", "TESLA", "APPLE", "NASDAQ", "SP500", "US30", "US500", "USTEC",
    "LAGARDE", "ECB", "BCE", "BITCOIN", "BTC", "BINANCE", "CRIPTO", "CHINA",
    "TAIWAN", "RUSSIA", "PUTIN", "TRUMP", "BIDEN", "ELECCIONES"
]

RSS_FEEDS = [
    "https://es.investing.com/rss/news_1.rss",   # Noticias Generales
    "https://es.investing.com/rss/news_25.rss",  # Commodities
    "https://es.investing.com/rss/news_4.rss",   # Forex
    "https://es.investing.com/rss/news_95.rss",  # Economía
    "https://es.investing.com/rss/news_11.rss",  # Bancos Centrales
    "https://es.investing.com/rss/market_overview.rss", # Resumen
]

class NewsHunter:
    def __init__(self, mode="daemon"):
        self.db = DBConnector()
        self.interval = 600 # 10 minutos
        self.active = False
        self.mode = mode # "daemon" o "view"
        self.console = Console()
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            print(f"[HUNTER] Error iniciando Gemini: {e}")
            self.client = None

    def start(self):
        self.active = True
        if not self.db.conectar():
            print("[HUNTER] Error conectando a DB")
            return

        if self.mode == "view":
            self.show_dashboard()
        else:
            print(f"[HUNTER] Radar activo (Daemon). Frecuente: {self.interval}s")
            self.barrido_inicial()
            try:
                while self.active:
                    self.patrullar()
                    time.sleep(self.interval)
            except KeyboardInterrupt:
                self.stop()
            finally:
                self.db.desconectar()

    def barrido_inicial(self):
        """Escanea todos los feeds al arrancar para asegurar que no falte nada reciente."""
        print("[HUNTER] 🧹 Iniciando barrido de noticias recientes...")
        self.patrullar()

    def show_dashboard(self):
        """Modo TUI interactivo para monitorear noticias en tiempo real."""
        with Live(self._generate_table(), refresh_per_second=1) as live:
            try:
                while self.active:
                    live.update(self._generate_table())
                    time.sleep(15) # Refrescar cada 15s desde DB
            except KeyboardInterrupt:
                self.stop()

    def _generate_table(self):
        table = Table(title="📡 AURUM NEWS RADAR - LIVE FEED", box=box.ROUNDED, style="cyan", expand=True)
        table.add_column("Tiempo", style="dim", width=10)
        table.add_column("Fuente", style="yellow", width=12)
        table.add_column("Titular", style="bold white")
        table.add_column("Análisis / Impacto", justify="center", width=20)

        try:
            # Re-conectar si es necesario
            if not self.db.conn or self.db.conn.closed: self.db.conectar()
            
            # Traer las últimas 20 noticias (V13.0 columns: timestamp, content_summary)
            self.db.cursor.execute("""
                SELECT timestamp, source, title, content_summary 
                FROM raw_news_feed 
                ORDER BY timestamp DESC 
                LIMIT 20;
            """)
            rows = self.db.cursor.fetchall()
            for row in rows:
                fecha = row[0].strftime("%H:%M") if row[0] else "??"
                fuente = row[1][:12]
                titulo = row[2]
                resumen = row[3] or ""
                
                # Clasificar impacto visualmente
                impacto_str = "S/D"
                style_imp = "white"
                
                if "Impacto:" in resumen:
                    try:
                        val = resumen.split("|")[0].replace("Impacto:", "").strip()
                        impacto_str = f"IMPACTO {val}/10"
                        if int(val) >= 8: style_imp = "bold red"
                        elif int(val) >= 5: style_imp = "yellow"
                        else: style_imp = "green"
                    except: pass
                elif "Descargada" in resumen:
                    impacto_str = "[dim]Irrelevante[/dim]"
                elif "Filtro mecanico" in resumen:
                    impacto_str = "[dim]Ignorada[/dim]"

                table.add_row(fecha, fuente, titulo, f"[{style_imp}]{impacto_str}[/{style_imp}]")
        except Exception as e:
            table.add_row("ERR", "DB", f"Error de lectura: {e}", "--")
            
        return Panel(table, subtitle="Ctrl+C para salir | Monitoreo 24/7 Activo", border_style="bright_blue")

    def stop(self):
        self.active = False
        print("[HUNTER] Radar desactivado.")

    def patrullar(self):
        ahora = datetime.now().strftime('%H:%M:%S')
        for url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    self._procesar_entrada(entry)
            except:
                pass

    def _procesar_entrada(self, entry):
        titulo = getattr(entry, 'title', 'Sin titulo')
        link = getattr(entry, 'link', 'Sin link')
        
        # Extraer fecha real de publicación del feed
        pub_parsed = getattr(entry, 'published_parsed', None)
        if pub_parsed:
            # Convertir struct_time a datetime UTC
            dt_pub = datetime(pub_parsed[0], pub_parsed[1], pub_parsed[2], pub_parsed[3], pub_parsed[4], pub_parsed[5], tzinfo=timezone.utc)
        else:
            dt_pub = datetime.now(timezone.utc)

        hash_id = hashlib.sha256(titulo.encode()).hexdigest()

        if self.db.verificar_hash_noticia(hash_id):
            return

        relevante_mecanico = any(k.upper() in titulo.upper() for k in KEYWORDS)
        
        if relevante_mecanico:
            relevancia_ia, impacto = self._evaluar_relevancia_ia(titulo)
            
            if relevancia_ia:
                self.db.guardar_noticia_cruda(
                    source="Investing",
                    title=titulo,
                    summary=f"Impacto: {impacto}/10 | {link}",
                    hash_id=hash_id,
                    published_at=dt_pub
                )
                if impacto >= 8:
                    self._inyectar_regimen(titulo, impacto, dt_pub)
            else:
                self.db.guardar_noticia_cruda(
                    source="Investing",
                    title=titulo,
                    summary=f"Descargada por IA | {link}",
                    hash_id=hash_id,
                    published_at=dt_pub
                )
        else:
            self.db.guardar_noticia_cruda(
                source="Investing",
                title=titulo,
                summary=f"Filtro mecanico | {link}",
                hash_id=hash_id,
                published_at=dt_pub
            )

    def _evaluar_relevancia_ia(self, titulo: str):
        if not self.client: return False, 0
        prompt = (
            f"Evalua si este titular afecta al Oro, Petroleo o Indices (NASDAQ/SP500).\n"
            f"Titular: {titulo}\n"
            f"Responde JSON: {{\"relevante\": bool, \"impacto\": int(1-10)}}"
        )
        try:
            resp = self.client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(resp.text)
            return data.get("relevante", False), data.get("impacto", 0)
        except:
            return False, 0

    def _inyectar_regimen(self, titulo: str, impacto: int, dt_pub: datetime):
        try:
            tipo = "URGENTE" if impacto >= 9 else "CATALIZADOR"
            query = "INSERT INTO regimenes_mercado (titulo, clasificacion, estado, fecha_inicio) VALUES (%s, %s, 'ACTIVO', %s)"
            self.db.cursor.execute(query, (titulo, tipo, dt_pub))
            self.db.conn.commit()
            
            # Formatear hora local para el mensaje
            hora_msg = dt_pub.astimezone().strftime("%H:%M") 
            _enviar_telegram(f"🚨 <b>HUNTER IMPACTO {impacto}/10</b>\n\n📌 {titulo}\n⌚ Pub: {hora_msg}")
        except:
            self.db.conn.rollback()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", action="store_true", help="Inicia en modo visor (TUI)")
    args = parser.parse_args()
    
    hunter = NewsHunter(mode="view" if args.view else "daemon")
    hunter.start()
