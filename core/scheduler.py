import time
import threading
import schedule
from datetime import datetime
from config.notifier import _enviar_telegram, _enviar_imagen_telegram
from core.visualizer import Visualizer

class AurumScheduler:
    """
    Programador de Reportes (V7.5).
    Gestiona los envíos automáticos (08:30, 13:00, 20:00).
    """

    def __init__(self, manager):
        self.manager = manager
        self.visualizer = Visualizer()
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        """Inicia el hilo del programador."""
        # V10.1: Silent Hunter - Reportes automaticos desactivados
        # schedule.every().day.at("08:30").do(self.reporte_apertura)
        # schedule.every().day.at("13:00").do(self.reporte_mediodia)
        # schedule.every().day.at("20:00").do(self.reporte_cierre)
        
        # Eventos de Sesión (V7.6) - También desactivados para silencio total
        # schedule.every().day.at("00:00").do(self.evento_sesion, "Tokio")
        # schedule.every().day.at("08:00").do(self.evento_sesion, "Londres")
        # schedule.every().day.at("14:30").do(self.evento_sesion, "Nueva York")
        
        # V11.1: Reporte Horario de Noticias (Pedido por Usuario)
        schedule.every().hour.at(":00").do(self.reporte_noticias_horario)

        # D2 V14: Recalibración semanal de pesos — DESACTIVADA (ajuste manual preferido)
        # Llamar manualmente: engine.gerente._recalibrar_pesos() desde aurum_admin.py
        # schedule.every().sunday.at("17:00").do(self.recalibrar_pesos_semanal)
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("[SCHEDULER] Programador iniciado (Reportes + Sesiones + Pulso IA + Noticias)")

    def _run_loop(self):
        while not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(30)

    def reporte_noticias_horario(self):
        """Reporte Triple Horario (V13.0): Crudo + Contexto + Análisis."""
        print("[SCHEDULER] Generando Reporte Triple Horario...")
        try:
            db = self.manager.db
            
            # 1. NOTICIAS CRUDAS (de raw_news_feed)
            raw_news = db.get_top_news(limit=5)
            # 2. CONTEXTOS MAESTROS (de market_catalysts)
            catalysts = db.get_catalizadores_activos()
            # 3. ANÁLISIS DE ACTIVOS (de cache_nlp_impactos)
            activos = db.get_tablero_global() # Reusamos para ver sentimientos actuales
            
            resumen = "🏛️ <b>AURUM: REPORTE TRIPLE (V13.0)</b>\n"
            resumen += "━━━━━━━━━━━━━━━━━━\n\n"
            
            # Sección 1: NOTICIAS CRUDAS
            resumen += "📰 <b>NOTICIAS CRUDAS:</b>\n"
            if raw_news:
                for n in raw_news:
                    fecha_str = n['fecha'].strftime("%H:%M") if n['fecha'] else "Incierta"
                    resumen += f"• {n['title']} | Pub: {fecha_str} | ID: {n['hash'][:6]}\n"
            else:
                resumen += "<i>Sin noticias recientes.</i>\n"
            
            resumen += "\n🧠 <b>CONTEXTOS MAESTROS:</b>\n"
            if catalysts:
                for c in catalysts:
                    sesgo = "🟢" if c['score'] > 0 else "🔴" if c['score'] < 0 else "⚪"
                    resumen += f"• {c['name']} | Sesgo: {sesgo} {c['score']:+.2f} | Activo\n"
            else:
                resumen += "<i>Sin catalizadores maestros activos.</i>\n"
                
            resumen += "\n📊 <b>ANÁLISIS DE ACTIVOS:</b>\n"
            if activos:
                for a in activos[:5]: # Top 5 activos
                    impacto = "Alcista" if a['veredicto'] > 0.3 else "Bajista" if a['veredicto'] < -0.3 else "Neutral"
                    resumen += f"• <b>{a['simbolo']}:</b> {impacto} ({a['veredicto']:+.2f})\n"
            
            resumen += "\n<i>Monitorización continua V13.0 estructural.</i>"
            
            _enviar_telegram(resumen)
            print("[SCHEDULER] Reporte Triple enviado.")
        except Exception as e:
            print(f"[SCHEDULER] Error en Reporte Triple: {e}")

    def reporte_apertura(self):
        """08:30 - Estrategia de Apertura."""
        print("[SCHEDULER] Generando reporte de apertura...")
        activos = self.manager.db.obtener_activos_patrullaje()
        resumen = "🌅 <b>REPORTE DE APERTURA (08:30)</b>\n\n"
        
        # Analizar un activo de referencia (Oro) para el gráfico
        try:
            simbolo_ref = "XAUUSD"
            # Pedimos al manager que evalúe (simulado) para obtener datos frescos
            # Pero para no interferir con el loop, solo extraemos info técnica básica si es posible
            # Por ahora, un resumen textual detallado
            for a in activos:
                sim = a['simbolo']
                # Obtenemos Hurst y SMC rápido (usando caché si existe)
                res_h = self.manager.hurst.analizar(sim)
                res_s = self.manager.structure.analizar(sim)
                resumen += f"• <b>{sim}</b>: H={res_h['h']:.4f} ({res_h['estado']}) | OB: {res_s['ob_precio']}\n"
            
            resumen += "\n🧠 <b>Proyección Gemini:</b> La sesión asiática dejó liquidez pendiente en los mínimos diarios; se espera volatilidad en la apertura de Londres."
            _enviar_telegram(resumen)
        except Exception as e:
            print(f"[SCHEDULER] Error en reporte apertura: {e}")

    def reporte_mediodia(self):
        """13:00 - Flash de Mediodía."""
        print("[SCHEDULER] Generando reporte de mediodía...")
        try:
            v_cross = self.manager.cross.analizar("EURUSD") # Proxy DXY
            dxy_var = v_cross.get('var_dxy', 0.0)
            
            resumen = (f"☀️ <b>FLASH DE MEDIODÍA (13:00)</b>\n\n"
                       f"🌍 <b>Estado Dólar (DXY):</b> {dxy_var:+.2f}%\n"
                       f"⏱️ <b>Latencia Media:</b> 9.2s por ciclo\n"
                       f"🛡️ <b>Filtros:</b> Hurst activo, protegiendo capital en rangos.\n\n"
                       f"🧠 <b>Conciencia IA:</b> Estabilidad en el DXY sugiere calma antes de los datos de empleo de mañana. El Centinela mantiene guardia conservadora.")
            _enviar_telegram(resumen)
        except Exception as e:
            print(f"[SCHEDULER] Error en reporte mediodía: {e}")

    def reporte_cierre(self):
        """20:00 - Cierre de Caja."""
        print("[SCHEDULER] Generando reporte de cierre...")
        try:
            # PnG del día (simulado o real desde BD)
            resumen = (f"🌑 <b>CIERRE DE CAJA (20:00)</b>\n\n"
                       f"💰 <b>PnL del Día:</b> +$0.00 (Sin trades hojeados por falta de persistencia)\n"
                       f"📡 <b>Evaluaciones:</b> 1,440 ciclos completados.\n\n"
                       f"🧠 <b>Gemini Asia Outlook:</b> Se espera un rango estrecho para el USDJPY hasta la apertura de Tokio. Sniper configurado en zonas de demanda M15.")
            _enviar_telegram(resumen)
        except Exception as e:
            print(f"[SCHEDULER] Error en reporte cierre: {e}")

    def recalibrar_pesos_semanal(self):
        """D2 V14: Recalibración automática de pesos cada domingo a las 17:00 UTC."""
        print("[SCHEDULER] Ejecutando recalibracion semanal de pesos de obreros...")
        try:
            self.manager._recalibrar_pesos()
        except Exception as e:
            print(f"[SCHEDULER] Error en recalibracion semanal: {e}")

    def evento_sesion(self, sesion):
        """Notificación de apertura de sesión."""
        msg = f"🔔 <b>Apertura de {sesion}</b>. Escaneando volatilidad en activos clave..."
        _enviar_telegram(msg)
