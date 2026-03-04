import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.risk_module import RiskModule
from workers.worker_trend import TrendWorker
from workers.worker_nlp import NLPWorker
from workers.worker_flow import OrderFlowWorker
from config.notifier import (
    notificar_zona_caliente,
    notificar_orden_ejecutada,
    notificar_error_critico,
    notificar_divergencia,
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
        self.flow  = OrderFlowWorker(db, mt5)

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
        v_trend = self.trend.analizar(simbolo_interno)
        v_nlp   = self.nlp.analizar(simbolo_interno, id_activo=id_activo, forzar_refresh=forzar_nlp)
        v_flow  = self.flow.analizar(simbolo_interno)

        # 5. Reflejo de Combate: Alerta de Divergencia
        if self._detectar_divergencia(simbolo_interno, v_trend, v_nlp):
            motivo = "Bloqueado por DIVERGENCIA extrema entre Trend e IA."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    0.0, "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        # 6. Suma ponderada -> Veredicto Final
        veredicto = round((v_trend * w_trend) + (v_nlp * w_nlp) + (v_flow * w_flow), 4)
        umbral    = params.get("GERENTE.umbral_disparo", 0.65)

        print(f"\n[GERENTE] Votos    : Trend={v_trend:+.2f}  NLP={v_nlp:+.2f}  Flow={v_flow:+.2f}")
        print(f"[GERENTE] Veredicto: {veredicto:+.4f}  (umbral: ±{umbral})")

        # 5. Decisión
        if abs(veredicto) < umbral:
            motivo = (f"Veredicto {veredicto:+.4f} no supera el umbral +-{umbral}. "
                      f"Votos: Trend={v_trend:+.2f}, NLP={v_nlp:+.2f}, Flow={v_flow:+.2f}.")
            print(f"\n[GERENTE] IGNORADO — {motivo}")

            # ⚠️ Alerta de Zona Caliente si veredicto supera 0.50
            UMBRAL_OBSERVACION = 0.50
            if abs(veredicto) >= UMBRAL_OBSERVACION:
                notificar_zona_caliente(simbolo_interno, veredicto, v_trend, v_nlp, v_flow)

            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "IGNORADO", motivo)
            return {"decision": "IGNORADO", "veredicto": veredicto, "motivo": motivo}

        # 6. Aprobado — calcular dirección y lotaje
        direccion = "COMPRA" if veredicto > 0 else "VENTA"
        ratio_tp  = params.get("GERENTE.ratio_tp", 2.0)

        precio_actual = self.mt5.obtener_precio_actual(
            self.db.obtener_simbolo_broker(simbolo_interno)
        )
        if not precio_actual:
            motivo = "No se pudo obtener precio actual. Orden abortada."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

        ask = precio_actual["ask"]
        bid = precio_actual["bid"]
        sl_distancia = 5.0  # USD de SL por defecto (configurable en BD)

        sl = (ask - sl_distancia) if direccion == "COMPRA" else (bid + sl_distancia)
        tp = (ask + sl_distancia * ratio_tp) if direccion == "COMPRA" \
             else (bid - sl_distancia * ratio_tp)

        lotes = self.risk.calcular_lotes(simbolo_interno, sl)
        if not lotes:
            motivo = "RiskModule no pudo calcular lotaje. Orden abortada."
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "CANCELADO_RIESGO", motivo)
            return {"decision": "CANCELADO_RIESGO", "motivo": motivo}

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
            notificar_orden_ejecutada(simbolo_interno, direccion, lotes, veredicto, motivo)
            self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                    veredicto, "EJECUTADO", motivo)
            return {"decision": direccion, "lotes": lotes, "veredicto": veredicto, "motivo": motivo}
        else:
            ticket = self.mt5.enviar_orden(
                self.db.obtener_simbolo_broker(simbolo_interno),
                direccion, lotes, sl, tp
            )
            
            if ticket is None:
                err_msg = f"MT5 ROJA — Orden Rechazada (AutoTrading off o sin margen). Ticket: None"
                print(f"\n[GERENTE] ERROR CRITICO: {err_msg}")
                notificar_error_critico("Broker/MT5", f"{simbolo_interno} {direccion} falló. Revisa terminal MT5 (AutoTrading = ON?).")
                self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                        veredicto, "ERROR_BROKER", err_msg)
                return {"decision": "ERROR_BROKER", "motivo": err_msg}
            else:
                print(f"\n[GERENTE] ORDEN ENVIADA — Ticket: {ticket}")
                notificar_orden_ejecutada(simbolo_interno, direccion, lotes, veredicto, motivo)
                self._guardar_auditoria(simbolo_interno, v_trend, v_nlp, v_flow,
                                        veredicto, "EJECUTADO", motivo)
                return {"decision": direccion, "lotes": lotes, "veredicto": veredicto, "motivo": motivo}

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
