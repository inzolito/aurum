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

        # A3: Filtro universal — NLP=0.00 indica ausencia de datos de noticias.
        # "Sin información = sin trade" aplica a todos los labs sin excepción.
        v_nlp = float(votos.get("nlp", 0.0))
        if abs(v_nlp) < 0.05:
            motivo = (f"[LAB] FILTRO_NLP: voto NLP={v_nlp:+.2f} — "
                      f"sin datos de noticias. Entrada bloqueada universalmente.")
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "CONFIANZA_BAJA", motivo, umbral, pesos_usados
            )
            return

        # 3. Decidir
        if abs(veredicto) < umbral:
            motivo = f"[LAB] Veredicto {veredicto:+.4f} insuficiente (umbral: {umbral})"
            decision = "CONFIANZA_BAJA"
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
                "BLOQUEO_EXPOSICION", motivo, umbral, pesos_usados
            )
            return

        # 5. Decidir dirección
        direccion = "COMPRA" if veredicto > 0 else "VENTA"
        tipo_orden = "BUY" if veredicto > 0 else "SELL"

        # A4: Filtro universal — Trend en contradicción con la dirección decidida.
        # No entrar largo cuando el análisis técnico es bajista, ni viceversa.
        v_trend = float(votos.get("trend", 0.0))
        if tipo_orden == "BUY" and v_trend < -0.10:
            motivo = (f"[LAB] FILTRO_TREND: BUY rechazado — "
                      f"Trend={v_trend:+.2f} indica tendencia bajista.")
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "CONFIANZA_BAJA", motivo, umbral, pesos_usados
            )
            return
        if tipo_orden == "SELL" and v_trend > +0.10:
            motivo = (f"[LAB] FILTRO_TREND: SELL rechazado — "
                      f"Trend={v_trend:+.2f} indica tendencia alcista.")
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "CONFIANZA_BAJA", motivo, umbral, pesos_usados
            )
            return

        # 6. Anti-duplicado
        posiciones_abiertas = self.db.get_lab_operaciones_abiertas(lab_id)
        ya_abierta = any(p["activo_id"] == activo_id for p in posiciones_abiertas)
        if ya_abierta:
            motivo = f"[LAB] Posicion ya abierta en {simbolo} — anti-duplicado activo"
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "BLOQUEO_EXPOSICION", motivo, umbral, pesos_usados
            )
            return

        # A5: Cooldown universal — ≥3 SLs en las últimas 4h en este lab+activo.
        # Evita acumular pérdidas consecutivas sin pausa cuando el mercado
        # está en contratendencia con las señales del sistema.
        if self._en_cooldown(lab_id, activo_id):
            motivo = (f"[LAB] COOLDOWN: ≥3 SLs en las últimas 4h para {simbolo} "
                      f"en este lab. Pausando entradas 4h.")
            self.db.guardar_lab_senal(
                lab_id, activo_id, {**votos, "veredicto": veredicto},
                "BLOQUEO_EXPOSICION", motivo, umbral, pesos_usados
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

        # 8. Simular entrada — incluir análisis IA en justificación
        import json as _json
        justificacion_json = _json.dumps({
            "ia_texto": votos.get("nlp_razonamiento", ""),
            "motivo_lab": motivo,
        }, ensure_ascii=False)
        self._simular_entrada(
            lab_id, activo_id, simbolo, tipo_orden,
            precio_info, params, veredicto, senal_id, justificacion_json
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
        p_macro  = max(0.10, float(params.get("MACRO.peso_voto", 0.20)))  # B1: mínimo 0.10 forzado

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

            # TP1: punto medio entre entrada y TP2 (objetivo parcial al 50%)
            tp1 = round((precio_entrada + tp) / 2.0, 4)

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
                justificacion=justificacion,
                tp1=tp1,
            )
            print(f"[LAB] Lab {lab_id} | {simbolo} | {tipo_orden} @ {precio_entrada:.4f} | SL={sl:.4f} TP1={tp1:.4f} TP={tp:.4f}")

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
                           lo.stop_loss, lo.take_profit, lo.take_profit_1,
                           lo.volumen_lotes, lo.capital_usado,
                           lo.tp1_alcanzado
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
                "precio_entrada", "stop_loss", "take_profit", "take_profit_1",
                "volumen_lotes", "capital_usado", "tp1_alcanzado"]

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
            tp1 = float(op["take_profit_1"]) if op["take_profit_1"] is not None else None
            tp1_alcanzado = bool(op["tp1_alcanzado"])
            precio_entrada = float(op["precio_entrada"])
            lotes = float(op["volumen_lotes"] or 1.0)
            capital_usado = float(op["capital_usado"] or 1000.0)

            # ── TP1: cerrar 50% de la posición cuando precio alcanza el primer objetivo
            if tp1 is not None and not tp1_alcanzado:
                tp1_hit = (op["tipo_orden"] == "BUY" and precio_actual >= tp1) or \
                          (op["tipo_orden"] == "SELL" and precio_actual <= tp1)
                if tp1_hit:
                    tp1_dist = abs(tp1 - precio_entrada)
                    sl_dist_actual = abs(precio_entrada - sl)
                    capital_half = capital_usado / 2.0
                    if sl_dist_actual > 0:
                        pnl_parcial = round((tp1_dist / sl_dist_actual) * capital_half, 2)
                    else:
                        tp_dist = abs(tp - precio_entrada)
                        pnl_parcial = round((tp1_dist / tp_dist) * capital_half, 2) if tp_dist > 0 else 0.0
                    self.db.marcar_tp1_lab(op["id"], pnl_parcial)
                    self.db.actualizar_sl_lab(op["id"], precio_entrada)  # persiste BE en BD
                    tp1_alcanzado = True
                    sl = precio_entrada  # BE activo desde ahora
                    capital_usado = capital_half  # solo queda el 50%
                    print(f"[LAB] TP1 alcanzado: Lab {op['lab_id']} | {simbolo} | "
                          f"Parcial +{pnl_parcial:.2f} | SL movido a BE | Resta 50%")

            # ── Breakeven: mover SL a entrada cuando ganancia >= 50% del capital en riesgo
            sl_en_be = (op["tipo_orden"] == "BUY" and sl >= precio_entrada) or \
                       (op["tipo_orden"] == "SELL" and sl <= precio_entrada and sl != 0)
            if not sl_en_be:
                sl_dist = abs(precio_entrada - sl)
                if sl_dist > 0:
                    if op["tipo_orden"] == "BUY":
                        diff_actual = precio_actual - precio_entrada
                    else:
                        diff_actual = precio_entrada - precio_actual
                    pnl_flotante = (diff_actual / sl_dist) * capital_usado
                    roe_flotante = pnl_flotante / capital_usado if capital_usado else 0
                    if roe_flotante >= 0.50:  # ganancia >= 50% del capital en riesgo
                        self.db.actualizar_sl_lab(op["id"], precio_entrada)
                        sl = precio_entrada
                        print(f"[LAB] Breakeven: Lab {op['lab_id']} | {simbolo} | SL movido a {precio_entrada:.4f} (ROE flotante {roe_flotante*100:.1f}%)")

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
                pnl, roe = self._calcular_pnl(
                    op["tipo_orden"], precio_entrada, precio_salida, lotes, capital_usado, sl=sl, tp=tp
                )
                self.db.cerrar_lab_operacion(
                    op_id=op["id"],
                    precio_salida=precio_salida,
                    resultado=resultado,
                    pnl=pnl,
                    roe=roe
                )
                print(f"[LAB] Cierre {resultado}: Lab {op['lab_id']} | {simbolo} | PnL={pnl:+.2f}")
            else:
                # Posición abierta — actualizar P&L flotante con precio actual
                precio_mid = (bid + ask) / 2.0
                pnl_float, roe_float = self._calcular_pnl(
                    op["tipo_orden"], precio_entrada, precio_mid, lotes, capital_usado, sl=sl, tp=tp
                )
                self.db.actualizar_pnl_flotante_lab(op["id"], pnl_float, roe_float)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calcular_pnl(self, tipo: str, precio_entrada: float, precio_salida: float,
                      lotes: float, capital_usado: float, sl: float = None, tp: float = None) -> tuple:
        """
        Calcula PnL proporcional al capital en riesgo real.
        - sl_dist > 0: PnL = (diff / sl_dist) * capital_usado
            → SL tocado = -capital_usado. TP tocado = +capital_usado * ratio_tp.
        - sl_dist = 0 (breakeven) y tp disponible: PnL = (diff / tp_dist) * capital_usado
            → Muestra progreso hacia el TP como fracción del capital.
        - Fallback: porcentaje del precio.
        """
        # C1: guard — capital negativo o cero produce signos incoherentes
        if capital_usado <= 0:
            return 0.0, 0.0

        if tipo == "BUY":
            diff = precio_salida - precio_entrada
        else:
            diff = precio_entrada - precio_salida  # positivo = ganancia para SELL

        if sl is not None and precio_entrada > 0:
            sl_dist = abs(precio_entrada - sl)
            if sl_dist > 0:
                pnl = round((diff / sl_dist) * capital_usado, 2)
                roe = round((pnl / capital_usado) * 100.0, 2)
                return pnl, roe
            # sl_dist = 0 → breakeven activo: usar TP como referencia de escala.
            # ROE = (diff / tp_dist) * 100 — signo siempre consistente con PnL.
            if tp is not None:
                tp_dist = abs(tp - precio_entrada)
                if tp_dist > 0:
                    pnl = round((diff / tp_dist) * capital_usado, 2)
                    roe = round((pnl / capital_usado) * 100.0, 2)
                    return pnl, roe

        # Fallback: porcentaje del precio (sin SL disponible)
        notional = lotes * 1000.0
        pnl_diff = precio_salida - precio_entrada if tipo == "BUY" else precio_entrada - precio_salida
        pnl = round((pnl_diff / precio_entrada) * notional, 2) if precio_entrada else 0.0
        roe = round((pnl / capital_usado) * 100.0, 2) if capital_usado else 0.0
        return pnl, roe

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

    def _en_cooldown(self, lab_id: int, activo_id: int) -> bool:
        """
        A5: Retorna True si el activo acumula ≥3 SLs en las últimas 4h en este lab.
        Previene entradas repetidas cuando el mercado está en contratendencia.
        """
        if not self.db.cursor:
            return False
        try:
            with self.db._lock:
                self.db.cursor.execute("""
                    SELECT COUNT(*) FROM lab_operaciones
                    WHERE lab_id    = %s
                      AND activo_id = %s
                      AND resultado = 'SL'
                      AND tiempo_salida >= NOW() - INTERVAL '4 hours'
                """, (lab_id, activo_id))
                row = self.db.cursor.fetchone()
                return (row[0] if row else 0) >= 3
        except Exception as e:
            print(f"[LAB] Error verificando cooldown lab={lab_id} activo={activo_id}: {e}")
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            return False
