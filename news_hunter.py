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
from config.notifier import _enviar_telegram, notificar_noticia_procesada

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

# Feeds cripto — solo eventos de alto impacto (colapso, ban regulatorio, intervención)
RSS_FEEDS_CRIPTO = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",  # CoinDesk
    "https://cointelegraph.com/rss",                    # CoinTelegraph
    "https://www.theblock.co/rss.xml",                  # The Block
]

# Palabras clave adicionales para filtro mecánico de noticias cripto
KEYWORDS_CRIPTO = [
    "EXCHANGE COLLAPSE", "HACK", "EXPLOIT", "BANKRUPTCY", "INSOLVENCY",
    "SEC", "CFTC", "REGULATION", "BAN", "SEIZURE", "ARREST",
    "TETHER", "USDT", "USDC", "STABLECOIN", "DEPEG",
    "ETHEREUM", "ETH", "SOLANA", "SOL", "XRP", "RIPPLE",
    "CBDC", "GOVERNMENT", "FEDERAL RESERVE CRYPTO", "CONGRESS",
    "FTX", "BINANCE", "COINBASE", "KRAKEN", "BYBIT",
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
                    self._procesar_entrada(entry, es_cripto=False)
            except Exception as e_feed:
                print(f"[HUNTER] Error procesando feed {url}: {e_feed}")
        for url in RSS_FEEDS_CRIPTO:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    self._procesar_entrada(entry, es_cripto=True)
            except Exception as e_feed:
                print(f"[HUNTER] Error procesando feed cripto {url}: {e_feed}")

    def _procesar_entrada(self, entry, es_cripto=False):
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

        # Para feeds cripto se usa lista de keywords cripto adicional
        keywords_activos = KEYWORDS + KEYWORDS_CRIPTO if es_cripto else KEYWORDS
        relevante_mecanico = any(k.upper() in titulo.upper() for k in keywords_activos)

        # Determinar fuente y etiquetas para BD
        fuente_label = "Cripto" if es_cripto else "Investing"

        if relevante_mecanico:
            relevancia_ia, impacto = self._evaluar_relevancia_ia(titulo, es_cripto=es_cripto)

            if relevancia_ia:
                self.db.guardar_noticia_cruda(
                    source=fuente_label,
                    title=titulo,
                    summary=f"Impacto: {impacto}/10 | {link}",
                    hash_id=hash_id,
                    published_at=dt_pub
                )
                if impacto >= 8:
                    self._inyectar_regimen(titulo, impacto, dt_pub)
                # V18 MacroSensor: evaluar régimen macro para noticias con impacto >= 6
                self._evaluar_regimen_macro(titulo, impacto, dt_pub)
                # FASE 2 V15: Notificar noticias de impacto medio-alto por Telegram
                if impacto >= 5:
                    fuente_display = "CoinDesk/CoinTelegraph/TheBlock" if es_cripto else "Investing.com"
                    notificar_noticia_procesada(
                        titulo=titulo,
                        fuente=fuente_display,
                        published_at=dt_pub,
                        impacto=impacto,
                    )
            else:
                self.db.guardar_noticia_cruda(
                    source=fuente_label,
                    title=titulo,
                    summary=f"Descargada por IA | {link}",
                    hash_id=hash_id,
                    published_at=dt_pub
                )
        else:
            self.db.guardar_noticia_cruda(
                source=fuente_label,
                title=titulo,
                summary=f"Filtro mecanico | {link}",
                hash_id=hash_id,
                published_at=dt_pub
            )

    def _evaluar_relevancia_ia(self, titulo: str, es_cripto: bool = False):
        if not self.client: return False, 0
        if es_cripto:
            prompt = (
                f"Eres el sistema de análisis de noticias del bot de trading Aurum.\n"
                f"Estamos en bear market cripto prolongado. La gran mayoría de noticias cripto "
                f"son ruido (análisis de precio, predicciones, declaraciones menores, "
                f"adopción institucional menor). Solo califican como relevantes los eventos "
                f"de ALTO IMPACTO SISTÉMICO como: colapso/insolvencia de un exchange importante, "
                f"ban regulatorio masivo (gobierno grande: EEUU, UE, China), intervención "
                f"gubernamental directa (incautación de fondos, arresto de ejecutivos clave), "
                f"depeg grave de una stablecoin sistémica (USDT, USDC), o hack de más de "
                f"$500M en un protocolo crítico.\n"
                f"Noticias de precio, análisis técnico, adopción menor, ETF de segunda línea, "
                f"declaraciones optimistas o tweets de influencers tienen impacto BAJO (<=3) "
                f"en bear market y NO son relevantes para trading de commodities/forex/indices.\n\n"
                f"Titular: {titulo}\n"
                f"Responde JSON: {{\"relevante\": bool, \"impacto\": int(1-10)}}"
            )
        else:
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
        except (json.JSONDecodeError, KeyError) as e_parse:
            print(f"[HUNTER] Error parseando respuesta Gemini: {e_parse}")
            return False, 0
        except Exception as e_gemini:
            print(f"[HUNTER] Error llamando a Gemini: {e_gemini}")
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
        except Exception as e_reg:
            print(f"[HUNTER] Error inyectando régimen en DB: {e_reg}")
            try:
                self.db.conn.rollback()
            except Exception:
                pass

    def _evaluar_regimen_macro(self, titulo: str, impacto: int, dt_pub: datetime):
        """
        MacroSensor V18: evalúa si la noticia genera, actualiza o disipa un régimen macro.
        Solo actúa si impacto >= 6. Llama a Gemini con contexto de regímenes activos.
        """
        if not self.client or impacto < 6:
            return

        try:
            regimenes_activos = self.db.get_regimenes_macro_activos()
        except Exception:
            regimenes_activos = []

        # Serializar lista de regímenes para el prompt
        if regimenes_activos:
            lista_regimenes = "\n".join(
                f"  ID={r['id']} | tipo={r['tipo']} | nombre={r['nombre']} | "
                f"fase={r['fase']} | dir={r['direccion']} | peso={r['peso']}"
                for r in regimenes_activos
            )
        else:
            lista_regimenes = "  (ninguno activo actualmente)"

        # Obtener lista completa de activos operativos para que Gemini evalúe TODOS
        try:
            activos_db = self.db.get_activos()
            activos_lab = self.db.get_activos_lab_only()
            todos_activos = [a["simbolo"] for a in activos_db + activos_lab]
        except Exception:
            todos_activos = []
        lista_activos_str = ", ".join(todos_activos) if todos_activos else "(sin activos)"

        prompt = (
            f"Eres el MacroSensor del sistema de trading Aurum. Tu misión es EXCLUSIVAMENTE "
            f"detectar cambios estructurales macro que afecten múltiples mercados durante 3+ días.\n\n"
            f"TITULAR: {titulo}\n"
            f"IMPACTO EVALUADO: {impacto}/10\n\n"
            f"REGÍMENES MACRO ACTIVOS AHORA:\n{lista_regimenes}\n\n"
            f"ACTIVOS EN OPERACIÓN (evaluar TODOS si creas/actualizas régimen):\n{lista_activos_str}\n\n"
            f"REGLA PRINCIPAL — cuándo usar IGNORAR (la mayoría de los casos):\n"
            f"  IGNORAR si la noticia es cualquiera de estos tipos:\n"
            f"  • Nota de analista / precio objetivo de un banco (Goldman Sachs, JPMorgan, etc.)\n"
            f"  • Resultados corporativos (earnings, revenue, guidance) de UNA empresa\n"
            f"  • M&A, fusiones, adquisiciones de empresas específicas\n"
            f"  • Movimiento de precio de 1 día sin cambio estructural\n"
            f"  • Datos económicos puntuales sin cambio de política (PMI, IPC puntual, etc.)\n"
            f"  • Noticias sectoriales que afectan a 1-2 activos por menos de 48 horas\n\n"
            f"CUÁNDO crear NUEVO (muy selectivo — impacto estructural real):\n"
            f"  • Solo si impacto >= 8 Y afecta múltiples mercados durante semanas\n"
            f"  • Decisiones de banco central (Fed, BCE, BoE, BoJ) con implicación de meses\n"
            f"  • Eventos geopolíticos mayores con consecuencias sistémicas (guerra, acuerdo de paz)\n"
            f"  • Shocks macro globales (crisis financiera, pandemia, embargo energético)\n"
            f"  JAMÁS crear NUEVO para notas de analistas, resultados de empresa, o noticias de 1-2 días\n\n"
            f"CUÁNDO ACTUALIZAR:\n"
            f"  • Si la noticia confirma/intensifica un régimen existente → ACTUALIZAR ese ID\n"
            f"  • Si la noticia revierte o anula un régimen existente → DISIPAR ese ID\n\n"
            f"- Tipos válidos: MONETARIO, GEOPOLITICO, CORPORATIVO, ECONOMICO, MERCADO.\n"
            f"- Fases válidas: RUMOR, ACTIVO, DATOS, POST_CLIMAX.\n"
            f"- Direcciones válidas: RISK_ON, RISK_OFF, VOLATIL.\n"
            f"- peso: float entre 0.1 y 1.0 (intensidad del régimen).\n"
            f"- activos_afectados: JSON con TODOS los activos de la lista. "
            f'Ejemplo: [{{"simbolo":"XAUUSD","dir":"UP"}},{{"simbolo":"AUDCAD","dir":"DOWN"}}]\n'
            f"  Reglas de dirección: RISK_OFF→AUD/EUR/GBP/cripto=DOWN, JPY/XAU/XAG=UP.\n"
            f"  RISK_ON→lo opuesto. Incluir TODOS los activos (dir=NEUTRAL si no aplica).\n"
            f"- expira_horas: número entero de horas hasta que expira (null si indefinido).\n"
            f"- nombre: conciso como concepto estructural (ej: 'Fed Hawkish Q1-2026').\n\n"
            f"Responde SOLO en JSON (sin markdown):\n"
            f'{{"accion": "NUEVO|ACTUALIZAR|DISIPAR|IGNORAR", '
            f'"id_existente": null_o_int, '
            f'"tipo": "MONETARIO|GEOPOLITICO|CORPORATIVO|ECONOMICO|MERCADO", '
            f'"nombre": "...", '
            f'"fase": "RUMOR|ACTIVO|DATOS|POST_CLIMAX", '
            f'"direccion": "RISK_ON|RISK_OFF|VOLATIL", '
            f'"peso": 0.0_a_1.0, '
            f'"activos_afectados": "[...]", '
            f'"razonamiento": "...", '
            f'"expira_horas": null_o_int}}'
        )

        try:
            resp = self.client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(resp.text)
        except (json.JSONDecodeError, KeyError) as e_parse:
            print(f"[HUNTER-MACRO] Error parseando respuesta Gemini: {e_parse}")
            return
        except Exception as e_gemini:
            print(f"[HUNTER-MACRO] Error llamando a Gemini: {e_gemini}")
            return

        accion = data.get("accion", "IGNORAR").upper()

        if accion == "IGNORAR":
            print(f"[HUNTER-MACRO] Noticia ignorada por MacroSensor: '{titulo[:60]}'")
            return

        if accion == "NUEVO":
            expira_horas = data.get("expira_horas")
            expira_en = None
            if expira_horas:
                from datetime import timedelta
                expira_en = dt_pub + timedelta(hours=int(expira_horas))

            new_id = self.db.guardar_regimen_macro(
                tipo=data.get("tipo", "MERCADO"),
                nombre=data.get("nombre", titulo[:100]),
                fase=data.get("fase", "ACTIVO"),
                direccion=data.get("direccion", "VOLATIL"),
                peso=float(data.get("peso", 0.5)),
                activos_afectados=data.get("activos_afectados", "[]"),
                razonamiento=data.get("razonamiento", ""),
                expira_en=expira_en,
                fuente_noticia=titulo[:200],
            )
            if new_id:
                print(f"[HUNTER-MACRO] NUEVO régimen macro #{new_id}: '{data.get('nombre')}'")

        elif accion == "ACTUALIZAR":
            id_existente = data.get("id_existente")
            if not id_existente:
                print(f"[HUNTER-MACRO] ACTUALIZAR sin id_existente — ignorando.")
                return
            self.db.actualizar_regimen_macro(
                regimen_id=int(id_existente),
                fase=data.get("fase"),
                peso=float(data.get("peso")) if data.get("peso") is not None else None,
                razonamiento=data.get("razonamiento"),
            )
            print(f"[HUNTER-MACRO] ACTUALIZADO régimen macro #{id_existente}.")

        elif accion == "DISIPAR":
            id_existente = data.get("id_existente")
            if not id_existente:
                print(f"[HUNTER-MACRO] DISIPAR sin id_existente — ignorando.")
                return
            self.db.actualizar_regimen_macro(
                regimen_id=int(id_existente),
                fase="POST_CLIMAX",
                activo=False,
            )
            print(f"[HUNTER-MACRO] DISIPADO régimen macro #{id_existente}.")

if __name__ == "__main__":
    # Prevenir instancias duplicadas via Named Mutex en Windows
    if os.name == 'nt':
        import ctypes
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\AurumNewsHunterMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(_mutex)
            print("[HUNTER] Ya hay una instancia corriendo. Abortando.")
            os._exit(0)

    parser = argparse.ArgumentParser()
    parser.add_argument("--view", action="store_true", help="Inicia en modo visor (TUI)")
    args = parser.parse_args()

    hunter = NewsHunter(mode="view" if args.view else "daemon")
    hunter.start()
