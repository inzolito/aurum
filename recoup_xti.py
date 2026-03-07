import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager
import time

def recoup_xti():
    print("Iniciando RECOUP REPORT para XTIUSD...")
    db = DBConnector()
    mt5 = MT5Connector()
    
    if not db.conectar() or not mt5.conectar():
        print("Error de conexión.")
        return
        
    manager = Manager(db, mt5)
    simbolo_interno = "XTIUSD"
    
    # 1. Obtener ID de la BD para el NLP
    # Obtenemos los activos para buscar el ID de XTIUSD
    activos = db.obtener_activos_patrullaje()
    id_activo = next((a['id'] for a in activos if a['simbolo'] == simbolo_interno), None)
    
    # 2. Ejecutamos los obreros como lo hace el bloque de volatilidad
    print("Recopilando datos técnicos actuales...")
    v_trend_tmp = manager.trend.analizar(simbolo_interno)
    v_flow_tmp = manager.flow.analizar(simbolo_interno)
    v_volume_tmp = manager.volume.analizar(simbolo_interno)
    v_cross_tmp = manager.cross.analizar(simbolo_interno)
    v_struct_tmp = manager.structure.analizar(simbolo_interno)
    res_hurst_tmp = manager.hurst.analizar(simbolo_interno)
    
    print("Consultando NLP forzar_refresh=True...")
    voto_emg = manager.nlp.analizar(simbolo_interno, id_activo=id_activo, forzar_refresh=True)
    
    razon_txt = manager.nlp.obtener_razonamiento(simbolo_interno)
    contexto_bloque = f"\n🧠 CONTEXTO (Post-Crash V9.0):\n\"{razon_txt}\"\n"
    
    veredicto_tmp = round(
        (v_trend_tmp * 0.30) + (voto_emg * 0.20) + 
        (v_volume_tmp['voto'] * 0.15) + (v_flow_tmp * 0.10) + 
        (v_cross_tmp['voto'] * 0.15) + (v_struct_tmp['voto'] * 0.10), 4
    )
    
    direccion_flecha = "🔼" if veredicto_tmp > 0 else "🔽"
    
    msg_vol = (
        f"🚨 <b>¡REPORTE RECOUP (V9.0 SANADA) - {simbolo_interno}!</b>\n"
        f"📈 Movimiento: <b>1 MINUTO</b> ({direccion_flecha})\n"
        f"⚡ Intensidad Original: <b>7.0x</b> sobre el promedio.\n"
        f"{contexto_bloque}\n"
        f"📊 ESTADO DE LA CUADRILLA:\n"
        f"📈 Trend: {v_trend_tmp:+.2f} | 🧠 NLP: {voto_emg:+.2f}\n"
        f"📍 Volume: {v_volume_tmp['voto']:+.2f} | 🌍 Cross: {v_cross_tmp['voto']:+.2f}\n"
        f"⚡ Flow: {v_flow_tmp:+.2f} | 🛡️ Hurst: {res_hurst_tmp['estado']} (H: {res_hurst_tmp['h']:.2f})\n"
        f"🎯 Sniper: {v_struct_tmp['voto']:+.2f}\n\n"
        f"<b>Veredicto Final:</b> {veredicto_tmp:+.2f} / 0.45"
    )
    
    from config.notifier import _enviar_telegram
    print("Enviando a Telegram...")
    _enviar_telegram(msg_vol)
    print("Reporte enviado.")
    
    db.desconectar()
    mt5.desconectar()

if __name__ == "__main__":
    recoup_xti()
