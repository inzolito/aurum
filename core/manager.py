import sys
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
import MetaTrader5 as mt5

sys.path.append(str(Path(__file__).parent.parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.risk_module import RiskModule
from workers.worker_trend import TrendWorker
from workers.worker_nlp import NLPWorker
from workers.worker_flow import OrderFlowWorker
from workers.worker_hurst import HurstWorker
from workers.worker_volume import VolumeWorker
from workers.worker_cross import CrossWorker
from workers.worker_structure import StructureWorker
from workers.worker_spread import SpreadWorker
from workers.worker_vix import VIXWorker
from core.visualizer import Visualizer
from config.notifier import (
    notificar_proximidad,
    notificar_error_market_watch,
    notificar_conciencia_ia,
    notificar_explicacion_ruido,
    notificar_oportunidad_detectada,
    notificar_orden_ejecutada,
    notificar_error_critico,
    notificar_rechazo_broker,
    notificar_mercado_cerrado,
    notificar_alerta_volatilidad_escalonada,
    notificar_tp_alcanzado,
    notificar_sl_alcanzado,
)


class Manager:
    """
    El Gerente Ensemble — orquestador central del sistema Aurum.

    Ciclo de vida por activo:
      1. Ejecuta los 3 Obreros y recoge sus votos.
      2. Aplica suma ponderada con los pesos de la BD.
      3. Compara el veredicto con el umbral_disparo.
      4. Si aprueba, calcula lotaje vía RiskModule y simula/ejecuta la orden.
      5. Registra TODA la auditoría en registro_senales.
    """

    # Umbrales de convicción compartidos entre métodos del Gerente.
    # Modificar aquí o en parametros_sistema en BD.
    _UMBRAL_OPORTUNIDAD = 0.30  # Convicción mínima para reportar oportunidad detectada
    _UMBRAL_PROXIMIDAD  = 0.15  # P-3 V14: Bajado de 0.38 a 0.15 para mayor participación NLP
    _UMBRAL_ZONA_GRIS   = 0.45  # Límite superior de zona gris (= umbral_disparo por defecto)

    def __init__(self, db: DBConnector, mt5: MT5Connector):
        self.db    = db
        self.mt5   = mt5
        self.risk  = RiskModule(db, mt5)
        self.trend = TrendWorker(db, mt5)
        self.nlp   = NLPWorker(db)
        self.flow   = OrderFlowWorker(db, mt5)
        self.hurst  = HurstWorker(db, mt5)
        self.volume = VolumeWorker(db, mt5)
        self.cross  = CrossWorker(db, mt5)
        self.structure = StructureWorker(db, mt5)
        self.spread    = SpreadWorker(db, mt5)
        self.vix       = VIXWorker(db, mt5)
        self.visualizer = Visualizer()

        # V7.7 & V9.0: Variables de estado global
        self._sentimiento_last_push = {} # {simbolo: float}
        self._sentimiento_last_time = {} # {simbolo: datetime}
        self._last_news_hash = {}
        self._hurst_noise_start = {}     # {simbolo: datetime}
        self._hurst_last_report = {}     # {simbolo: datetime}
        self._volatility_last_time = {} # {simbolo: datetime}
        self._hibernacion_activos = {}  # {simbolo: timestamp_inicio}
        self._last_vol_alert_level = {} # {simbolo: int_level}
        self._last_nlp_hash = None      # V15.0: Rastro de contexto macro

    # ------------------------------------------------------------------
    # Ciclo principal
    # ------------------------------------------------------------------

    def evaluar(self, simbolo_interno: str, modo_simulacion: bool = True,
                id_activo: int = None) -> dict:
        """
        Global Guard V8.0: Envuelve la evaluación en un escudo contra excepciones
        para evitar que un fallo en un activo detenga el motor completo.
        """
        try:
            return self._evaluar_internamente(simbolo_interno, modo_simulacion, id_activo)
        except Exception as e:
            error_msg = f"FALLO CRITICO en evaluacion de {simbolo_interno}: {e}"
            print(f"[GERENTE] 🚨 {error_msg}")
            self.db.registrar_log("ERROR", "MANAGER", error_msg)
            return {"decision": "ERROR_INTERNO", "motivo": str(e)}

    def _evaluar_internamente(self, simbolo_interno: str, modo_simulacion: bool = True,
                             id_activo: int = None) -> dict:
        """Lógica real de evaluación (antes evaluar)."""
        """
        Evalua un activo y decide si operar.
        id_activo: id de la BD. Si no se pasa, el NLPWorker lo resuelve por simbolo.
        modo_simulacion=True -> imprime la accion sin enviar orden real.
        """
        print(f"\n{'='*60}")
        print(f"  GERENTE — Evaluando {simbolo_interno}")
        print(f"{'='*60}")

        # V14.0 Check de Alerta de Volatilidad %Escalonada
        self._verificar_volatilidad_escalonada(simbolo_interno)

        # 1. Filtro de seguridad previo (RiskModule)
        if not self.risk.filtro_seguridad(simbolo_interno):
            motivo = f"Bloqueado por filtro_seguridad antes de evaluar Obreros."
            self._guardar_auditoria(simbolo_interno, 0.0, 0.0, 0.0, 0.0,
                                    "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # 2. Obtener pesos desde BD (Solo para compatibilidad, V6 usa balance dinámico)
        params    = self.db.get_parametros()

        # 2. Verificar visibilidad en el Broker
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            print(f"[GERENTE] Activo {simbolo_interno} no tiene mapeo en el broker.")
            return {"decision": "ERROR_CONFIG"}

        # --- PROTOCOLO GATEKEEPER V13.0: Hibernación por Error 10018 ---
        if simbolo_interno in self._hibernacion_activos:
            inicio_hib = self._hibernacion_activos[simbolo_interno]
            if time.time() - inicio_hib < 3600: # 1 hora
                min_restantes = int((3600 - (time.time() - inicio_hib)) / 60)
                print(f"[GATEKEEPER] {simbolo_interno} en HIBERNACIÓN (10018). Faltan {min_restantes} min.")
                return {"decision": "HIBERNACION_10018", "motivo": f"Pausa automatica por 1 hora. Restan {min_restantes} min."}
            else:
                del self._hibernacion_activos[simbolo_interno]
                print(f"[GATEKEEPER] {simbolo_interno} ha despertado de la hibernacion.")

        # --- PROTOCOLO GATEKEEPER V13.0: Check de Trade Mode ---
        info_simbolo = mt5.symbol_info(simbolo_broker)
        if info_simbolo:
            # SYMBOL_TRADE_MODE_DISABLED (0) o SYMBOL_TRADE_MODE_CLOSEONLY (1)
            if info_simbolo.trade_mode in (mt5.SYMBOL_TRADE_MODE_DISABLED, mt5.SYMBOL_TRADE_MODE_CLOSEONLY):
                print(f"[GATEKEEPER] {simbolo_interno} en modo {info_simbolo.trade_mode} (Cerrado). Abortando.")
                notificar_mercado_cerrado(simbolo_interno)
                return {"decision": "MERCADO_CERRADO", "motivo": "Trade mode deshabilitado por el broker."}
            
        # Hardened check for Market Watch (V6.1)
        mt5.symbol_select(simbolo_broker, True)
        tick = mt5.symbol_info_tick(simbolo_broker)
        if tick is None:
            # notificar_error_market_watch(simbolo_broker)
            print(f"[GERENTE] ⚠️ {simbolo_broker} no responde en el Market Watch.")
            return {"decision": "ERROR_CONEXION", "motivo": "Market Watch invisible"}

        # 3. Reflejo de Combate: Trigger de Volatilidad y Veto ATR (V12.0)
        volatil_ahora = self._medir_volatilidad(simbolo_broker)
        
        # Veto de Volatilidad Explosiva (ATR)
        # Si el ATR actual > 200% de la media (volatil_ahora >= 2.0 indica > 200% de la media historica en _medir_volatilidad)
        if volatil_ahora >= 2.0:
            print(f"[GERENTE] ⚡ VOLATILIDAD EXTREMA DETECTADA ({volatil_ahora:.1f}x)")
            motivo = f"Veto de Seguridad: Volatilidad explosiva ({volatil_ahora:.1f}x) superior al 200% de la media."
            self._guardar_auditoria(simbolo_interno, 0.0, 0.0, 0.0, 0.0, "VOLATILIDAD_EXTREMA", motivo)
            return {"decision": "VOLATILIDAD_EXTREMA", "motivo": motivo}

        forzar_nlp = False
        # (V12.0: El bloque de alerta de volatilidad quirurgica fue removido para priorizar el veto de seguridad)

        # 4. Consultar Obreros Técnicos primero (V10.1 Priority)
        print("\n[GERENTE] Consultando Obreros Técnicos...")
        v_trend  = self.trend.analizar(simbolo_interno)
        v_flow   = self.flow.analizar(simbolo_interno)
        v_volume = self.volume.analizar(simbolo_interno)
        v_cross  = self.cross.analizar(simbolo_interno)
        v_struct = self.structure.analizar(simbolo_interno)
        v_spread = self.spread.analizar(simbolo_interno)
        v_vix    = self.vix.analizar(simbolo_interno)
        
        # Juez de Persistencia (Hurst)
        res_hurst = self.hurst.analizar(simbolo_interno)
        h_val = res_hurst['h']
        h_estado = res_hurst['estado']

        # Calcular Veredicto Técnico preliminar para decidir el motor NLP
        # Pesos técnicos: Trend(30%), Volume(15%), Cross(15%), Flow(10%), Structure(10%) -> Total 80% (o normalizar a 1.0)
        # Para simplificar, usamos el veredicto normalizado sin el 20% de NLP.
        tecnico_veredicto = round(
            (v_trend * 0.30) + 
            (v_volume['voto'] * 0.15) + 
            (v_flow * 0.10) + 
            (v_cross['voto'] * 0.15) +
            (v_struct['voto'] * 0.10),
            4
        )
        
        # Obtener velas para contexto comprimido
        velas_recientes = []
        df_v = self.mt5.obtener_velas(simbolo_broker, 3)
        if not df_v.empty:
            velas_recientes = df_v.to_dict('records')

        # FIX-NLP-01 (2026-03-10): NLP vota siempre, sin gate de convicción técnica.
        # El gate anterior generaba un loop circular: NLP requería señal de otros obreros
        # que a su vez dependían del contexto macro. La caché de 5 min + hash SHA256
        # protegen el consumo de tokens Gemini sin necesidad de este bloqueo.
        if volatil_ahora >= 2.0 and 'voto_emg' in locals():
            v_nlp = voto_emg
        else:
            v_nlp = self.nlp.analizar(
                simbolo_interno,
                id_activo=id_activo,
                forzar_refresh=forzar_nlp,
                technical_verdict=tecnico_veredicto,
                velas_recientes=velas_recientes
            )

        # --- V10.2: Patrullaje de Noticias (Sin AI Analysis) ---
        self.nlp.patrullar_noticias()

        print(f"[SNIPER] {simbolo_interno} | Estructura: {v_struct['estado_smc']} | Veredicto: {v_struct['sniper_veredicto']}")
        
        # --- Reasoner de Ruido (V7.7) ---
        self._procesar_razonamiento_ruido(simbolo_interno, h_estado)

        # 5. Reflejo de Combate: Alerta de Divergencia
        if self._detectar_divergencia(simbolo_interno, v_trend, v_nlp):
            motivo = f"Bloqueado por DIVERGENCIA extrema entre Trend e IA."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    0.0, "CANCELADO_RIESGO", motivo,
                                    v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                    v_hurst=h_val, v_sniper=v_struct['voto'])
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # --- V12.0: WEIGHTED VOTING & NO-FLOW PROTOCOL ---
        # Pesos leídos desde parametros_sistema en BD (fallback a defaults si no hay dato).
        p_trend  = float(params.get("TENDENCIA.peso_voto",   0.40))
        p_nlp    = float(params.get("NLP.peso_voto",          0.30))
        p_flow   = float(params.get("ORDER_FLOW.peso_voto",   0.15))
        p_sniper = float(params.get("SNIPER.peso_voto",       0.15))
        
        # Protocolo No-Flow: Si Flow es None o 0.0 (neutral), redistribuimos.
        # En V12.0, si el obrero Flow retorna 0.0 (neutral por falta de datos o error), 
        # redistribuimos su 15% como: +10% a Trend y +5% a Sniper.
        if v_flow == 0.0:
            print(f"[GERENTE] 🛠 Protocolo No-Flow activado para {simbolo_interno}. Redistribuyendo pesos...")
            p_trend += 0.10 # 40% -> 50%
            p_sniper += 0.05 # 15% -> 20%
            p_flow = 0.0
            
        try:
            v_struct_voto = float(v_struct.get('voto', 0))
        except (ValueError, TypeError):
            v_struct_voto = 0.0
        
        veredicto = round(
            (v_trend * p_trend) + 
            (v_nlp * p_nlp) + 
            (v_flow * p_flow) + 
            (v_struct_voto * p_sniper),
            4
        )

        # --- PENALIZACIÓN DE HURST (V10.5) ---
        if 0.45 <= h_val <= 0.55:
            print(f"[GERENTE] ⚠️ Mercado en RUIDO (H: {h_val:.4f}). Penalización -0.15.")
            if veredicto > 0:
                veredicto = max(0.0, veredicto - 0.15)
            elif veredicto < 0:
                veredicto = min(0.0, veredicto + 0.15)

        # --- PENALIZACIÓN DE SPREAD (P-3) ---
        ajuste_spread = v_spread.get("ajuste", 0.0)
        if ajuste_spread != 0.0:
            print(f"[GERENTE] 📉 Spread {v_spread['estado']} ({v_spread['ratio']:.1f}x). Ajuste: {ajuste_spread:+.2f}")
            if veredicto > 0:
                veredicto = max(0.0, veredicto + ajuste_spread)
            elif veredicto < 0:
                veredicto = min(0.0, veredicto - ajuste_spread)

        # --- PENALIZACIÓN DE VOLATILIDAD VIX/ATR (P-4) ---
        ajuste_vix = v_vix.get("ajuste", 0.0)
        if ajuste_vix != 0.0:
            print(f"[GERENTE] 📊 Volatilidad {v_vix['nivel']} (ATR×{v_vix['ratio']:.1f}). Ajuste: {ajuste_vix:+.2f}")
            if veredicto > 0:
                veredicto = max(0.0, veredicto + ajuste_vix)
            elif veredicto < 0:
                veredicto = min(0.0, veredicto - ajuste_vix)
        
        # --- FUERZA DOMINANTE (V12.0) ---
        pesos_votos = {
            "Trend": abs(v_trend * p_trend),
            "NLP": abs(v_nlp * p_nlp),
            "Flow": abs(v_flow * p_flow),
            "Sniper": abs(v_struct_voto * p_sniper)
        }
        fuerza_dominante = max(pesos_votos, key=lambda k: pesos_votos[k])
        if pesos_votos[fuerza_dominante] == 0:
            fuerza_dominante = "Neutral"

        veredicto = round(max(-1.0, min(1.0, veredicto)), 4)

        # 6. Decisión y Telemetría Extra
        # Black Swan Emergency
        umbral_base = params.get("GERENTE.umbral_disparo", 0.45)
        umbral = 0.60 if v_cross['black_swan'] else umbral_base
        
        if v_cross['black_swan']:
            print(f"[GERENTE] 🚨 MODO EMERGENCIA: DXY Volátil. Umbral elevado a {umbral}")

        # --- IA CONSCIENCE (V7.5) ---
        gemini_thought = self.nlp.obtener_razonamiento(simbolo_interno)

        # Prep data para notificaciones
        vol_map = {
            "poc": v_volume['poc'],
            "va": f"{v_volume['val']} - {v_volume['vah']}",
            "contexto": v_volume['contexto'],
            "ajuste": v_volume['ajuste']
        }
        
        cross_map = {
            "dxy": v_cross['var_dxy'],
            "spx": v_cross['var_spx'],
            "oil": v_cross['var_oil'],
            "divergencia": v_cross['divergencia'],
            "ajuste": v_cross['ajuste'],
            "black_swan": v_cross['black_swan']
        }
        # 5. Decisión
        umbral = params.get("GERENTE.umbral_disparo", 0.45)
        
        print(f"\n[GERENTE] Pesos V12.0 Dynamic: Trend({p_trend*100:.0f}%) NLP({p_nlp*100:.0f}%) Flow({p_flow*100:.0f}%) Sniper({p_sniper*100:.0f}%)")
        print(f"[GERENTE] Veredicto: {veredicto:+.4f} | Sniper: {v_struct['sniper_veredicto']} | Fuerza: {fuerza_dominante}")
        print(f"[GERENTE] Hurst: {h_val:.4f} ({h_estado}) | Status: {'MODO EMERGENCIA' if v_cross['black_swan'] else 'Normal'}")
        
        if abs(veredicto) < umbral:
            # --- NUEVO REPORTE DE GATILLO Y PROXIMIDAD ---
            confianza = abs(veredicto)
            if self._UMBRAL_PROXIMIDAD <= confianza < self._UMBRAL_ZONA_GRIS:
                # Generar Telemetría Gráfica (V7.5)
                df_viz = self.mt5.obtener_velas(simbolo_broker, 100)
                votos_map = {
                    "Trend": v_trend, "NLP": v_nlp, "Flow": v_flow,
                    "Volume": v_volume['voto'], "Cross": v_cross['voto'], "Struct": v_struct['voto']
                }
                img_path = self.visualizer.generar_reporte_grafico(simbolo_interno, df_viz, votos_map, v_struct['ob_precio'], v_volume['poc'])
                
                # notificar_proximidad(simbolo_interno, veredicto, h_val, h_estado, vol_map, cross_map, v_struct, 
                #                      image_path=img_path, gemini_thought=gemini_thought, fuerza_dominante=fuerza_dominante)
                pass # Silenciado V12.1
            elif self._UMBRAL_OPORTUNIDAD <= confianza < self._UMBRAL_PROXIMIDAD:
                # notificar_oportunidad_detectada(simbolo_interno, veredicto, fuerza_dominante=fuerza_dominante)
                pass # Silenciado V12.1
            
            if confianza >= self._UMBRAL_OPORTUNIDAD:
                motivo = f"Oportunidad detectada ({confianza:.2f}), pero debajo del umbral ({umbral})."
            else:
                motivo = f"Veredicto {veredicto:+.4f} insufficiente (Umbral: {umbral})"
            
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "IGNORADO", motivo,
                                    v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                    v_hurst=h_val, v_sniper=v_struct['voto'])
            return {"decision": "IGNORADO", "veredicto": veredicto, "motivo": motivo}

        # 6. Aprobado — verificar ventana de ejecución (D1 V14)
        # Los workers ya votaron. Este check solo bloquea la ORDEN, no el análisis.
        if not self.risk.verificar_ventana_ejecucion(simbolo_interno):
            motivo = f"Veredicto {veredicto:+.4f} aprobado pero ejecucion bloqueada (horario/arranque de sesion)."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "BLOQUEADO_HORARIO", motivo,
                                    v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                    v_hurst=h_val, v_sniper=v_struct['voto'])
            return {"decision": "BLOQUEADO_HORARIO", "veredicto": veredicto, "motivo": motivo}

        # 6b. Calcular dirección y lotaje
        direccion = "COMPRA" if veredicto > 0 else "VENTA"
        
        # --- NUEVA LOGICA DE RIESGO DINAMICO ---
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        
        # 6.a Calculo de SL y TP via ATR
        sl, tp = self.risk.obtener_sl_tp_atr(simbolo_broker, direccion)
        if sl is None or tp is None:
            motivo = "Error calculando SL/TP via ATR. Orden abortada."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "CANCELADO_RIESGO", motivo,
                                    v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                    v_hurst=h_val, v_sniper=v_struct['voto'])
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # 6.b Calculo de Lotaje Dinamico (Confianza)
        lotes = self.risk.calcular_lotes_dinamicos(veredicto)
        
        print(f"[GERENTE] Riesgo Dinamico -> Conviccion: {abs(veredicto)*100:.1f}% | Lotes: {lotes} | SL: {sl:.4f} | TP: {tp:.4f}")

        # 7. Justificación Glass Box
        motivo = (
            f"Veredicto Ensemble: {veredicto:+.4f} supera umbral {umbral}. "
            f"Señal de {direccion}. "
            f"Votos: Trend={v_trend:+.2f} (0.30), "
            f"NLP={v_nlp:+.2f} (0.20), "
            f"Flow={v_flow:+.2f} (0.10). "
            f"SL={sl:.2f}  TP={tp:.2f}  Lotes={lotes}."
        )

        # 8. Ejecutar o simular
        if modo_simulacion:
            print(f"\n[GERENTE] Simulando ejecucion de {direccion} con {lotes} lotes")
            
            # Obtener balance actual para la notificación
            import MetaTrader5 as mt5_api
            acc_info = mt5_api.account_info()
            balance = acc_info.balance if acc_info else 0.0
            equity  = acc_info.equity  if acc_info else balance

            notificar_orden_ejecutada(
                simbolo=simbolo_interno,
                direccion=direccion,
                lotes=lotes,
                ticket=999999,  # Ticket ficticio para simulacion
                precio=self._obtener_precio_seguro(simbolo_interno, direccion),
                sl=sl,
                tp=tp,
                veredicto=veredicto,
                v_trend=v_trend,
                v_nlp=v_nlp,
                balance=balance,
                equity=equity,
                hurst_h=h_val,
                hurst_estado=h_estado,
                vol_poc=vol_map['poc'],
                vol_va=vol_map['va'],
                vol_ctx=vol_map['contexto'],
                vol_ajuste=vol_map['ajuste'],
                cross_div=cross_map['cross_div'] if 'cross_div' in cross_map else cross_map['divergencia'],
                cross_ajuste=cross_map['cross_ajuste'] if 'cross_ajuste' in cross_map else cross_map['ajuste'],
                smc_ob=v_struct['ob_precio'],
                smc_estado=v_struct['estado_smc'],
                smc_veredicto=v_struct['sniper_veredicto'],
                smc_voto_raw=v_struct_voto,
                v_flow=v_flow,
                v_vol=v_volume['voto'],
                v_cross=v_cross['voto'],
                v_hurst=h_val,
                gemini_thought=gemini_thought,
                fuerza_dominante=fuerza_dominante,
                image_path=self.visualizer.generar_reporte_grafico(
                    simbolo_interno, self.mt5.obtener_velas(simbolo_broker, 100), 
                    {"Trend": v_trend, "NLP": v_nlp, "Flow": v_flow, "Vol": v_volume['voto'], "Cross": v_cross['voto'], "Struct": v_struct['voto']},
                    v_struct['ob_precio'], v_volume['poc']
                )
            )
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "EJECUTADO", motivo,
                                    v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                    v_hurst=h_val, v_sniper=v_struct['voto'])
            return {"decision": direccion, "lotes": lotes, "veredicto": veredicto, "motivo": motivo}
        else:
            # 8.a Validación de seguridad (Cuenta MT5)
            import MetaTrader5 as mt5_api
            cuenta_esperada = os.environ.get("MT5_LOGIN", "")
            info_oc = mt5_api.account_info()
            if not info_oc or str(info_oc.login) != cuenta_esperada:
                err_msg = f"Rechazo de Seguridad: Intento de operar en cuenta {info_oc.login if info_oc else 'Desconocida'} en vez de {cuenta_esperada}"
                print(f"[GERENTE] 🚨 {err_msg}")
                notificar_error_critico("SEGURIDAD_PRE_TRADE", err_msg)
                return {"decision": "ERROR_BROKER", "motivo": err_msg}

            obj_ticket = self.mt5.enviar_orden(
                self.db.obtener_simbolo_broker(simbolo_interno),
                direccion, lotes, sl, tp
            )
            
            if obj_ticket.get("status") == "error":
                retcode = obj_ticket.get("retcode", -1)
                causa   = obj_ticket.get("comment", "Desconocido")
                err_msg = f"Rechazo del Broker. Retcode: {retcode} | {causa}"
                
                print(f"\n[GERENTE] ERROR DE EJECUCION: {err_msg}")
                # Registrar en la nueva tabla de errores
                self.db.guardar_error_ejecucion(
                    simbolo=simbolo_interno,
                    retcode=retcode,
                    mensaje=causa,
                    decision=direccion,
                    lotes=lotes,
                    contexto=motivo
                )

                # --- PROTOCOLO GATEKEEPER V13.0: Gatillo de Hibernación ---
                if retcode == 10018:
                    print(f"[GATEKEEPER] Activando HIBERNACIÓN para {simbolo_interno} (Error 10018).")
                    self._hibernacion_activos[simbolo_interno] = time.time()

                notificar_rechazo_broker(simbolo_interno, retcode, causa)
                
                self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                        veredicto, "ERROR_BROKER", err_msg,
                                        v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                        v_hurst=h_val, v_sniper=v_struct['voto'])
                return {"decision": "ERROR_BROKER", "motivo": err_msg}
            else:
                ticket = obj_ticket.get("ticket")
                print(f"\n[GERENTE] ORDEN RECIBIDA (10009) — Ticket: {ticket}")
                
                # Bucle de Verificación Post-Trade
                time.sleep(1)
                posiciones = mt5_api.positions_get(ticket=ticket)
                if not posiciones:
                    err_msg = f"Discrepancia MT5: Ticket {ticket} reportado como DONE pero no aparece en posiciones abiertas."
                    print(f"[GERENTE] 🚨 {err_msg}")
                    notificar_error_critico("DISCREPANCIA_BROKER", err_msg)
                    self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow, veredicto, "ERROR_BROKER", err_msg,
                                            v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                            v_hurst=h_val, v_sniper=v_struct['voto'])
                    return {"decision": "ERROR_BROKER", "motivo": err_msg}
                
                # Obtener detalles reales
                pos          = posiciones[0]
                precio_real  = pos.price_open
                info_acc     = mt5_api.account_info()
                balance_real = info_acc.balance if info_acc else 0.0
                equity_real  = info_acc.equity  if info_acc else balance_real

                # --- NUEVO: Cálculo de Probabilidad ---
                # Confianza [0.45 - 1.0] -> Probabilidad [65% - 98%]
                confianza  = abs(veredicto)
                prob_exito = 65 + ((confianza - 0.45) / (0.55)) * (33)
                prob_exito = max(65, min(98, round(prob_exito, 1)))

                notificar_orden_ejecutada(
                    simbolo=simbolo_interno,
                    direccion=direccion,
                    lotes=lotes,
                    ticket=ticket,
                    precio=precio_real,
                    sl=sl, tp=tp,
                    veredicto=veredicto,
                    v_trend=v_trend,
                    v_nlp=v_nlp,
                    balance=balance_real,
                    equity=equity_real,
                    hurst_h=h_val,
                    hurst_estado=h_estado,
                    vol_poc=vol_map['poc'],
                    vol_va=vol_map['va'],
                    vol_ctx=vol_map['contexto'],
                    vol_ajuste=vol_map['ajuste'],
                    cross_div=cross_map['cross_div'] if 'cross_div' in cross_map else cross_map['divergencia'], 
                    cross_ajuste=cross_map['cross_ajuste'] if 'cross_ajuste' in cross_map else cross_map['ajuste'],
                    smc_ob=v_struct['ob_precio'],
                    smc_estado=v_struct['estado_smc'],
                    smc_veredicto=v_struct['sniper_veredicto'],
                    smc_voto_raw=v_struct_voto,
                    v_flow=v_flow,
                    v_vol=v_volume['voto'],
                    v_cross=v_cross['voto'],
                    v_hurst=h_val,
                    gemini_thought=gemini_thought,
                    fuerza_dominante=fuerza_dominante,
                    image_path=self.visualizer.generar_reporte_grafico(
                        simbolo_interno, self.mt5.obtener_velas(simbolo_broker, 100), 
                        {"Trend": v_trend, "NLP": v_nlp, "Flow": v_flow, "Vol": v_volume['voto'], "Cross": v_cross['voto'], "Struct": v_struct['voto']},
                        v_struct['ob_precio'], v_volume['poc']
                    )
                )
                
                # Actualizar registro con veredicto y probabilidad
                try:
                    self.db.cursor.execute("""
                        UPDATE registro_operaciones 
                        SET veredicto_apertura = %s, probabilidad_est = %s
                        WHERE ticket_mt5 = %s
                    """, (veredicto, prob_exito, ticket))
                    self.db.conn.commit()
                except Exception as e_reg:
                    print(f"[GERENTE] Error actualizando precision inicial: {e_reg}")

                self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                        veredicto, "EJECUTADO", motivo,
                                        v_vol=v_volume['voto'], v_cross=v_cross['voto'],
                                        v_hurst=h_val, v_sniper=v_struct['voto'])
                return {"decision": direccion, "lotes": lotes, "veredicto": veredicto, "motivo": motivo}

    # ------------------------------------------------------------------
    # Gestión de Posiciones Abiertas (Breakeven)
    # ------------------------------------------------------------------

    def gestionar_posiciones_abiertas(self):
        """
        Cicla por las posiciones abiertas y aplica la logica de Breakeven.
        Si el precio recorrio el 50% del camino al TP, mueve SL a BE.
        """
        import MetaTrader5 as mt5_api
        posiciones = mt5_api.positions_get()
        if not posiciones:
            return

        for pos in posiciones:
            # Solo gestionamos posiciones del bot (opcional: filtrar por magic number)
            # if pos.magic != 20250101: continue
            
            # Si el SL ya esta en el precio de entrada (o mejor), ignorar
            if (pos.type == mt5_api.POSITION_TYPE_BUY and pos.sl >= pos.price_open) or \
               (pos.type == mt5_api.POSITION_TYPE_SELL and pos.sl <= pos.price_open and pos.sl != 0):
                continue

            precio_actual = mt5_api.symbol_info_tick(pos.symbol).bid if pos.type == mt5_api.POSITION_TYPE_BUY \
                            else mt5_api.symbol_info_tick(pos.symbol).ask
            
            # Calcular progreso hacia el TP
            distancia_total = abs(pos.tp - pos.price_open)
            if distancia_total == 0: continue
            
            progreso = abs(precio_actual - pos.price_open) / distancia_total
            
            if progreso >= 0.50:
                print(f"[GERENTE] 🛡️ Aplicando Breakeven a #{pos.ticket} ({pos.symbol}). Progreso: {progreso*100:.1f}%")
                if self.mt5.mover_sl(pos.ticket, pos.price_open):
                    self.db.registrar_log("INFO", "MANAGER", f"Breakeven aplicado a #{pos.ticket} ({pos.symbol})")

    def auditar_precision_cierres(self):
        """
        Escanea el historial de MT5 para detectar cierres de órdenes del bot.
        Calcula la Divergencia de Precisión y actualiza la BD.
        """
        # Guarda: Si la DB no está disponible (Modo Supervivencia), salir
        if not self.db.cursor:
            return

        import MetaTrader5 as mt5_api
        from datetime import datetime, timedelta

        # 1. Obtener trades cerrados sin resultado en la BD (D3 V14: incluir simbolo)
        try:
            self.db.cursor.execute("""
                SELECT ro.ticket_mt5, ro.veredicto_apertura, ro.probabilidad_est,
                       ro.precio_entrada, ro.take_profit, ro.stop_loss, a.simbolo
                FROM registro_operaciones ro
                JOIN activos a ON a.id = ro.activo_id
                WHERE ro.resultado_final IS NULL AND ro.ticket_mt5 != 999999
            """)
        except Exception:
            return
        pendientes = self.db.cursor.fetchall()
        if not pendientes:
            return

        # 2. Consultar historial de MT5 (últimas 24h para estar seguros)
        from_date = datetime.now() - timedelta(days=1)
        history = mt5_api.history_deals_get(from_date, datetime.now())
        if history is None:
            return

        for ticket, veredicto, prob, p_ent, tp, sl, simbolo in pendientes:
            # Buscar el deal de salida para este ticket de orden
            deals = [d for d in history if d.order == ticket and d.entry == mt5_api.DEAL_ENTRY_OUT]

            if deals:
                deal = deals[0]
                ganancia = deal.profit
                resultado = "GANADO" if ganancia > 0 else "PERDIDO"

                exito_real = 100.0 if resultado == "GANADO" else 0.0
                divergencia = abs(exito_real - float(prob))

                print(f"[GERENTE] Auditoria de Cierre #{ticket}: Result={resultado} | Prob={prob}% | Div={divergencia:.1f}")

                try:
                    self.db.cursor.execute("""
                        UPDATE registro_operaciones
                        SET resultado_final = %s, divergencia_precision = %s, pnl_usd = %s
                        WHERE ticket_mt5 = %s
                    """, (resultado, divergencia, ganancia, ticket))
                    self.db.conn.commit()
                except Exception as e:
                    print(f"[GERENTE] Error actualizando precision de cierre #{ticket}: {e}")

                # FASE 4 V15: Consultar cuenta para notificaciones de cierre
                try:
                    acc_cierre = mt5_api.account_info()
                    bal_cierre = acc_cierre.balance if acc_cierre else 0.0
                    eq_cierre  = acc_cierre.equity  if acc_cierre else 0.0
                except Exception:
                    bal_cierre = eq_cierre = 0.0

                # D3 V14: Autopsia de Pérdida — analizar con Gemini por qué falló
                motivo_entrada = "Sin registro de justificacion"
                if resultado == "PERDIDO":
                    try:
                        self.db.cursor.execute("""
                            SELECT motivo FROM registro_senales
                            WHERE activo_id = (SELECT id FROM activos WHERE simbolo = %s)
                            AND decision_gerente = 'EJECUTADO'
                            ORDER BY tiempo DESC LIMIT 1
                        """, (simbolo,))
                        row = self.db.cursor.fetchone()
                        motivo_entrada = row[0] if row else "Sin registro de justificacion"
                        self._autopsia_perdida(ticket, simbolo, motivo_entrada, ganancia)
                    except Exception as e:
                        print(f"[GERENTE] Error preparando autopsia #{ticket}: {e}")

                # FASE 4 V15: Notificaciones Telegram de cierre
                try:
                    if resultado == "GANADO":
                        notificar_tp_alcanzado(
                            ticket=ticket, simbolo=simbolo, pnl=ganancia,
                            p_entrada=float(p_ent), tp=float(tp), p_cierre=deal.price,
                            veredicto=float(veredicto),
                            prob_est=float(prob) if prob else 0.0,
                            balance=bal_cierre, equity=eq_cierre,
                        )
                    else:
                        # Intentar leer autopsia recién guardada para incluirla
                        autopsia_data = {}
                        try:
                            self.db.cursor.execute("""
                                SELECT tipo_fallo, worker_culpable, descripcion, correccion_sugerida
                                FROM autopsias_perdidas WHERE ticket = %s LIMIT 1
                            """, (ticket,))
                            r = self.db.cursor.fetchone()
                            if r:
                                autopsia_data = {
                                    "tipo_fallo":       r[0] or "",
                                    "worker_culpable":  r[1] or "",
                                    "descripcion":      r[2] or "",
                                    "correccion":       r[3] or "",
                                }
                        except Exception:
                            pass
                        notificar_sl_alcanzado(
                            ticket=ticket, simbolo=simbolo, pnl=ganancia,
                            p_entrada=float(p_ent), sl=float(sl), p_cierre=deal.price,
                            veredicto=float(veredicto),
                            prob_est=float(prob) if prob else 0.0,
                            balance=bal_cierre, equity=eq_cierre,
                            motivo_entrada=motivo_entrada,
                            **autopsia_data,
                        )
                except Exception as e_notif:
                    print(f"[GERENTE] Error notificacion de cierre #{ticket}: {e_notif}")

    # ------------------------------------------------------------------
    # Auditoría obligatoria (Glass Box)
    # ------------------------------------------------------------------

    def _guardar_auditoria(self, simbolo: str, v_trend: float, v_nlp: float,
                            v_flow: float, veredicto: float,
                            decision: str, motivo: str, 
                            v_vol: float = 0.0, v_cross: float = 0.0, 
                            v_hurst: float = 0.5, v_sniper: float = 0.0):
        """Guarda la auditoría completa en registro_senales. SIEMPRE se ejecuta."""
        try:
            # V12.0: Forzar cast a float para evitar fugas de tipos numpy (np.float64) a SQL
            self.db.guardar_senal(simbolo, float(v_trend), float(v_nlp), float(v_flow),
                                  float(veredicto), decision, motivo,
                                  v_vol=float(v_vol), v_cross=float(v_cross), 
                                  v_hurst=float(v_hurst), v_sniper=float(v_sniper))
            
            # --- NUEVO: Persistencia de Veredicto en registro_operaciones si fue ejecutado ---
            if decision in ("COMPRA", "VENTA", "EJECUTADO") and not motivo.startswith("Simulando"):
                # Intentamos actualizar la última operación abierta para este activo con el veredicto
                try:
                    query = """
                        UPDATE registro_operaciones 
                        SET veredicto_apertura = %s
                        WHERE id = (
                            SELECT id FROM registro_operaciones 
                            WHERE activo_id = (SELECT id FROM activos WHERE simbolo = %s)
                            ORDER BY tiempo_entrada DESC LIMIT 1
                        )
                    """
                    self.db.cursor.execute(query, (veredicto, simbolo))
                    self.db.conn.commit()
                except Exception as e_db:
                    print(f"[GERENTE] Error guardando veredicto_apertura: {e_db}")

            print(f"[GERENTE] Auditoria guardada en registro_senales ({decision})")
        except Exception as e:
            print(f"[GERENTE] ERROR guardando auditoria: {e}")

    # ------------------------------------------------------------------
    # Reflejos de Combate (Sensor de Inconsistencia)
    # ------------------------------------------------------------------

    def mantener_vigilancia(self):
        """Protocolo V15.0: Vigilancia de Fin de Semana (News + Heartbeat)."""
        try:
            ahora = datetime.now().strftime("%H:%M")
            print(f"[VIGILANCIA] {ahora} -> Patrullando noticias...")
            
            # 1. Update Heartbeat
            self.db.update_estado_bot("AHORRO (VIGILANCIA)", f"Vigilando noticias desde las {ahora}. MT5 en reposo.")
            
            # 2. Patrullar Noticias (Nuevas notificaciones a Telegram)
            self.nlp.patrullar_noticias()
            
            # 3. Verificar si el hash global cambió para forzar refresco de caché
            current_hash = self.nlp.get_current_hash()
            if self._last_nlp_hash and current_hash != self._last_nlp_hash:
                print(f"[VIGILANCIA] ⚠️ Cambio de contexto macro detectado. Refrescando caché...")
                # Forzar un análisis ligero para un activo de referencia para 'calentar' el caché
                self.nlp.analizar("XAUUSD", forzar_refresh=True, solo_si_conviccion=False)
            
            self._last_nlp_hash = current_hash
            
        except Exception as e:
            print(f"[VIGILANCIA] Error en ciclo de vigilancia: {e}")

    def _verificar_volatilidad_escalonada(self, simbolo_interno: str):
        """Protocolo V14.0: Alertas escalonadas (5, 8, 10, 12, 15, 20%)."""
        try:
            sb = self.db.obtener_simbolo_broker(simbolo_interno)
            rates = mt5.copy_rates_from_pos(sb, mt5.TIMEFRAME_D1, 0, 1)
            if rates is None or len(rates) == 0:
                return
            
            day_open = rates[0]['open']
            tick = mt5.symbol_info_tick(sb)
            if not tick:
                return
            
            precio_actual = tick.bid
            cambio_pct = ((precio_actual - day_open) / day_open) * 100.0
            pct_abs = abs(cambio_pct)
            
            # Umbrales
            umbrales = [5, 8, 10, 12, 15, 20, 25, 30]
            current_level = 0
            for u in umbrales:
                if pct_abs >= u:
                    current_level = u
            
            last_level = self._last_vol_alert_level.get(simbolo_interno, 0)
            if current_level > last_level:
                self._last_vol_alert_level[simbolo_interno] = current_level
                notificar_alerta_volatilidad_escalonada(simbolo_interno, cambio_pct, precio_actual)
                print(f"[GERENTE] Alerta de Volatilidad lanzada para {simbolo_interno} @ {current_level}%")
                
        except Exception as e:
            print(f"[GERENTE] Error en check_volatilidad_escalonada: {e}")

    def _medir_volatilidad(self, simbolo_broker: str) -> float:
        """
        Calcula el ratio de volatilidad de la vela actual (M1) respecto al promedio
        de las 10 velas anteriores.
        Retorna el ratio (ej: 3.5 significa que la vela actual es 3.5x más grande).
        """
        try:
            import MetaTrader5 as mt5
            velas = mt5.copy_rates_from_pos(simbolo_broker, mt5.TIMEFRAME_M1, 0, 11)
            if velas is None or len(velas) < 11:
                return 1.0

            vela_actual = velas[-1]
            velas_previas = velas[:-1]

            tamano_actual = abs(vela_actual['high'] - vela_actual['low'])
            
            # Promedio de las ultimas 10 velas
            suma_tamanos = sum(abs(v['high'] - v['low']) for v in velas_previas)
            promedio_10 = suma_tamanos / 10.0

            if promedio_10 == 0:
                return 1.0

            ratio = tamano_actual / promedio_10
            return ratio
        except Exception as e:
            print(f"[GERENTE] ERROR midiendo volatilidad: {e}")
            return 1.0

    def _detectar_divergencia(self, simbolo: str, v_trend: float, v_nlp: float) -> bool:
        """
        Detecta si hay una contradiccion severa entre el analisis tecnico puro
        (TrendWorker al maximo) y el analisis macroeconomico (NLPWorker).
        """
        # Condiciones de divergencia: precio explotando pero IA dice neutral/contrario
        divergencia_alcista = (v_trend >= 0.90) and (v_nlp <= 0.0)
        divergencia_bajista = (v_trend <= -0.90) and (v_nlp >= 0.0)

        if divergencia_alcista or divergencia_bajista:
            # notificar_divergencia(simbolo, v_trend, v_nlp)
            print(f"[GERENTE] ⚠️ Divergencia detectada en {simbolo}. Silenciada por V10.2.")
            return True
        return False

    # ------------------------------------------------------------------
    # Bitácora de Guerra (V7.7 Helpers)
    # ------------------------------------------------------------------

    def _procesar_ai_push(self, simbolo, v_nlp):
        """
        V10.2: Desactivado por Silent Mode.
        """
        pass

    def _obtener_precio_seguro(self, simbolo_interno: str, direccion: str) -> float:
        """Obtiene precio bid/ask con protección contra respuesta None de MT5."""
        sb = self.db.obtener_simbolo_broker(simbolo_interno)
        tick = self.mt5.obtener_precio_actual(sb) if sb else None
        if not tick:
            return 0.0
        return tick['ask'] if direccion == "COMPRA" else tick['bid']

    # ------------------------------------------------------------------
    # D3 V14: Autopsia de Pérdidas
    # ------------------------------------------------------------------

    def _autopsia_perdida(self, ticket: int, simbolo: str, motivo_entrada: str, pnl: float):
        """
        D3 V14: Llama a Gemini para analizar por qué falló un trade perdedor.
        Contrasta la justificación original de entrada con el resultado final.
        Guarda el diagnóstico en autopsias_perdidas para revisión y recalibración.
        """
        try:
            from workers.worker_nlp import _llamar_gemini_api, GEMINI_MODEL_LITE
            prompt = (
                f"AUTOPSIA DE TRADE PERDEDOR — Sistema Aurum\n\n"
                f"ACTIVO: {simbolo}\n"
                f"TICKET: {ticket}\n"
                f"PERDIDA: ${abs(pnl):.2f} USD\n\n"
                f"JUSTIFICACION ORIGINAL DE ENTRADA:\n{motivo_entrada}\n\n"
                f"TAREA:\n"
                f"1. Identifica el fallo principal: tecnico (trend/flow/structure), macro (nlp), timing o riesgo.\n"
                f"2. Cual senal de advertencia se ignoro o peso incorrectamente?\n"
                f"3. Sugiere UNA correccion concreta al sistema.\n\n"
                f"Responde SOLO en JSON (sin markdown):\n"
                f"{{\"tipo_fallo\": \"TECNICO|MACRO|TIMING|RIESGO\", "
                f"\"worker_culpable\": \"TrendWorker|NLPWorker|FlowWorker|StructureWorker|Otro\", "
                f"\"descripcion\": \"...\", \"correccion_sugerida\": \"...\"}}"
            )
            texto = _llamar_gemini_api(prompt, model=GEMINI_MODEL_LITE)
            if texto:
                import json as _json
                inicio = texto.find("{")
                fin = texto.rfind("}") + 1
                if inicio >= 0 and fin > inicio:
                    data = _json.loads(texto[inicio:fin])
                    self.db.guardar_autopsia(
                        ticket=ticket,
                        simbolo=simbolo,
                        pnl=pnl,
                        tipo_fallo=data.get("tipo_fallo", "DESCONOCIDO"),
                        worker_culpable=data.get("worker_culpable", "Desconocido"),
                        descripcion=data.get("descripcion", ""),
                        correccion=data.get("correccion_sugerida", "")
                    )
                    print(f"[AUTOPSIA] #{ticket} {simbolo} -> Fallo: {data.get('tipo_fallo')} | Worker: {data.get('worker_culpable')}")
        except Exception as e:
            print(f"[AUTOPSIA] Error en autopsia de #{ticket}: {e}")

    # ------------------------------------------------------------------
    # D2 V14: Recalibración Semanal de Pesos
    # ------------------------------------------------------------------

    def _recalibrar_pesos(self):
        """
        D2 V14: Recalibración de pesos de obreros basada en tasa de acierto (7 días).
        Requisitos: >= 20 trades completados en la muestra.
        Ajuste máximo: ±0.05 por semana. Límites: [0.10, 0.60] por obrero.
        Escribe los nuevos pesos en parametros_sistema y notifica por Telegram.
        """
        try:
            if not self.db.cursor:
                return

            self.db.cursor.execute("""
                SELECT
                    rs.voto_tendencia,
                    rs.voto_nlp,
                    rs.voto_order_flow,
                    rs.voto_sniper,
                    ro.resultado_final
                FROM registro_senales rs
                JOIN registro_operaciones ro ON ro.activo_id = rs.activo_id
                WHERE rs.decision_gerente = 'EJECUTADO'
                AND ro.resultado_final IS NOT NULL
                AND rs.tiempo > NOW() - INTERVAL '7 days'
                LIMIT 500
            """)
            rows = self.db.cursor.fetchall()

            if len(rows) < 20:
                print(f"[RECALIB] Muestra insuficiente ({len(rows)} trades en 7 dias). Sin ajustes.")
                return

            def _tasa_acierto(votos, resultados):
                pares = [(v, r) for v, r in zip(votos, resultados) if abs(v) > 0.05]
                if not pares:
                    return 0.5
                aciertos = sum(
                    1 for v, r in pares
                    if (v > 0 and r == "GANADO") or (v < 0 and r == "PERDIDO")
                )
                return aciertos / len(pares)

            resultados = [r[4] for r in rows]
            accs = {
                "TENDENCIA.peso_voto":   _tasa_acierto([r[0] for r in rows], resultados),
                "NLP.peso_voto":         _tasa_acierto([r[1] for r in rows], resultados),
                "ORDER_FLOW.peso_voto":  _tasa_acierto([r[2] for r in rows], resultados),
                "SNIPER.peso_voto":      _tasa_acierto([r[3] for r in rows], resultados),
            }

            params = self.db.get_parametros()
            cambios = []

            for param, acc in accs.items():
                peso_actual = float(params.get(param, 0.25))
                if acc > 0.65:
                    delta = +0.05
                elif acc < 0.45:
                    delta = -0.05
                else:
                    delta = 0.0

                if delta != 0.0:
                    nuevo_peso = round(max(0.10, min(0.60, peso_actual + delta)), 2)
                    if nuevo_peso != peso_actual:
                        self.db.cursor.execute(
                            "UPDATE parametros_sistema SET valor = %s WHERE nombre_parametro = %s",
                            (nuevo_peso, param)
                        )
                        cambios.append(f"{param}: {peso_actual:.2f} -> {nuevo_peso:.2f} (acc={acc:.0%})")

            if cambios:
                self.db.conn.commit()
                self.db._params_last_refresh = 0  # Forzar recarga del cache
                msg = "<b>Recalibracion de Pesos Completada</b>\nMuestra: {} trades (7 dias)\n".format(len(rows))
                msg += "\n".join(f"• {c}" for c in cambios)
                from config.notifier import _enviar_telegram
                _enviar_telegram(msg)
                print(f"[RECALIB] Pesos ajustados: {cambios}")
            else:
                print(f"[RECALIB] Pesos estables (muestra: {len(rows)} trades). Sin ajustes necesarios.")

        except Exception as e:
            print(f"[RECALIB] Error en recalibracion: {e}")
            if self.db.conn:
                try:
                    self.db.conn.rollback()
                except Exception:
                    pass

    def _procesar_razonamiento_ruido(self, simbolo, h_estado):
        """Explica el ruido del Hurst una vez por hora."""
        ahora = datetime.now(timezone.utc)
        
        if h_estado == "RUIDO":
            if simbolo not in self._hurst_noise_start:
                self._hurst_noise_start[simbolo] = ahora
            
            last_rep = self._hurst_last_report.get(simbolo, datetime.min.replace(tzinfo=timezone.utc))
            seg_ruido = (ahora - self._hurst_noise_start[simbolo]).total_seconds()
            seg_desde_rep = (ahora - last_rep).total_seconds()
            
            if seg_ruido >= 3600 and seg_desde_rep >= 3600:
                self._hurst_last_report[simbolo] = ahora
                # notificar_explicacion_ruido(...)
                print(f"[GERENTE] ⚠️ Mercado en RUIDO para {simbolo}. Silenciada por V10.2.")
                pass
        else:
            # Si ya no hay ruido, reseteamos el contador
            if simbolo in self._hurst_noise_start:
                del self._hurst_noise_start[simbolo]
