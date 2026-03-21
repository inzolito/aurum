"""
LabEvaluator — V18.0
Evaluador del Laboratorio de Activos.

Aplica los votos ya calculados por los workers a los parámetros propios de cada lab.
No re-ejecuta workers, no escribe en registro_senales ni registro_operaciones.
Aislado completamente de la lógica de producción.
"""

import time
from datetime import datetime
from config.db_connector import DBConnector


class LabEvaluator:
    """
    Motor de evaluación para el Laboratorio de Activos.

    Diseñado para ser llamado al FINAL del ciclo normal del Manager,
    DESPUÉS de que producción ya evaluó. Usa los votos recolectados
    durante el ciclo sin re-ejecutar workers.
    """

    def __init__(self, db: DBConnector):
        self.db = db

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------

    def evaluar_todos(self, votos_por_activo: dict, precios_actuales: dict):
        """
        Evalúa todos los labs ACTIVOS usando los votos ya calculados.

        votos_por_activo = {
            'XAUUSD': {'trend': 0.8, 'nlp': 0.4, 'sniper': 0.2,
                       'hurst': 0.65, 'volume': 0.0, 'cross': 0.0},
            ...
        }
        precios_actuales = {
            'XAUUSD': {'bid': 2350.20, 'ask': 2350.45},
            ...
        }
        """
        t_inicio = time.time()
        try:
            labs = self.db.get_labs_activos()
            if not labs:
                return

            # Cerrar posiciones abiertas que tocaron SL/TP
            self._gestionar_posiciones_abiertas_lab(precios_actuales)

            for lab in labs:
                self._evaluar_lab(lab, votos_por_activo, precios_actuales)

            elapsed = int((time.time() - t_inicio) * 1000)
            print(f"[LAB] Ciclo evaluacion: {elapsed}ms | {len(labs)} labs")
            if elapsed > 2000:
                print(f"[LAB] ALERTA: ciclo supero 2000ms ({elapsed}ms)")

        except Exception as e:
            print(f"[LAB] Error en evaluar_todos: {e}")

    # ------------------------------------------------------------------
    # Evaluación por lab
    # ------------------------------------------------------------------

    def _evaluar_lab(self, lab: dict, votos_por_activo: dict, precios_actuales: dict):
        """Evalúa todos los activos de un lab."""
        lab_id = lab["id"]
        try:
            params = self.db.get_lab_params(lab_id)
        except Exception as e:
            print(f"[LAB] Error cargando params del lab {lab_id}: {e}")
            return

        for activo_info in lab["activos"]:
            activo_id = activo_info["id"]
            simbolo = activo_info["simbolo"]

            if simbolo not in votos_por_activo:
                # Activo del lab no fue evaluado en este ciclo (no en producción)
                continue

            votos = votos_por_activo[simbolo]

            try:
                self._evaluar_activo_en_lab(
                    lab_id, activo_id, simbolo, votos, precios_actuales, params
                )
            except Exception as e:
                print(f"[LAB] Error evaluando {simbolo} en lab {lab_id}: {e}")

    def _evaluar_activo_en_lab(self, lab_id: int, activo_id: int, simbolo: str,
                                votos: dict, precios_actuales: dict, params: dict):
        """Aplica pesos del lab, decide y guarda señal."""
        # 1. Calcular veredicto con pesos propios del lab
        veredicto, pesos_usados = self._aplicar_pesos_lab(votos, params)

        # 2. Umbral propio del lab
        umbral = float(params.get("LAB.umbral_disparo",
                                   params.get("GERENTE.umbral_disparo", 0.45)))

        # 3. Decidir
        if abs(veredicto) < umbral:
            motivo = f"[LAB] Veredicto {veredicto:+.4f} insuficiente (umbral: {umbral})"
            decision = "IGNORADO"
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                decision, motivo, umbral, pesos_usados
            )
            return

        # 4. Verificar precio disponible
        precio_info = precios_actuales.get(simbolo)
        if not precio_info:
            motivo = f"[LAB] Sin precio disponible para {simbolo}"
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "CANCELADO_RIESGO", motivo, umbral, pesos_usados
            )
            return

        # 5. Decidir dirección
        direccion = "COMPRA" if veredicto > 0 else "VENTA"
        tipo_orden = "BUY" if veredicto > 0 else "SELL"

        # 6. Anti-duplicado
        posiciones_abiertas = self.db.get_lab_operaciones_abiertas(lab_id)
        ya_abierta = any(p["activo_id"] == activo_id for p in posiciones_abiertas)
        if ya_abierta:
            motivo = f"[LAB] Posicion ya abierta en {simbolo} — anti-duplicado activo"
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "CANCELADO_RIESGO", motivo, umbral, pesos_usados
            )
            return

        # 7. Guardar señal aprobada
        motivo = (
            f"[LAB] Veredicto {veredicto:+.4f} >= umbral {umbral}. "
            f"Señal de {direccion}. "
            f"Trend={votos.get('trend',0):+.2f} "
            f"NLP={votos.get('nlp',0):+.2f} "
            f"Sniper={votos.get('sniper',0):+.2f} "
            f"Macro={votos.get('macro',0):+.2f}"
        )
        senal_id = self.db.guardar_lab_senal(
            lab_id, activo_id, {**votos, "veredicto": veredicto},
            "EJECUTADO", motivo, umbral, pesos_usados
        )

        # 8. Simular entrada
        self._simular_entrada(
            lab_id, activo_id, simbolo, tipo_orden,
            precio_info, params, veredicto, senal_id, motivo
        )

    # ------------------------------------------------------------------
    # Cálculo de veredicto con pesos del lab
    # ------------------------------------------------------------------

    def _aplicar_pesos_lab(self, votos: dict, params: dict) -> tuple:
        """
        Aplica pesos propios del lab a los votos existentes.
        Retorna (veredicto: float, pesos_usados: dict).
        """
        p_trend  = float(params.get("TENDENCIA.peso_voto", 0.50))
        p_nlp    = float(params.get("NLP.peso_voto",       0.30))
        p_sniper = float(params.get("SNIPER.peso_voto",    0.20))
        p_macro  = float(params.get("MACRO.peso_voto",     0.20))

        v_trend  = float(votos.get("trend",  0.0))
        v_nlp    = float(votos.get("nlp",    0.0))
        v_sniper = float(votos.get("sniper", 0.0))
        v_hurst  = float(votos.get("hurst",  0.5))
        v_macro  = float(votos.get("macro",  0.0))

        veredicto = round(
            (v_trend  * p_trend)  +
            (v_nlp    * p_nlp)    +
            (v_sniper * p_sniper) +
            (v_macro  * p_macro),
            4
        )

        # Penalización Hurst (igual que en producción)
        if 0.45 <= v_hurst <= 0.55:
            if veredicto > 0:
                veredicto = max(0.0, veredicto - 0.15)
            elif veredicto < 0:
                veredicto = min(0.0, veredicto + 0.15)

        veredicto = round(max(-1.0, min(1.0, veredicto)), 4)

        pesos_usados = {
            "trend": p_trend, "nlp": p_nlp, "sniper": p_sniper, "macro": p_macro
        }
        return veredicto, pesos_usados

    # ------------------------------------------------------------------
    # Simulación de entrada
    # ------------------------------------------------------------------

    def _simular_entrada(self, lab_id: int, activo_id: int, simbolo: str,
                          tipo_orden: str, precio_info: dict, params: dict,
                          veredicto: float, senal_id: int, justificacion: str):
        """
        Calcula SL/TP con parámetros del lab, aplica spread simulado,
        y guarda la operación virtual.
        """
        try:
            # Precio con spread simulado
            spread_pips = float(params.get("LAB.spread_pips_default", 20.0))
            punto = self._get_punto(simbolo)
            spread_precio = spread_pips * punto

            if tipo_orden == "BUY":
                precio_entrada = float(precio_info.get("ask", precio_info.get("bid", 0))) + spread_precio
            else:
                precio_entrada = float(precio_info.get("bid", 0)) - spread_precio

            if precio_entrada <= 0:
                print(f"[LAB] Precio inválido para {simbolo}: {precio_entrada}")
                return

            # SL / TP basado en parámetros del lab
            ratio_tp       = float(params.get("LAB.ratio_tp",           2.0))
            sl_mult        = float(params.get("LAB.sl_atr_multiplier",  1.5))
            riesgo_pct     = float(params.get("LAB.riesgo_trade_pct",   1.5))

            # Distancia SL estimada: sl_mult * 0.5% del precio (aproximación sin ATR real)
            sl_distancia = precio_entrada * 0.005 * sl_mult
            tp_distancia = sl_distancia * ratio_tp

            if tipo_orden == "BUY":
                sl = round(precio_entrada - sl_distancia, 4)
                tp = round(precio_entrada + tp_distancia, 4)
            else:
                sl = round(precio_entrada + sl_distancia, 4)
                tp = round(precio_entrada - tp_distancia, 4)

            # Capital virtual del lab (leer balance actual)
            capital_lab = self._get_balance_virtual(lab_id)
            capital_riesgo = capital_lab * (riesgo_pct / 100.0)
            # Lotes aproximados (1 lote = $1000 de capital usado como referencia)
            lotes = round(max(0.01, capital_riesgo / 1000.0), 2)

            self.db.guardar_lab_operacion(
                lab_id=lab_id,
                activo_id=activo_id,
                senal_id=senal_id,
                tipo=tipo_orden,
                precio=precio_entrada,
                sl=sl,
                tp=tp,
                lotes=lotes,
                capital=capital_riesgo,
                justificacion=justificacion
            )
            print(f"[LAB] Lab {lab_id} | {simbolo} | {tipo_orden} @ {precio_entrada:.4f} | SL={sl:.4f} TP={tp:.4f}")

        except Exception as e:
            print(f"[LAB] Error en _simular_entrada para {simbolo} (lab={lab_id}): {e}")

    # ------------------------------------------------------------------
    # Gestión de posiciones abiertas (verificar SL/TP)
    # ------------------------------------------------------------------

    def _gestionar_posiciones_abiertas_lab(self, precios_actuales: dict):
        """
        Para cada lab_operacion ABIERTA:
          - Obtiene precio actual
          - Si precio toca TP → cerrar con resultado=TP
          - Si precio toca SL → cerrar con resultado=SL
          - Actualiza balance_virtual del lab
        """
        if not self.db.cursor:
            return
        try:
            with self.db._lock:
                self.db.cursor.execute("""
                    SELECT lo.id, lo.lab_id, lo.activo_id, a.simbolo,
                           lo.tipo_orden, lo.precio_entrada,
                           lo.stop_loss, lo.take_profit,
                           lo.volumen_lotes, lo.capital_usado
                    FROM lab_operaciones lo
                    JOIN activos a ON a.id = lo.activo_id
                    WHERE lo.estado = 'ABIERTA'
                """)
                ops = self.db.cursor.fetchall()
        except Exception as e:
            print(f"[LAB] Error consultando posiciones abiertas: {e}")
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            return

        cols = ["id", "lab_id", "activo_id", "simbolo", "tipo_orden",
                "precio_entrada", "stop_loss", "take_profit",
                "volumen_lotes", "capital_usado"]

        for row in ops:
            op = dict(zip(cols, row))
            simbolo = op["simbolo"]
            precio_info = precios_actuales.get(simbolo)
            if not precio_info:
                continue

            # Precio mid para verificar SL/TP
            bid = float(precio_info.get("bid", 0))
            ask = float(precio_info.get("ask", bid))
            precio_actual = (bid + ask) / 2.0

            sl = float(op["stop_loss"])
            tp = float(op["take_profit"])
            precio_entrada = float(op["precio_entrada"])
            lotes = float(op["volumen_lotes"] or 1.0)

            resultado = None
            precio_salida = None

            if op["tipo_orden"] == "BUY":
                if precio_actual >= tp:
                    resultado = "TP"
                    precio_salida = tp
                elif precio_actual <= sl:
                    resultado = "SL"
                    precio_salida = sl
            else:  # SELL
                if precio_actual <= tp:
                    resultado = "TP"
                    precio_salida = tp
                elif precio_actual >= sl:
                    resultado = "SL"
                    precio_salida = sl

            if resultado and precio_salida:
                # Calcular PnL virtual aproximado
                diff = precio_salida - precio_entrada
                if op["tipo_orden"] == "SELL":
                    diff = -diff
                # PnL = diff * lotes * 1000 (aproximación genérica — sin pip value real)
                capital_usado = float(op["capital_usado"] or 1000.0)
                pnl = round(diff * lotes * 100.0, 2)  # Simplificado
                capital_inicial = float(op["capital_usado"] or 1000.0)
                roe = round((pnl / capital_inicial) * 100.0, 2) if capital_inicial else 0.0

                self.db.cerrar_lab_operacion(
                    op_id=op["id"],
                    precio_salida=precio_salida,
                    resultado=resultado,
                    pnl=pnl,
                    roe=roe
                )
                print(f"[LAB] Cierre {resultado}: Lab {op['lab_id']} | {simbolo} | PnL={pnl:+.2f}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_punto(self, simbolo: str) -> float:
        """Retorna el valor de un punto para el símbolo (simplificado)."""
        puntos = {
            "EURUSD": 0.00001, "GBPUSD": 0.00001, "USDJPY": 0.001,
            "GBPJPY": 0.001,   "USDCAD": 0.00001, "AUDUSD": 0.00001,
            "XAUUSD": 0.01,    "XAGUSD": 0.001,   "XTIUSD": 0.001,
            "XBRUSD": 0.001,   "US30":   0.1,      "US500":  0.01,
            "USTEC":  0.01,    "GER40":  0.01,
            "BTCUSD": 0.01,    "ETHUSD": 0.01,
        }
        return puntos.get(simbolo, 0.00001)

    def _get_balance_virtual(self, lab_id: int) -> float:
        """Lee el balance_virtual actual del lab desde BD."""
        if not self.db.cursor:
            return 3000.0
        with self.db._lock:
            try:
                self.db.cursor.execute(
                    "SELECT balance_virtual FROM laboratorios WHERE id = %s",
                    (lab_id,)
                )
                row = self.db.cursor.fetchone()
                return float(row[0]) if row else 3000.0
            except Exception:
                return 3000.0
