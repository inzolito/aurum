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


def notificar_inicio(activos: list):
    """
    Mensaje de bienvenida al arrancar el sistema.
    Se dispara una sola vez al iniciar main.py.
    """
    lista = " | ".join(activos)
    _print_alerta("SISTEMA INICIADO",
                  f"Aurum Omni V1.0 OPERATIVO | {len(activos)} activos | Umbral: 0.65 | Ciclo: 60s")
    _enviar_telegram(
        f"<b>Aurum Omni V1.0 Operativo.</b>\n"
        f"Patrullando {len(activos)} activos en condiciones reales.\n"
        f"Umbral: 0.65 | Ciclo: 60s\n\n"
        f"<b>Activos:</b> {lista}\n\n"
        f"Centinela apostado, Maikol!"
    )


def notificar_divergencia(simbolo: str, v_trend: float, v_nlp: float):
    """
    Alerta crítica de divergencia extrema entre lectura técnica (Trend) y macro (IA).
    Bloquea operación por seguridad.
    """
    msg = f"DIVERGENCIA: Precio volando pero IA neutral o contraria. Operacion bloqueada por seguridad."
    _print_alerta("ALERTA DIVERGENCIA", f"{simbolo} | Trend: {v_trend:+.2f} | IA: {v_nlp:+.2f}")
    _enviar_telegram(
        f"⚠️ <b>DIVERGENCIA DETECTADA -- {simbolo}</b>\n\n"
        f"<b>Trend:</b> {v_trend:+.2f} (Técnico volando)\n"
        f"<b>IA:</b> {v_nlp:+.2f} (Macro neutral/contrario)\n\n"
        f"<i>Operación bloqueada por seguridad.</i>"
    )


def notificar_resumen_horario(ciclo: int, activos: list,
                               ciclos_hora: int, ordenes_hora: int,
                               uptime_minutos: int):
    """
    Pulso de vida enviado cada 60 ciclos (~1 hora).
    Confirma que el bot sigue corriendo y resume la actividad reciente.
    """
    import time as _t
    hora_local = _t.strftime("%H:%M:%S")
    lista = " | ".join(activos)
    horas = uptime_minutos // 60
    _print_alerta("PULSO HORARIO",
                  f"Ciclo #{ciclo} | Uptime: {uptime_minutos}min | "
                  f"Evaluaciones: {ciclos_hora} | Ordenes: {ordenes_hora}")
    _enviar_telegram(
        f"<b>Aurum — Pulso Horario</b> ({hora_local})\n\n"
        f"Sistema OPERATIVO\n"
        f"Uptime: {horas}h {uptime_minutos % 60}min | Ciclo: #{ciclo}\n"
        f"Activos patrullados: {len(activos)}\n"
        f"Evaluaciones en la hora: {ciclos_hora}\n"
        f"Ordenes ejecutadas en la hora: {ordenes_hora}\n\n"
        f"<b>Activos:</b> {lista}"
    )
