import os
import sys
import psutil
import asyncio
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager

try:
    from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("[TELEGRAM] ERROR: python-telegram-bot no instalado.")
    sys.exit(1)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- KEYBOARD ---
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📊 TABLERO GLOBAL"), KeyboardButton("🩺 TEST DE SALUD")],
        [KeyboardButton("🔍 LUPA DE ACTIVO"), KeyboardButton("📰 RADAR DE NOTICIAS")],
        [KeyboardButton("🗞️ ULTIMAS NOTICIAS (/news)")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)

# --- COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el teclado principal."""
    print(f"[TELEGRAM] Recibido /start de ChatID: {update.effective_chat.id}")
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID:
        print(f"[TELEGRAM] Bloqueado: ChatID {update.effective_chat.id} no coincide con {ALLOWED_CHAT_ID}")
        return
    await update.message.reply_text(
        "⚡ <b>Aurum Omni V11.2 - Traceability & Memory</b>\nSeleccione una acción:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /news: Muestra las últimas 5 noticias crudas."""
    await get_news_report(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones interactivos."""
    if str(update.effective_chat.id) != ALLOWED_CHAT_ID: return
    text = update.message.text

    if "TABLERO GLOBAL" in text:
        await tablero_global(update, context)
    elif "TEST DE SALUD" in text:
        await health_check(update, context)
    elif "LUPA DE ACTIVO" in text:
        await update.message.reply_text("🔍 Envíame el símbolo (ej: XAUUSD) para inspeccionarlo:")
        context.user_data['esperando_simbolo'] = True
    elif "RADAR DE NOTICIAS" in text:
        await radar_noticias(update, context)
    elif "ULTIMAS NOTICIAS" in text:
        await get_news_report(update, context)
    elif context.user_data.get('esperando_simbolo'):
        context.user_data['esperando_simbolo'] = False
        await lupa_activo(update, context, text.upper())

# --- ACCIONES ---
async def get_news_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de comunicación con la base de datos.")
        return
    
    news = db.get_top_news(5)
    db.desconectar()

    if not news:
        await update.message.reply_text("🗞️ No hay noticias crudas registradas en la última hora.")
        return

    msg = "🗞️ <b>ÚLTIMAS NOTICIAS CRUDAS (Trazabilidad)</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    for n in news:
        msg += f"• <code>{n['fecha'].strftime('%H:%M')}</code>: {n['title']}\n\n"
    
    await update.message.reply_text(msg, parse_mode="HTML")
    await update.message.reply_text("📊 Consultando Tablero Global (Direct DB)...")
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
    table = "<code>Simb. | Trnd | NLP  | Flow | Vered.</code>\n"
    table += "<code>----------------------------------</code>\n"
    
    for row in data:
        simbolo = row['simbolo'].ljust(5)
        trend = f"{row['trend']:+.2f}"[:5] if row['trend'] is not None else " N/A "
        nlp = f"{row['nlp']:+.2f}"[:5] if row['nlp'] is not None else " N/A "
        flow = f"{row['flow']:+.2f}"[:5] if row['flow'] is not None else " N/A "
        veredicto = f"{row['veredicto']:+.2f}"[:5] if row['veredicto'] is not None else " N/A "
        
        table += f"<code>{simbolo} | {trend} | {nlp} | {flow} | {veredicto}</code>\n"
    
    msg = header + table
    await update.message.reply_text(msg, parse_mode="HTML")

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # PID y RAM
    pid = os.getpid()
    proceso = psutil.Process(pid)
    mem_mb = proceso.memory_info().rss / (1024 * 1024)
    cpu_pct = psutil.cpu_percent(interval=0.1)
    
    # DB Latency
    db = DBConnector()
    import time
    t0 = time.time()
    db_ok = db.conectar()
    db_lat = (time.time() - t0) * 1000 if db_ok else 0
    if db_ok: db.desconectar()

    # MT5
    mt5 = MT5Connector()
    mt5_ok = mt5.conectar()
    if mt5_ok: mt5.desconectar()

    msg = (
        "🩺 <b>AURUM HEALTH CHECK</b>\n\n"
        f"🖥️ <b>PID:</b> {pid} | <b>CPU:</b> {cpu_pct}%\n"
        f"🧠 <b>RAM Bot:</b> {mem_mb:.1f} MB\n"
        f"🗄️ <b>PostgreSQL:</b> {'✅ ONLINE' if db_ok else '❌ OFFLINE'}\n"
        f"⚡ <b>Latencia DB:</b> {db_lat:.1f} ms\n"
        f"📈 <b>MT5 Terminal:</b> {'✅ ONLINE' if mt5_ok else '❌ OFFLINE'}\n"
        f"🌡️ <b>Surface Pro 5:</b> Óptima"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def lupa_activo(update: Update, context: ContextTypes.DEFAULT_TYPE, simbolo: str):
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
        f"📝 <b>Estructura/Motivo:</b>\n<i>{detalles['motivo']}</i>\n\n"
        f"🧠 <b>Último Pensamiento IA:</b>\n<i>{detalles['comentario_ia']}</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def radar_noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = DBConnector()
    if not db.conectar():
        await update.message.reply_text("❌ Error de conexión a DB.")
        return

    noticias = db.get_radar_noticias()
    db.desconectar()

    if not noticias:
        await update.message.reply_text("🗞️ Sin novedades en la DB.")
        return

    msg_lines = ["🗞️ <b>RADAR DE NOTICIAS (Cero Tokens)</b>\n"]
    for n in noticias:
        msg_lines.append(f"<b>[{n['simbolo']}]</b> ({n['fecha'].strftime('%H:%M')}):")
        msg_lines.append(f"<i>{n['razonamiento']}</i>\n")

    await update.message.reply_text("\n".join(msg_lines), parse_mode="HTML")

# --- MAIN RUNNER ---
def run_telegram_bot():
    if not TOKEN:
        print("[TELEGRAM] No hay token. Bot deshabilitado.")
        return
    
    print("[TELEGRAM] Iniciando Bot de Interfaz Interactiva V10.0...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run polling no-bloqueante si se integra con otro event loop, 
    # o bloqueante si corre como proceso separado. Lo haremos bloqueante aquí para run in thread.
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    run_telegram_bot()
