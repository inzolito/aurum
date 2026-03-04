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
                                ticket: int, precio: float,
                                sl: float, tp: float,
                                veredicto: float, v_trend: float, v_nlp: float,
                                balance: float):
    """
    Protocolo Truth-Only: Alerta confirmada con ticket real en MetaTrader.
    Incluye nivel de convicción y detalles de riesgo (ATR).
    """
    conviccion = abs(veredicto) * 100
    pips_sl = abs(precio - sl) # Simplificacion para visualización
    pips_tp = abs(precio - tp)

    prob_exito = 65 + ((conviccion - 45) / (100 - 45)) * (98 - 65)
    prob_exito = max(65, min(98, prob_exito))

    msg = (
        f">> ORDEN CONFIRMADA\n"
        f"Activo: {simbolo} | Ticket: #{ticket}\n"
        f"Accion: {direccion} | Conviccion: {conviccion:.1f}% | Lote: {lotes}\n"
        f"🎯 Probabilidad Est. de Éxito: {prob_exito:.1f}%\n"
        f"Precio: {precio} | SL: {sl:.4f} | TP: {tp:.4f}\n"
        f"Veredicto IA: {veredicto:+.4f} (Trend: {v_trend:+.2f} | NLP: {v_nlp:+.2f})\n"
        f"Balance Actual: ${balance:,.2f}"
    )
    _print_alerta("ORDEN CONFIRMADA", msg.replace("\n", " | "))
    
    _enviar_telegram(
        f"🟢 <b>ORDEN CONFIRMADA</b>\n"
        f"<b>Activo:</b> {simbolo} | <b>Ticket:</b> #{ticket}\n"
        f"<b>Convicción:</b> {conviccion:.1f}% -> <b>Lote Asignado:</b> {lotes}\n"
        f"🎯 <b>Probabilidad Est. de Éxito:</b> {prob_exito:.1f}%\n"
        f"<b>Acción:</b> {direccion} @ {precio}\n"
        f"<b>Riesgo:</b> SL: {sl:.4f} | TP: {tp:.4f}\n"
        f"<b>Veredicto:</b> {veredicto:+.4f} (Trend: {v_trend:+.2f} | NLP: {v_nlp:+.2f})\n"
        f"📊 <b>Hurst:</b> {kwargs.get('hurst_h', 'N/A')} | <b>Estado:</b> {kwargs.get('hurst_estado', 'N/A')}\n"
        f"📍 <b>MAPA DE VOLUMEN</b>\n"
        f"POC: {kwargs.get('vol_poc', 'N/A')} | VA: {kwargs.get('vol_va', 'N/A')}\n"
        f"Contexto: {kwargs.get('vol_ctx', 'N/A')}\n"
        f"Ajuste: {kwargs.get('vol_ajuste', 'N/A')}\n\n"
        f"<b>Balance Actual:</b> ${balance:,.2f}"
    )


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


def notificar_kill_switch_activado(equity: float):
    """Alerta roja de Kill-Switch por drawdown."""
    msg = f"🚨 MAX DRAWDOWN ALCANZADO (${equity:,.2f}). SISTEMA HIBERNANDO HASTA MAÑANA."
    _print_alerta("KILL-SWITCH", msg)
    _enviar_telegram(f"<b>🚨 MAX DRAWDOWN ALCANZADO</b>\n\n"
                     f"El Balance flotante ha caído por debajo de los límites de riesgo ($2,850).\n"
                     f"<b>Equity actual:</b> ${equity:,.2f}\n\n"
                     f"<i>El sistema ha cerrado todas las posiciones y ha entrado en hibernación.</i>")

def notificar_proximidad(simbolo: str, veredicto: float, hurst_h: float, hurst_estado: str, vol_map: dict):
    """Filtro de pre-alerta: Aviso de proximidad al gatillo (0.38 - 0.44)."""
    msg = f"⚠️ PROXIMIDAD DETECTADA en {simbolo} | Veredicto: {abs(veredicto):.4f}"
    print(f"[NOTIFIER] {msg}")
    _enviar_telegram(f"⚠️ <b>PROXIMIDAD DETECTADA</b>\n"
                     f"<b>Activo:</b> {simbolo} | <b>Veredicto:</b> {abs(veredicto):.4f}\n"
                     f"📊 <b>Hurst:</b> {hurst_h:.4f} | <b>Estado:</b> {hurst_estado}\n"
                     f"📍 <b>MAPA DE VOLUMEN</b>\n"
                     f"POC: {vol_map['poc']} | VAH/VAL: {vol_map['va']}\n"
                     f"Contexto: {vol_map['contexto']}\n"
                     f"Ajuste: {vol_map['ajuste']}\n\n"
                     f"<b>Estado:</b> El Centinela está quitando el seguro. Esperando confirmación final (+0.45).")

def notificar_oportunidad_detectada(simbolo: str, veredicto: float):
    """Reporte de Gatillo: Señal en radar pero sin llegar al umbral de ejecución."""
    emoji = "🔭" if veredicto > 0 else "📡"
    msg = f"🔍 Oportunidad detectada en {simbolo} | Confianza: {abs(veredicto):.4f} | Esperando +0.45"
    print(f"[NOTIFIER] {msg}")
    _enviar_telegram(f"{emoji} <b>Oportunidad Detectada -- {simbolo}</b>\n"
                     f"Confianza: {abs(veredicto):.4f}\n"
                     f"Estado: <i>Esperando +0.45 para gatillar.</i>")

def notificar_error_critico(modulo: str, mensaje: str):
    """Alerta de error grave (desconexion MT5, fallo de BD, etc.)."""
    msg = f"ERROR CRITICO en {modulo}: {mensaje}"
    _print_alerta("ERROR CRITICO", msg)
    _enviar_telegram(f"<b>ERROR CRITICO</b>\nModulo: {modulo}\n{mensaje}")


def notificar_rechazo_broker(simbolo: str, retcode: int, causa: str):
    """
    Se dispara cuando el broker rechaza una orden en el ciclo final de envío.
    """
    msg = f"RECHAZO BROKER — {simbolo} (Err {retcode}): {causa}"
    _print_alerta("ALERTA ROJA", msg)
    _enviar_telegram(
        f"🔴 <b>FALLO DE EJECUCIÓN</b>\n"
        f"<b>Activo:</b> {simbolo} | <b>Error:</b> {retcode}\n"
        f"<b>Descripción:</b> {causa}\n"
        f"<b>Acción:</b> La orden ha sido descartada. Revisar terminal."
    )


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
