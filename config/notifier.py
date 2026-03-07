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


def _enviar_imagen_telegram(caption: str, image_path: str):
    """Envía una imagen a Telegram usando multipart/form-data (raw urllib)."""
    if not _TELEGRAM_ACTIVO or not os.path.exists(image_path):
        return
    
    try:
        import uuid
        boundary = uuid.uuid4().hex
        url = f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendPhoto"
        
        with open(image_path, "rb") as f:
            img_data = f.read()
            
        # Construir cuerpo multipart manualmente
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            f"{_TELEGRAM_CHAT_ID}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{caption}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
            f"HTML\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(image_path)}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
        
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        urllib.request.urlopen(req, timeout=15)
        
    except Exception as e:
        print(f"[NOTIFIER] Error enviando imagen: {e}")


# ------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------

def notificar_orden_ejecutada(simbolo: str, direccion: str, lotes: float, 
                                ticket: int, precio: float,
                                sl: float, tp: float,
                                veredicto: float, v_trend: float, v_nlp: float,
                                balance: float, **kwargs):
    """
    Protocolo Truth-Only: Alerta confirmada con ticket real en MetaTrader.
    Incluye nivel de convicción y detalles de riesgo (ATR).
    """
    conviccion = abs(veredicto) * 100
    pips_sl = abs(precio - sl) # Simplificacion para visualización
    pips_tp = abs(precio - tp)

    prob_exito = 65 + ((conviccion - 45) / (100 - 45)) * (98 - 65)
    prob_exito = max(65, min(98, prob_exito))

    pensamiento_gemini = kwargs.get('gemini_thought', "Análisis en tiempo real: El mercado muestra signos de agotamiento institucional, vigilando reversión.")

    msg = (
        f">> ORDEN CONFIRMADA\n"
        f"Activo: {simbolo} | Ticket: #{ticket}\n"
        f"Accion: {direccion} | Conviccion: {conviccion:.1f}% | Lote: {lotes}\n"
        f"🎯 Probabilidad Est. de Éxito: {prob_exito:.1f}%\n"
        f"Precio: {precio} | SL: {sl:.4f} | TP: {tp:.4f}\n"
        f"Veredicto IA: {veredicto:+.4f} (Trend: {v_trend:+.2f} | NLP: {v_nlp:+.2f})\n"
        f"Balance Actual: ${balance:,.2f}"
    )
    _print_alerta("ORDEN CONFIRMADA", f"{simbolo} {direccion} {lotes} @ {precio}")
    
    msg_tg = _build_msg_orden(simbolo, direccion, lotes, ticket, precio, sl, tp, veredicto, v_trend, v_nlp, balance, **kwargs)
    
    image_path = kwargs.get('image_path')
    if image_path:
        _enviar_imagen_telegram(msg_tg, image_path)
    else:
        _enviar_telegram(msg_tg)

def _build_msg_orden(simbolo, direccion, lotes, ticket, precio, sl, tp, veredicto, v_trend, v_nlp, balance, **kwargs):
    conviccion = abs(veredicto) * 100
    prob_exito = 65 + ((conviccion - 45) / (100 - 45)) * (98 - 65)
    prob_exito = max(65, min(98, prob_exito))
    pensamiento_gemini = kwargs.get('gemini_thought', "Análisis en tiempo real: El mercado muestra signos de agotamiento institucional, vigilando reversión.")
    
    return (
        f"🟢 <b>ORDEN CONFIRMADA</b>\n"
        f"<b>Activo:</b> {simbolo} | <b>Ticket:</b> #{ticket}\n"
        f"<b>Convicción:</b> {conviccion:.1f}% -> <b>Lote:</b> {lotes}\n"
        f"🎯 <b>Probabilidad Est. de Éxito:</b> {prob_exito:.1f}%\n"
        f"<b>Acción:</b> {direccion} @ {precio}\n"
        f"<b>Riesgo:</b> SL: {sl:.4f} | TP: {tp:.4f}\n"
        f"<b>Veredicto Final:</b> {veredicto:+.4f}\n\n"
        f"🗳️ <b>DETALLE DE VOTACIÓN:</b>\n"
        f"• Trend: {v_trend:+.2f} (40%)\n"
        f"• NLP IA: {v_nlp:+.2f} (30%)\n"
        f"• Flow: {kwargs.get('v_flow', 0.0):+.2f} (15%)\n"
        f"• Sniper: {kwargs.get('smc_voto_raw', 0.0):+.2f} (15%)\n\n"
        f"📉 <b>FILTROS TÉCNICOS:</b>\n"
        f"• Vol: {kwargs.get('v_vol', 0.0):+.2f} | Cross: {kwargs.get('v_cross', 0.0):+.2f}\n"
        f"• Hurst: {kwargs.get('v_hurst', 0.0):+.2f}\n\n"
        f"📊 <b>CONTEXTO:</b> {kwargs.get('hurst_estado', 'N/A')}\n"
        f"🎯 <b>ZONA SNIPER (SMC)</b>\n"
        f"OB: {kwargs.get('smc_ob', 'N/A')}\n"
        f"Estructura: {kwargs.get('smc_estado', 'N/A')}\n"
        f"Sniper V: {kwargs.get('smc_veredicto', 'N/A')}\n\n"
        f"⚖️ <b>Fuerza Dominante:</b> {kwargs.get('fuerza_dominante', 'N/A')}\n\n"
        f"🧠 <b>ANÁLISIS DE CONCIENCIA IA</b>\n"
        f"<i>{kwargs.get('gemini_thought', 'Análisis macro dinámico...')}</i>\n\n"
        f"💰 Balance actual: {balance:,.2f} USD"
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

def notificar_proximidad(simbolo: str, veredicto: float, hurst_h: float, hurst_estado: str, vol_map: dict, cross_map: dict, v_struct: dict = None, **kwargs):
    """Filtro de pre-alerta: Aviso de proximidad al gatillo (0.38 - 0.44)."""
    msg = f"⚠️ PROXIMIDAD DETECTADA en {simbolo} | Veredicto: {abs(veredicto):.4f}"
    print(f"[NOTIFIER] {msg}")
    
    _print_alerta("PROXIMIDAD", f"{simbolo} {veredicto:+.4f}")

    msg_tg = _build_msg_proximidad(simbolo, veredicto, hurst_h, hurst_estado, vol_map, cross_map, v_struct, **kwargs)

    image_path = kwargs.get('image_path')
    if image_path:
        _enviar_imagen_telegram(msg_tg, image_path)
    else:
        _enviar_telegram(msg_tg)

def _check_impulse_radar(cross_map: dict) -> str:
    """V10.0: Genera un encabezado prioritario si el Petróleo o el VIX explotan."""
    oil_var = cross_map.get('oil', 0.0)
    vix_var = cross_map.get('vix', 0.0)
    
    alertas = []
    if abs(oil_var) >= 2.0:
        alertas.append(f"🛢️ <b>IMPULSO PETRÓLEO: {oil_var:+.2f}%</b>")
    if abs(vix_var) >= 3.0:
        alertas.append(f"📉 <b>IMPULSO VIX (MIEDO): {vix_var:+.2f}%</b>")
        
    if alertas:
        header = "🚨 <b>RADAR DE IMPULSO - PRIORIDAD MÁXIMA</b>\n"
        header += "\n".join(alertas) + "\n\n"
        # Convertimos a Rojo/Negrita usando tags (HTML parse_mode)
        # Nota: Telegram no tiene tag <color>, usamos <b> y emoticonos para impacto visual
        return header
    return ""

def _build_msg_proximidad(simbolo, veredicto, hurst_h, hurst_estado, vol_map, cross_map, v_struct, **kwargs):
    impulse_header = _check_impulse_radar(cross_map)
    bs_alert = "🚨 <b>ESTADO DE EMERGENCIA: VOLATILIDAD EXTREMA</b>\n" if cross_map['black_swan'] else ""
    pensamiento_gemini = kwargs.get('gemini_thought', "Estructura de mercado detectada: El precio busca mitigar zonas de liquidez pendientes.")

    # Datos de estructura
    smc_ob = v_struct['ob_precio'] if v_struct else "N/A"
    smc_estado = v_struct['estado_smc'] if v_struct else "N/A"
    smc_v = v_struct['sniper_veredicto'] if v_struct else "N/A"

    return (f"{impulse_header}"
              f"⚠️ <b>PROXIMIDAD DETECTADA</b>\n"
              f"{bs_alert}"
              f"<b>Activo:</b> {simbolo} | <b>Veredicto:</b> {abs(veredicto):.4f}\n"
              f"📊 <b>Hurst:</b> {hurst_h:.4f} | <b>Estado:</b> {hurst_estado}\n"
              f"📍 <b>MAPA DE VOLUMEN</b>\n"
              f"POC: {vol_map['poc']} | VA: {vol_map['va']}\n"
              f"🌍 <b>SENSORES GLOBALES</b>\n"
              f"DXY: {cross_map['dxy']}% | SPX: {cross_map['spx']}%\n"
              f"VIX: {cross_map.get('vix', 0.0):+.2f}% | OIL: {cross_map.get('oil', 0.0):+.2f}%\n"
              f"Divergencia: {cross_map['divergencia']}\n\n"
              f"🎯 <b>ZONA SNIPER (SMC)</b>\n"
              f"Order Block: {smc_ob}\n"
              f"Estructura: {smc_estado}\n"
              f"Veredicto Sniper: {smc_v}\n\n"
              f"⚖️ <b>Fuerza Dominante:</b> {kwargs.get('fuerza_dominante', 'N/A')}\n\n"
              f"🧠 <b>ANÁLISIS DE CONCIENCIA IA</b>\n"
              f"<i>{pensamiento_gemini}</i>\n\n"
              f"<b>Estado:</b> El Centinela { 'está en ALERTA MÁXIMA (+0.60)' if cross_map['black_swan'] else 'está quitando el seguro (+0.45)' }.")

def notificar_error_market_watch(simbolo: str):
    """Alerta roja si un activo no es visible en la terminal."""
    msg = f"🚨 ERROR DE MARKET WATCH: Símbolo {simbolo} no visible en la terminal."
    print(f"[NOTIFIER] {msg}")
    _enviar_telegram(f"🚨 <b>ERROR DE MARKET WATCH</b>\n"
                     f"El símbolo <b>{simbolo}</b> no está respondiendo en la terminal.\n\n"
                     f"<i>El Centinela no puede patrullar este activo hasta que se resuelva la conexión.</i>")

def notificar_oportunidad_detectada(simbolo: str, veredicto: float, **kwargs):
    """Reporte de Gatillo: Señal en radar pero sin llegar al umbral de ejecución."""
    emoji = "🔭" if veredicto > 0 else "📡"
    msg = f"🔍 Oportunidad detectada en {simbolo} | Confianza: {abs(veredicto):.4f} | Esperando +0.45"
    print(f"[NOTIFIER] {msg}")
    _enviar_telegram(f"{emoji} <b>Oportunidad Detectada -- {simbolo}</b>\n"
                     f"<b>Confianza:</b> {abs(veredicto)*100:.1f}%\n"
                     f"⚖️ <b>Fuerza Dominante:</b> {kwargs.get('fuerza_dominante', 'N/A')}\n\n"
                     f"<i>Monitoreando persistencia...</i>")

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
                  f"Aurum Omni V1.0 OPERATIVO | {len(activos)} activos | Umbral: 0.45 | Ciclo: 60s")
    _enviar_telegram(
        f"<b>Aurum Omni V1.0 Operativo.</b>\n"
        f"Patrullando {len(activos)} activos en condiciones reales.\n"
        f"Umbral: 0.45 | Ciclo: 60s\n\n"
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


def notificar_conciencia_ia(activo, sentimiento, razonamiento, status_obreros):
    """
    Bitácora de Guerra V7.7: Envía el 'Pulso de Conciencia' de la IA.
    """
    emoji = "🔴" if sentimiento < -0.3 else "🟢" if sentimiento > 0.3 else "⚪"
    msg = (
        f"🧠 <b>PENSAMIENTO IA [{activo}]</b>\n\n"
        f"{emoji} <b>Sentimiento:</b> {sentimiento:+.2f}\n"
        f"💬 <b>Justificación:</b> {razonamiento}\n\n"
        f"🎯 <b>Estado de Obreros:</b>\n"
        f"• {status_obreros}\n"
    )
    _enviar_telegram(msg)


def notificar_explicacion_ruido(motivo_gemini):
    """
    Bitácora de Guerra V7.7: Explica por qué el bot sigue fuera debido al ruido.
    """
    msg = (
        f"🛡️ <b>REPORTE DE SIN-ACCIÓN (Hurst Noise)</b>\n\n"
        f"Maikol, sigo fuera. {motivo_gemini}\n\n"
        f"<i>El capital se mantiene blindado esperando una tendencia persistente.</i>"
    )
    _enviar_telegram(msg)


def notificar_mercado_cerrado(simbolo: str):
    """Protocolo Gatekeeper V13.0: Mercado cerrado por el broker."""
    msg = f"🌙 {simbolo} en pausa: Mercado Cerrado por el Broker. Reintentando en la próxima sesión."
    print(f"[GATEKEEPER] {msg}")
    _enviar_telegram(f"🌙 <b>{simbolo} en pausa</b>\n\nMercado Cerrado por el Broker. Reintentando en la próxima sesión.")


def notificar_alerta_volatilidad_escalonada(simbolo, porcentaje, precio):
    """Fase V14.0: Alerta de volatilidad escalonada."""
    emoji = "🔥" if abs(porcentaje) >= 10 else "⚠️"
    direccion = "SUBIENDO" if porcentaje > 0 else "CAYENDO"
    msg = (
        f"{emoji} <b>MOVIMIENTO BRUSCO: {simbolo}</b>\n\n"
        f"El activo está <b>{direccion}</b> un <b>{abs(porcentaje):.1f}%</b> hoy.\n"
        f"Precio Actual: <code>{precio}</code>\n\n"
        f"<i>Nivel de alerta cruzado. El bot sigue monitoreando.</i>"
    )
    _print_alerta("VOLATILIDAD", f"{simbolo} {porcentaje:+.1f}% @ {precio}")
    _enviar_telegram(msg)
