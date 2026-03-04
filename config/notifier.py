"""
config/notifier.py — Sistema de Notificaciones de Aurum Bot
Modo actual: PRINT de alta prioridad + Telegram opcional vía .env.

Para activar Telegram:
  1. Crea un bot con @BotFather en Telegram y obtén el TOKEN.
  2. Obtén tu CHAT_ID enviando un mensaje al bot y consultando:
     https://api.telegram.org/bot<TOKEN>/getUpdates
  3. Añade las variables al .env:
     TELEGRAM_BOT_TOKEN=xxxxxx:xxxxxxxxxxxxxxxxx
     TELEGRAM_CHAT_ID=123456789
"""
import os
import urllib.request
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

_TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID",   "")
_TELEGRAM_ACTIVO  = bool(_TELEGRAM_TOKEN and _TELEGRAM_CHAT_ID)


def _print_alerta(tipo: str, mensaje: str):
    """Imprime en consola con formato de alta prioridad."""
    linea = "!" * 60
    print(f"\n{linea}")
    print(f"  [{tipo}] {mensaje}")
    print(f"{linea}\n")


def _enviar_telegram(mensaje: str):
    """Envía un mensaje vía Telegram Bot API (sin librerías externas)."""
    if not _TELEGRAM_ACTIVO:
        return
    try:
        url  = f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": _TELEGRAM_CHAT_ID,
                                       "text": mensaje, "parse_mode": "HTML"}).encode()
        req  = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[NOTIFIER] Advertencia: Telegram no disponible ({e})")


# ------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------

def notificar_orden_ejecutada(simbolo: str, direccion: str, lotes: float,
                               veredicto: float, motivo: str):
    """
    Alerta de MÁXIMA PRIORIDAD — se dispara cuando el Manager ejecuta una orden real.
    """
    msg = (
        f">> ORDEN EJECUTADA\n"
        f"Símbolo  : {simbolo}\n"
        f"Dirección: {direccion}\n"
        f"Lotes    : {lotes}\n"
        f"Veredicto: {veredicto:+.4f}\n"
        f"Motivo   : {motivo[:200]}"
    )
    _print_alerta("ORDEN EJECUTADA", msg.replace("\n", " | "))
    _enviar_telegram(f"<b>ORDEN EJECUTADA -- {simbolo}</b>\n"
                     f"Dirección: {direccion} | Lotes: {lotes}\n"
                     f"Veredicto: {veredicto:+.4f}")


def notificar_zona_caliente(simbolo: str, veredicto: float,
                             v_trend: float, v_nlp: float, v_flow: float):
    """
    Alerta de observación — veredicto entre 0.50 y el umbral de disparo (0.65).
    El bot no opera aún, pero la señal está calentando.
    """
    direccion = "COMPRA" if veredicto > 0 else "VENTA"
    msg = (
        f"ZONA CALIENTE -- {simbolo}\n"
        f"Veredicto {veredicto:+.4f} supera 0.50 -> observar para {direccion}\n"
        f"Trend={v_trend:+.2f}  NLP={v_nlp:+.2f}  Flow={v_flow:+.2f}"
    )
    _print_alerta("ZONA CALIENTE", msg.replace("\n", " | "))
    _enviar_telegram(f"<b>ZONA CALIENTE -- {simbolo}</b>\n"
                     f"Veredicto: {veredicto:+.4f} -> senal de {direccion}\n"
                     f"Trend={v_trend:+.2f} | NLP={v_nlp:+.2f} | Flow={v_flow:+.2f}")


def notificar_error_critico(modulo: str, mensaje: str):
    """Alerta de error grave (desconexion MT5, fallo de BD, etc.)."""
    msg = f"ERROR CRITICO en {modulo}: {mensaje}"
    _print_alerta("ERROR CRITICO", msg)
    _enviar_telegram(f"<b>ERROR CRITICO</b>\nModulo: {modulo}\n{mensaje}")
