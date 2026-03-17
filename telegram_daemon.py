"""
telegram_daemon.py — Daemon de Telegram V2.0 (Proceso Independiente)
Aurum OMNI V15.0

Arquitectura: Proceso completamente independiente del Core y del Hunter.
Monitorizado por heartbeat.py (SHIELD). Se relanza automáticamente si cae.

Al iniciar llama a delete_webhook(drop_pending_updates=True) para limpiar
cualquier sesión de getUpdates activa de instancias anteriores, eliminando
el error telegram.error.Conflict de raíz.
"""
import os
import sys
import asyncio
import psutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).parent.absolute()))

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from config.logging_config import setup_logging, get_logger
from dotenv import load_dotenv

try:
    from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("[DAEMON] ERROR: python-telegram-bot no instalado. Abortando.")
    sys.exit(1)

load_dotenv()
setup_logging("INFO")
logger = get_logger("telegram_daemon")

TOKEN          = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Símbolos válidos para el comando Lupa
_SIMBOLOS_VALIDOS = {
    "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY",
    "GBPJPY", "US30", "US500", "USTEC", "XTIUSD", "XBRUSD",
}

# Estado en memoria — se carga desde DB al iniciar
_modo_silencioso: bool = False


# ------------------------------------------------------------------
# Teclado Principal
# ------------------------------------------------------------------

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["📊 TABLERO GLOBAL", "🩺 TEST DE SALUD"],
        ["🔍 LUPA DE ACTIVO", "📰 RADAR DE NOTICIAS"],
        ["📋 MIS POSICIONES", "📊 RENDIMIENTO HOY"],
        ["⚙️ PARAMETROS", "🗞️ ULTIMAS NOTICIAS"],
        ["🔄 REINICIAR BOT"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _autorizado(update: Update) -> bool:
    autorizado = str(update.effective_chat.id) == ALLOWED_CHAT_ID
    if not autorizado:
        logger.warning(f"Intento de acceso no autorizado desde el Chat ID: {update.effective_chat.id}")
    return autorizado


def _leer_modo_silencio() -> bool:
    """Lee el estado de silencio desde parametros_sistema en BD."""
    try:
        db = DBConnector()
        if db.conectar():
            db.cursor.execute(
                "SELECT valor FROM parametros_sistema WHERE clave = 'TELEGRAM.modo_silencioso' LIMIT 1;"
            )
            row = db.cursor.fetchone()
            db.desconectar()
            return row[0].lower() == "true" if row else False
    except Exception:
        pass
    return False


def _guardar_modo_silencio(activo: bool):
    """Persiste el estado de silencio en parametros_sistema."""
    try:
        db = DBConnector()
        if db.conectar():
            db.cursor.execute("""
                INSERT INTO parametros_sistema (clave, valor)
                VALUES ('TELEGRAM.modo_silencioso', %s)
                ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor;
            """, (str(activo).lower(),))
            db.conn.commit()
            db.desconectar()
    except Exception as e:
        logger.warning(f"No se pudo guardar modo silencio en BD: {e}")


def _get_estado_procesos() -> dict:
    """Detecta qué procesos de Aurum están corriendo."""
    estado = {"core": "❌ CAIDO", "hunter": "❌ CAIDO", "daemon": "✅ ONLINE (este)"}
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            if "python" in proc.info.get("name", "").lower():
                cmd = " ".join(proc.info.get("cmdline", [])).lower()
                if "main.py" in cmd or "manager.py" in cmd:
                    estado["core"] = "✅ ONLINE"
                elif "news_hunter.py" in cmd:
                    estado["hunter"] = "✅ ONLINE"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return estado


def _construir_pulso_nocturno() -> str:
    """Construye el mensaje de resumen diario (02:00 UTC)."""
    lineas = ["🌙 <b>PULSO DE VIDA NOCTURNO — Aurum V15</b>\n"]

    db = DBConnector()
    if db.conectar():
        # Estadísticas del día
        try:
            db.cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) AS ganados,
                    COALESCE(SUM(pnl_usd), 0) AS pnl_neto
                FROM registro_operaciones
                WHERE fecha_apertura::date = CURRENT_DATE
                  AND resultado_final IS NOT NULL;
            """)
            r = db.cursor.fetchone()
            if r:
                total, ganados, pnl = r[0] or 0, r[1] or 0, r[2] or 0.0
                wr = (ganados / total * 100) if total > 0 else 0.0
                pnl_emoji = "📈" if pnl >= 0 else "📉"
                lineas.append(
                    f"📊 <b>Trades hoy:</b> {total} ({ganados}W / {total - ganados}L) | "
                    f"Win Rate: {wr:.1f}% | {pnl_emoji} PnL: ${pnl:+.2f}"
                )
        except Exception:
            pass

        # Noticias procesadas hoy
        try:
            db.cursor.execute(
                "SELECT COUNT(*) FROM raw_news_feed WHERE timestamp::date = CURRENT_DATE;"
            )
            n_noticias = db.cursor.fetchone()[0] or 0
            lineas.append(f"📰 <b>Noticias procesadas:</b> {n_noticias}")
        except Exception:
            pass

        # Siguiente evento macro
        try:
            db.cursor.execute("""
                SELECT titulo, clasificacion FROM regimenes_mercado
                WHERE estado = 'ACTIVO'
                ORDER BY fecha_inicio DESC LIMIT 1;
            """)
            ev = db.cursor.fetchone()
            if ev:
                lineas.append(f"📡 <b>Último evento activo:</b> [{ev[1]}] {ev[0][:60]}")
        except Exception:
            pass

        db.desconectar()

    # Estado de procesos
    proc = _get_estado_procesos()
    lineas.append(
        f"\n🔄 <b>Procesos:</b>\n"
        f"• Core: {proc['core']}\n"
        f"• Hunter: {proc['hunter']}\n"
        f"• Daemon: {proc['daemon']}"
    )

    return "\n".join(lineas)


# ------------------------------------------------------------------
# Comandos
# ------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _autorizado(update):
        return
    await update.message.reply_text(
        "⚡ <b>Aurum Omni V15 — Daemon Telegram V2.0</b>\n\nSeleccioná una acción:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _autorizado(update):
        return
    await _accion_ultimas_noticias(update)


async def cmd_silencio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _autorizado(update):
        return
    global _modo_silencioso
    _modo_silencioso = True
    _guardar_modo_silencio(True)
    await update.message.reply_text(
        "🔕 <b>Modo silencioso activado.</b>\nNo recibirás notificaciones automáticas.\nUsá /despertar para reactivar.",
        parse_mode="HTML",
    )


async def cmd_despertar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _autorizado(update):
        return
    global _modo_silencioso
    _modo_silencioso = False
    _guardar_modo_silencio(False)
    await update.message.reply_text(
        "🔔 <b>Notificaciones automáticas reactivadas.</b>",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# Dispatcher de mensajes de teclado
# ------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _autorizado(update):
        return
    text = update.message.text or ""

    if "TABLERO GLOBAL" in text:
        await _accion_tablero_global(update)
    elif "TEST DE SALUD" in text:
        await _accion_health_check(update)
    elif "LUPA DE ACTIVO" in text:
        context.user_data["esperando_simbolo"] = True
        await update.message.reply_text("🔍 Envíame el símbolo a inspeccionar (ej: XAUUSD):")
    elif "RADAR DE NOTICIAS" in text:
        await _accion_radar_noticias(update)
    elif "ULTIMAS NOTICIAS" in text:
        await _accion_ultimas_noticias(update)
    elif "MIS POSICIONES" in text:
        await _accion_mis_posiciones(update)
    elif "RENDIMIENTO HOY" in text:
        await _accion_rendimiento_hoy(update)
    elif "PARAMETROS" in text:
        await _accion_parametros(update)
    elif "REINICIAR BOT" in text:
        await _accion_reiniciar(update)
    elif context.user_data.get("esperando_simbolo"):
        context.user_data["esperando_simbolo"] = False
        simbolo = text.upper().strip()
        if simbolo not in _SIMBOLOS_VALIDOS:
            await update.message.reply_text(
                f"❌ Símbolo '<code>{simbolo}</code>' no reconocido.\n"
                f"Opciones: {', '.join(sorted(_SIMBOLOS_VALIDOS))}",
                parse_mode="HTML",
            )
            return
        await _accion_lupa_activo(update, simbolo)
    else:
        # Respuesta por defecto para mensajes no reconocidos
        emoji = "🤖"
        saludos = ["hola", "buen dia", "buenas", "que tal", "hello"]
        if any(s in text.lower() for s in saludos):
            await update.message.reply_text(
                f"{emoji} ¡Hola Maikol! Soy el Centinela Aurum. ¿En qué puedo ayudarte hoy?",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"{emoji} No reconozco el comando '<b>{text}</b>'.\n"
                "Usa los botones del menú o escribe /start para ver las opciones.",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )


# ------------------------------------------------------------------
# Acciones de los botones
# ------------------------------------------------------------------

async def _accion_tablero_global(update: Update):
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return
    data = db.get_tablero_global()
    db.desconectar()

    if not data:
        await update.message.reply_text("Sin datos en el Tablero Global.")
        return

    header = "📊 <b>ESTADO GLOBAL DE LA CUADRILLA</b>\n\n"
    table  = "<code>Simb. | Trnd | NLP  | Flow | Vered.</code>\n"
    table += "<code>----------------------------------</code>\n"
    for row in data:
        simbolo  = row["simbolo"].ljust(5)
        trend    = f"{row['trend']:+.2f}"[:5] if row["trend"]    is not None else " N/A "
        nlp      = f"{row['nlp']:+.2f}"[:5]   if row["nlp"]      is not None else " N/A "
        flow     = f"{row['flow']:+.2f}"[:5]   if row["flow"]     is not None else " N/A "
        veredicto = f"{row['veredicto']:+.2f}"[:5] if row["veredicto"] is not None else " N/A "
        table += f"<code>{simbolo} | {trend} | {nlp} | {flow} | {veredicto}</code>\n"
    await update.message.reply_text(header + table, parse_mode="HTML")


async def _accion_health_check(update: Update):
    import time as _t

    pid     = os.getpid()
    proceso = psutil.Process(pid)
    mem_mb  = proceso.memory_info().rss / (1024 * 1024)
    cpu_pct = psutil.cpu_percent(interval=0.1)

    db   = DBConnector()
    t0   = _t.time()
    db_ok = db.conectar()
    db_lat = (_t.time() - t0) * 1000 if db_ok else 0

    core_latido = "N/A"
    if db_ok:
        try:
            db.cursor.execute("SELECT tiempo FROM estado_bot WHERE id = 1;")
            fila = db.cursor.fetchone()
            if fila:
                delta = (datetime.now(timezone.utc) - fila[0]).total_seconds()
                core_latido = f"{delta:.0f}s"
        except Exception:
            pass
        db.desconectar()

    mt5    = MT5Connector()
    mt5_ok = mt5.conectar()
    if mt5_ok:
        mt5.desconectar()

    proc = _get_estado_procesos()

    msg = (
        "🩺 <b>AURUM HEALTH CHECK</b>\n\n"
        f"🖥️ <b>PID Daemon:</b> {pid} | <b>CPU:</b> {cpu_pct}%\n"
        f"🧠 <b>RAM Daemon:</b> {mem_mb:.1f} MB\n"
        f"🗄️ <b>PostgreSQL:</b> {'✅ ONLINE' if db_ok else '❌ OFFLINE'}\n"
        f"⚡ <b>Latencia DB:</b> {db_lat:.1f} ms\n"
        f"📈 <b>MT5 Terminal:</b> {'✅ ONLINE' if mt5_ok else '❌ OFFLINE'}\n"
        f"❤️ <b>Latido Core:</b> {core_latido}\n\n"
        f"🔄 <b>PROCESOS</b>\n"
        f"• Core: {proc['core']}\n"
        f"• Hunter: {proc['hunter']}\n"
        f"• Daemon: {proc['daemon']}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def _accion_lupa_activo(update: Update, simbolo: str):
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return
    detalles = db.get_detalle_activo(simbolo)
    db.desconectar()

    if not detalles:
        await update.message.reply_text(f"No se encontraron datos para {simbolo}.")
        return

    msg = (
        f"🔍 <b>DEEP DIVE: {simbolo}</b>\n\n"
        f"📅 <b>Última captura:</b> {detalles['fecha']}\n"
        f"⚖️ <b>Veredicto:</b> {detalles['veredicto']:+.4f}\n"
        f"📝 <b>Motivo:</b>\n<i>{detalles['motivo']}</i>\n\n"
        f"🧠 <b>Último Pensamiento IA:</b>\n<i>{detalles['comentario_ia']}</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def _accion_ultimas_noticias(update: Update):
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return
    news = db.get_top_news(5)
    db.desconectar()

    if not news:
        await update.message.reply_text("🗞️ No hay noticias en la última hora.")
        return

    msg = "🗞️ <b>ULTIMAS NOTICIAS</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    for n in news:
        msg += f"• <code>{n['fecha'].strftime('%H:%M')}</code>: {n['title']}\n\n"
    await update.message.reply_text(msg, parse_mode="HTML")


async def _accion_radar_noticias(update: Update):
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return
    noticias = db.get_radar_noticias()
    db.desconectar()

    if not noticias:
        await update.message.reply_text("🗞️ Sin novedades en la DB.")
        return

    lineas = ["🗞️ <b>RADAR DE NOTICIAS (Análisis IA)</b>\n"]
    for n in noticias:
        lineas.append(f"<b>[{n['simbolo']}]</b> ({n['fecha'].strftime('%H:%M')}):")
        lineas.append(f"<i>{n['razonamiento']}</i>\n")
    await update.message.reply_text("\n".join(lineas), parse_mode="HTML")


async def _accion_mis_posiciones(update: Update):
    """F5-A: Lista posiciones abiertas en MT5 con PnL flotante."""
    mt5 = MT5Connector()
    if not mt5.conectar():
        await update.message.reply_text("❌ MT5 no disponible.")
        return

    try:
        import MetaTrader5 as mt5_lib
        posiciones = mt5_lib.positions_get()
        acc        = mt5_lib.account_info()
        mt5.desconectar()

        if not posiciones:
            equity_str = f"\n💎 <b>Equity:</b> ${acc.equity:,.2f}" if acc else ""
            await update.message.reply_text(
                f"📋 <b>SIN POSICIONES ABIERTAS</b>{equity_str}",
                parse_mode="HTML",
            )
            return

        msg       = "📋 <b>POSICIONES ABIERTAS</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        pnl_total = 0.0
        for pos in posiciones:
            tipo      = "🟢 COMPRA" if pos.type == 0 else "🔴 VENTA"
            pnl_emoji = "📈" if pos.profit >= 0 else "📉"
            pnl_total += pos.profit
            msg += (
                f"{tipo} <b>{pos.symbol}</b>\n"
                f"• Ticket: #{pos.ticket} | Lotes: {pos.volume}\n"
                f"• Entrada: {pos.price_open:.5f} | Actual: {pos.price_current:.5f}\n"
                f"• SL: {pos.sl:.5f} | TP: {pos.tp:.5f}\n"
                f"• {pnl_emoji} PnL: <b>${pos.profit:+.2f}</b>\n\n"
            )

        pnl_emoji_total = "📈" if pnl_total >= 0 else "📉"
        if acc:
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{pnl_emoji_total} <b>PnL Flotante Total:</b> ${pnl_total:+.2f}\n"
                f"💰 <b>Balance:</b> ${acc.balance:,.2f}\n"
                f"💎 <b>Equity:</b> ${acc.equity:,.2f}"
            )

        await update.message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Error consultando MT5: {e}")


async def _accion_rendimiento_hoy(update: Update):
    """F5-A: Win rate, PnL neto, trades del día."""
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return

    try:
        db.cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) AS ganados,
                SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) AS perdidos,
                COALESCE(SUM(pnl_usd), 0) AS pnl_neto
            FROM registro_operaciones
            WHERE tiempo_entrada::date = CURRENT_DATE
              AND resultado_final IS NOT NULL;
        """)
        stats = db.cursor.fetchone()

        db.cursor.execute("""
            SELECT COUNT(*) FROM registro_operaciones
            WHERE tiempo_entrada::date = CURRENT_DATE AND resultado_final IS NULL;
        """)
        abiertos = db.cursor.fetchone()[0] or 0
        db.desconectar()

        total, ganados, perdidos, pnl_neto = (
            stats[0] or 0, stats[1] or 0, stats[2] or 0, float(stats[3] or 0.0)
        )
        win_rate  = (ganados / total * 100) if total > 0 else 0.0
        pnl_emoji = "📈" if pnl_neto >= 0 else "📉"

        msg = (
            f"📊 <b>RENDIMIENTO HOY</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>Trades cerrados:</b> {total} ({ganados}W / {perdidos}L)\n"
            f"🏆 <b>Win Rate:</b> {win_rate:.1f}%\n"
            f"{pnl_emoji} <b>PnL Neto:</b> ${pnl_neto:+.2f}\n"
            f"🔓 <b>Posiciones abiertas:</b> {abiertos}\n\n"
            f"📅 {datetime.now().strftime('%d-%b-%Y')}"
        )
        await update.message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Error consultando rendimiento: {e}")
        try:
            db.desconectar()
        except Exception:
            pass


async def _accion_parametros(update: Update):
    """F5-A: Ver parámetros del sistema (pesos + Gerente)."""
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return

    try:
        db.cursor.execute("""
            SELECT nombre_parametro, valor FROM parametros_sistema
            WHERE nombre_parametro LIKE 'PESO.%' OR nombre_parametro LIKE 'GERENTE.%'
            ORDER BY nombre_parametro;
        """)
        params = db.cursor.fetchall()
        db.desconectar()

        if not params:
            await update.message.reply_text("⚙️ No hay parámetros configurados en BD.")
            return

        msg = "⚙️ <b>PARAMETROS DEL SISTEMA</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        for nombre_param, valor in params:
            nombre = nombre_param.replace("PESO.", "").replace("GERENTE.", "").replace("_", " ")
            msg += f"• <b>{nombre}:</b> <code>{valor}</code>\n"

        await update.message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Error consultando parámetros: {e}")
        try:
            db.desconectar()
        except Exception:
            pass


async def _accion_reiniciar(update: Update):
    """Reinicia todo el ecosistema python."""
    await update.message.reply_text("🔄 <b>Iniciando secuencia de reinicio total...</b>\nSe apagará Aurum y volverá a encender en unos segundos.", parse_mode="HTML")
    import subprocess
    subprocess.Popen("start /b restart_all.bat", shell=True, cwd=os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------
# Tarea de Pulso Nocturno (02:00 UTC) — F5-C
# ------------------------------------------------------------------

async def _tarea_pulso_nocturno(app: Application):
    """Envía un resumen diario a las 02:00 UTC."""
    logger.info("Tarea de pulso nocturno iniciada.")
    while True:
        try:
            ahora  = datetime.now(timezone.utc)
            target = ahora.replace(hour=2, minute=0, second=0, microsecond=0)
            if ahora >= target:
                target += timedelta(days=1)

            segundos = (target - ahora).total_seconds()
            logger.info(f"Pulso nocturno programado en {segundos/3600:.1f}h.")
            await asyncio.sleep(segundos)

            if _modo_silencioso or not ALLOWED_CHAT_ID:
                continue

            msg = _construir_pulso_nocturno()
            await app.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=msg, parse_mode="HTML")
            logger.info("Pulso nocturno enviado.")

        except asyncio.CancelledError:
            logger.info("Tarea de pulso nocturno cancelada.")
            break
        except Exception as e:
            logger.error(f"Error en pulso nocturno: {e}")
            await asyncio.sleep(3600)


# ------------------------------------------------------------------
# Inicialización — post_init hook
# ------------------------------------------------------------------

async def post_init(app: Application) -> None:
    """
    Se ejecuta dentro del event loop de PTB, antes de que comience el polling.
    1. Elimina sesiones de getUpdates anteriores (fix Conflict error).
    2. Carga el estado de silencio desde BD.
    3. Arranca la tarea de pulso nocturno en background.
    """
    global _modo_silencioso

    # F0-C: Eliminar sesiones fantasma de Telegram
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Sesiones de polling anteriores limpiadas (delete_webhook OK).")
    except Exception as e:
        logger.warning(f"delete_webhook falló (no crítico): {e}")

    # Leer modo silencio desde BD
    _modo_silencioso = _leer_modo_silencio()
    if _modo_silencioso:
        logger.info("Daemon iniciado en MODO SILENCIOSO.")

    # Arrancar pulso nocturno como tarea asyncio en el event loop de PTB
    asyncio.ensure_future(_tarea_pulso_nocturno(app))

    # Notificar inicio al usuario
    if ALLOWED_CHAT_ID:
        try:
            await app.bot.send_message(
                chat_id=ALLOWED_CHAT_ID,
                text="⚡ <b>Centinela Aurum V15 — Online y patrullando.</b>\nUsa los botones para interactuar conmigo.",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar mensaje de inicio: {e}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    # Prevenir instancias duplicadas via Named Mutex en Windows
    if os.name == 'nt':
        import ctypes
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\AurumTelegramDaemonMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.kernel32.CloseHandle(_mutex)
            logger.warning("Ya hay una instancia del Daemon corriendo. Abortando.")
            sys.exit(0)

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado. Daemon abortado.")
        sys.exit(1)

    logger.info("Aurum Telegram Daemon V2.0 iniciando...")

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("news",      cmd_news))
    app.add_handler(CommandHandler("silencio",  cmd_silencio))
    app.add_handler(CommandHandler("despertar", cmd_despertar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Daemon listo. Iniciando polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
