import sys
import os
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.risk_module import RiskModule
from workers.worker_trend import TrendWorker
from workers.worker_nlp import NLPWorker
from workers.worker_flow import OrderFlowWorker
from workers.worker_hurst import HurstWorker
from workers.worker_volume import VolumeWorker
from config.notifier import (
    notificar_zona_caliente,
    notificar_orden_ejecutada,
    notificar_error_critico,
    notificar_divergencia,
    notificar_rechazo_broker,
    notificar_oportunidad_detectada,
    notificar_proximidad
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

    def __init__(self, db: DBConnector, mt5: MT5Connector):
        self.db    = db
        self.mt5   = mt5
        self.risk  = RiskModule(db, mt5)
        self.trend = TrendWorker(db, mt5)
        self.nlp   = NLPWorker(db)
        self.flow   = OrderFlowWorker(db, mt5)
        self.hurst  = HurstWorker(db, mt5)
        self.volume = VolumeWorker(db, mt5)

    # ------------------------------------------------------------------
    # Ciclo principal
    # ------------------------------------------------------------------

    def evaluar(self, simbolo_interno: str, modo_simulacion: bool = True,
                id_activo: int = None) -> dict:
        """
        Evalua un activo y decide si operar.
        id_activo: id de la BD. Si no se pasa, el NLPWorker lo resuelve por simbolo.
        modo_simulacion=True -> imprime la accion sin enviar orden real.
        """
        print(f"\n{'='*60}")
        print(f"  GERENTE — Evaluando {simbolo_interno}")
        print(f"{'='*60}")

        # 1. Filtro de seguridad previo (RiskModule)
        if not self.risk.filtro_seguridad(simbolo_interno):
            motivo = f"Bloqueado por filtro_seguridad antes de evaluar Obreros."
            self._guardar_auditoria(simbolo_interno, 0.0, 0.0, 0.0, 0.0,
                                    "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # 2. Obtener pesos desde BD
        params    = self.db.get_parametros()
        w_trend   = params.get("TENDENCIA.peso_voto",  0.30)
        w_nlp     = params.get("NLP.peso_voto",        0.20)
        w_flow    = params.get("ORDER_FLOW.peso_voto", 0.50)

        # Normalizar a 1.0 aunque los pesos cambien en la BD
        total_pesos = w_trend + w_nlp + w_flow
        w_trend /= total_pesos
        w_nlp   /= total_pesos
        w_flow  /= total_pesos

        print(f"\n[GERENTE] Pesos normalizados: "
              f"Tendencia={w_trend:.2f}  NLP={w_nlp:.2f}  Flow={w_flow:.2f}  "
              f"[Suma={w_trend+w_nlp+w_flow:.2f}]")

        # 3. Reflejo de Combate: Trigger de Volatilidad
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        volatil_ahora = self._medir_volatilidad(simbolo_broker)
        forzar_nlp = False
        
        if volatil_ahora >= 3.0:
            print(f"[GERENTE] ⚡ PICO DE VOLATILIDAD IDENTIFICADO (Ratio: {volatil_ahora:.1f}x)")
            print(f"[GERENTE] Forzando re-evaluacion macro de emergencia...")
            forzar_nlp = True

        # 4. Consultar Obreros
        print("\n[GERENTE] Consultando Obreros...")
        v_trend  = self.trend.analizar(simbolo_interno)
        v_nlp    = self.nlp.analizar(simbolo_interno, id_activo=id_activo, forzar_refresh=forzar_nlp)
        v_flow   = self.flow.analizar(simbolo_interno)
        v_volume = self.volume.analizar(simbolo_interno)
        
        # --- Juez de Persistencia (Hurst) ---
        res_hurst = self.hurst.analizar(simbolo_interno)
        h_val = res_hurst['h']
        h_estado = res_hurst['estado']

        # 5. Reflejo de Combate: Alerta de Divergencia
        if self._detectar_divergencia(simbolo_interno, v_trend, v_nlp):
            motivo = "Bloqueado por DIVERGENCIA extrema entre Trend e IA."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    0.0, "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # --- VETO DE HURST ---
        if h_estado != "PERSISTENTE":
            motivo = f"VETO HURST: Mercado en estado {h_estado} (H: {h_val:.4f}). Abortando por falta de persistencia."
            print(f"[GERENTE] 🛑 {motivo}")
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow, 0.0, "VETO_HURST", motivo)
            return {"decision": "VETO_HURST", "veredicto": 0.0, "motivo": motivo}

        # --- RE-BALANCEO PARA VOLUMEN (V5.0) ---
        # Pesos Propuestos: Trend (40%), NLP (30%), Flow (10%), Volume (20%)
        # Nota: W_FLOW se mantiene bajo por ser L2.
        veredicto = round((v_trend * 0.40) + (v_nlp * 0.30) + (v_flow * 0.10) + (v_volume['voto'] * 0.20), 4)

        # 6. Decisión y Telemetría Extra
        # Prep data para notificaciones
        vol_map = {
            "poc": v_volume['poc'],
            "va": f"{v_volume['val']} - {v_volume['vah']}",
            "contexto": v_volume['contexto'],
            "ajuste": v_volume['ajuste']
        }
        # 5. Decisión
        umbral = params.get("GERENTE.umbral_disparo", 0.45)
        
        print(f"\n[GERENTE] Votos    : Trend={v_trend:+.2f}  NLP={v_nlp:+.2f}  Flow={v_flow:+.2f}")
        print(f"[GERENTE] Veredicto: {veredicto:+.4f}  (umbral: ±{umbral})")
        
        if abs(veredicto) < umbral:
            # --- NUEVO REPORTE DE GATILLO Y PROXIMIDAD ---
            confianza = abs(veredicto)
            if 0.38 <= confianza < 0.45:
                # Recuperar Hurst y Volumen para telemetria
                notificar_proximidad(simbolo_interno, veredicto, h_val, h_estado, vol_map)
            elif 0.30 <= confianza < 0.38:
                notificar_oportunidad_detectada(simbolo_interno, veredicto)
            
            if confianza >= 0.30:
                motivo = f"Oportunidad detectada ({confianza:.2f}), pero debajo del umbral ({umbral})."
            else:
                motivo = f"Veredicto {veredicto:+.4f} insuficiente (Umbral: {umbral})"
            
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "IGNORADO", motivo)
            return {"decision": "IGNORADO", "veredicto": veredicto, "motivo": motivo}

        # 6. Aprobado — calcular dirección y lotaje
        direccion = "COMPRA" if veredicto > 0 else "VENTA"
        
        # --- NUEVA LOGICA DE RIESGO DINAMICO ---
        simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        
        # 6.a Calculo de SL y TP via ATR
        sl, tp = self.risk.obtener_sl_tp_atr(simbolo_broker, direccion)
        if sl is None or tp is None:
            motivo = "Error calculando SL/TP via ATR. Orden abortada."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # 6.b Calculo de Lotaje Dinamico (Confianza)
        lotes = self.risk.calcular_lotes_dinamicos(veredicto)
        
        print(f"[GERENTE] Riesgo Dinamico -> Conviccion: {abs(veredicto)*100:.1f}% | Lotes: {lotes} | SL: {sl:.4f} | TP: {tp:.4f}")

        # 7. Justificación Glass Box
        motivo = (
            f"Veredicto Ensemble: {veredicto:+.4f} supera umbral {umbral}. "
            f"Señal de {direccion}. "
            f"Votos: Trend={v_trend:+.2f} (×{w_trend:.2f}), "
            f"NLP={v_nlp:+.2f} (×{w_nlp:.2f}), "
            f"Flow={v_flow:+.2f} (×{w_flow:.2f}). "
            f"SL={sl:.2f}  TP={tp:.2f}  Lotes={lotes}."
        )

        # 8. Ejecutar o simular
        if modo_simulacion:
            print(f"\n[GERENTE] Simulando ejecucion de {direccion} con {lotes} lotes")
            
            # Obtener balance actual para la notificación
            import MetaTrader5 as mt5_api
            acc_info = mt5_api.account_info()
            balance = acc_info.balance if acc_info else 0.0
            
            notificar_orden_ejecutada(
                simbolo=simbolo_interno, 
                direccion=direccion, 
                lotes=lotes, 
                ticket=999999, # Ticket ficticio para simulacion
                precio=self.mt5.obtener_precio_actual(self.db.obtener_simbolo_broker(simbolo_interno))['ask'] if direccion == "COMPRA" else self.mt5.obtener_precio_actual(self.db.obtener_simbolo_broker(simbolo_interno))['bid'],
                sl=sl, 
                tp=tp, 
                veredicto=veredicto, 
                v_trend=v_trend, 
                v_nlp=v_nlp, 
                balance=balance,
                hurst_h=h_val,
                hurst_estado=h_estado,
                vol_poc=vol_map['poc'],
                vol_va=vol_map['va'],
                vol_ctx=vol_map['contexto'],
                vol_ajuste=vol_map['ajuste']
            )
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "EJECUTADO", motivo)
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
                notificar_rechazo_broker(simbolo_interno, retcode, causa)
                
                self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                        veredicto, "ERROR_BROKER", err_msg)
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
                    self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow, veredicto, "ERROR_BROKER", err_msg)
                    return {"decision": "ERROR_BROKER", "motivo": err_msg}
                
                # Obtener detalles reales
                pos = posiciones[0]
                precio_real = pos.price_open
                info_acc = mt5_api.account_info()
                balance_real = info_acc.balance if info_acc else 0.0

                # --- NUEVO: Cálculo de Probabilidad ---
                # Confianza [0.45 - 1.0] -> Probabilidad [65% - 98%]
                # Fórmula: 65 + ((abs(veredicto) - 0.45) / (1.0 - 0.45)) * (98 - 65)
                confianza = abs(veredicto)
                prob_exito = 65 + ((confianza - 0.45) / (0.55)) * (33)
                prob_exito = max(65, min(98, round(prob_exito, 1)))

                notificar_orden_ejecutada(
                    simbolo_interno, direccion, lotes, ticket, precio_real, 
                    sl, tp, veredicto, v_trend, v_nlp, balance_real,
                    hurst_h=h_val, hurst_estado=h_estado,
                    vol_poc=vol_map['poc'], vol_va=vol_map['va'],
                    vol_ctx=vol_map['contexto'], vol_ajuste=vol_map['ajuste']
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
                                        veredicto, "EJECUTADO", motivo)
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
        import MetaTrader5 as mt5_api
        from datetime import datetime, timedelta

        # 1. Obtener trades cerrados sin resultado en la BD
        self.db.cursor.execute("""
            SELECT ticket_mt5, veredicto_apertura, probabilidad_est, precio_entrada, take_profit, stop_loss
            FROM registro_operaciones 
            WHERE resultado_final IS NULL AND ticket_mt5 != 999999
        """)
        pendientes = self.db.cursor.fetchall()
        if not pendientes:
            return

        # 2. Consultar historial de MT5 (últimas 24h para estar seguros)
        from_date = datetime.now() - timedelta(days=1)
        history = mt5_api.history_deals_get(from_date, datetime.now())
        if history is None:
            return

        for ticket, veredicto, prob, p_ent, tp, sl in pendientes:
            # Buscar el deal de salida para este ticket de orden
            # MT5: El deal de salida suele tener el entry == DEAL_ENTRY_OUT
            deals = [d for d in history if d.order == ticket and d.entry == mt5_api.DEAL_ENTRY_OUT]
            
            if deals:
                deal = deals[0]
                ganancia = deal.profit
                resultado = "GANADO" if ganancia > 0 else "PERDIDO"
                
                # Calcular Divergencia de Precisión
                # Si probabilidad_est era 90% y ganó, divergencia = 10 (pequeña)
                # Si era 90% y perdió, divergencia = 90 (grande)
                exito_real = 100.0 if resultado == "GANADO" else 0.0
                divergencia = abs(exito_real - float(prob))
                
                print(f"[GERENTE] 📊 Auditoria de Cierre #{ticket}: Result={resultado} | Prob={prob}% | Div={divergencia:.1f}")
                
                try:
                    self.db.cursor.execute("""
                        UPDATE registro_operaciones 
                        SET resultado_final = %s, divergencia_precision = %s, pnl_usd = %s
                        WHERE ticket_mt5 = %s
                    """, (resultado, divergencia, ganancia, ticket))
                    self.db.conn.commit()
                except Exception as e:
                    print(f"[GERENTE] Error actualizando precision de cierre #{ticket}: {e}")

    # ------------------------------------------------------------------
    # Auditoría obligatoria (Glass Box)
    # ------------------------------------------------------------------

    def _guardar_auditoria(self, simbolo: str, v_trend: float, v_nlp: float,
                            v_flow: float, veredicto: float,
                            decision: str, motivo: str):
        """Guarda la auditoría completa en registro_senales. SIEMPRE se ejecuta."""
        try:
            self.db.guardar_senal(simbolo, v_trend, v_nlp, v_flow,
                                  veredicto, decision, motivo)
            
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
            notificar_divergencia(simbolo, v_trend, v_nlp)
            return True
        return False
