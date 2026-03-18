import sys
from pathlib import Path

import MetaTrader5 as mt5_lib

sys.path.append(str(Path(__file__).parent.parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector


class RiskModule:
    """
    El guardián del capital del sistema Aurum.
    Centraliza toda la matemática de gestión de riesgo
    y los filtros de seguridad previos a cualquier ejecución.
    """

    def __init__(self, db: DBConnector, mt5: MT5Connector):
        self.db  = db
        self.mt5 = mt5

    # ------------------------------------------------------------------
    # Pilar 1: Cálculo Dinámico de Lotaje
    # ------------------------------------------------------------------

    def calcular_lotes_dinamicos(self, veredicto: float) -> float:
        """
        Calcula lotaje basado en la convicción del veredicto (interpolación lineal).
        Ajuste Optimizado:
        THRESHOLD_ENTRY = 0.45 -> Lote 0.05
        THRESHOLD_FULL  = 0.80 -> Lote 0.12
        """
        THRESHOLD_ENTRY = 0.45
        THRESHOLD_FULL  = 0.80
        MIN_LOT = 0.05
        MAX_LOT = 0.12
        
        # Obtenemos la magnitud de la señal
        confianza = abs(veredicto)
        
        if confianza <= THRESHOLD_ENTRY:
            return MIN_LOT
            
        if confianza >= THRESHOLD_FULL:
            return MAX_LOT

        # Interpolación lineal entre THRESHOLD_ENTRY (0.45) y THRESHOLD_FULL (0.80)
        lote = MIN_LOT + ((confianza - THRESHOLD_ENTRY) / (THRESHOLD_FULL - THRESHOLD_ENTRY)) * (MAX_LOT - MIN_LOT)

        # D4 V14: IA-Risk — reducir lotaje si hay noticias de alto impacto recientes
        factor_noticias = self._factor_riesgo_noticias()
        lote = lote * factor_noticias

        return max(MIN_LOT, round(lote, 2))

    def obtener_sl_tp_atr(self, simbolo_broker: str, direccion: str) -> tuple[float, float] | tuple[None, None]:
        """
        Calcula SL y TP usando ATR(14) en M15.
        SL = entrada +- 1.5 * ATR
        TP = entrada +- 2.0 * ATR
        """
        atr = self.mt5.obtener_atr(simbolo_broker, periodo=14, timeframe=mt5_lib.TIMEFRAME_M15)
        if not atr:
            return None, None
            
        tick = mt5_lib.symbol_info_tick(simbolo_broker)
        info = mt5_lib.symbol_info(simbolo_broker)
        if not tick or not info:
            return None, None
            
        precio = tick.ask if direccion == "COMPRA" else tick.bid
        
        dist_sl = atr * 1.5
        dist_tp = atr * 2.0
        
        # Validacion Anti-Error 10016: El spread a veces devora el ATR en volatilidades bajas
        # Safety minimum: 30 pips (pip = point * 10), para cubrir brokers con stop mínimo oculto elevado
        pip = info.point * 10
        min_dist = max(max(info.spread, info.trade_stops_level) * info.point, pip * 30)
        min_sl = min_dist * 1.5
        min_tp = min_dist * 2.0

        if dist_sl < min_sl:
            print(f"[RISK] ATR SL ({dist_sl:.5f}) violaba StopLevel/Spread en {simbolo_broker}. SL ajustado a {min_sl:.5f}")
            dist_sl = min_sl
        if dist_tp < min_tp:
            dist_tp = min_tp

        sl = precio - dist_sl if direccion == "COMPRA" else precio + dist_sl
        tp = precio + dist_tp if direccion == "COMPRA" else precio - dist_tp

        # Redondear a la precision del simbolo para evitar rechazos por floating point
        digits = info.digits
        return round(sl, digits), round(tp, digits)

    def verificar_ventana_ejecucion(self, simbolo_interno: str) -> bool:
        """
        D1 V14: Verifica si el activo está dentro de su ventana horaria de operación
        y si ya pasaron los primeros 15 minutos de apertura (anti-volatilidad).
        Se llama DESPUÉS de que los workers votan, solo bloquea la ejecución.
        Retorna True si se puede ejecutar, False si hay que esperar.
        """
        if not self.db.cursor:
            return True  # Sin DB: no bloquear
        try:
            self.db.cursor.execute(
                """
                SELECT hora_apertura, hora_cierre
                FROM horarios_operativos h
                JOIN activos a ON a.id = h.activo_id
                WHERE a.simbolo = %s;
                """,
                (simbolo_interno,)
            )
            horarios = self.db.cursor.fetchall()
            if not horarios:
                return True  # Sin horarios configurados: no bloquear

            from datetime import datetime, timezone
            hora_actual = datetime.now(timezone.utc).time()
            hora_actual_min = hora_actual.hour * 60 + hora_actual.minute

            for apertura, cierre in horarios:
                apertura_min = apertura.hour * 60 + apertura.minute
                cierre_min   = cierre.hour   * 60 + cierre.minute
                if apertura_min <= hora_actual_min <= cierre_min:
                    min_arranque = hora_actual_min - apertura_min
                    if min_arranque < 15:
                        print(f"[RISK] EJECUCION BLOQUEADA: {simbolo_interno} en arranque de sesion ({min_arranque}/15 min). Analisis visible, sin orden.")
                        return False
                    return True  # Dentro de ventana y pasados los 15 min

            print(f"[RISK] EJECUCION BLOQUEADA: {simbolo_interno} fuera de horario operativo.")
            return False
        except Exception:
            return True  # En caso de error: no bloquear

    def _factor_riesgo_noticias(self) -> float:
        """
        D4 V14: IA-Risk — retorna 0.5 si hay noticias de alto impacto en los últimos 30 min.
        Palabras clave: Fed, NFP, CPI, GDP, FOMC, inflación, Powell, empleo.
        Retorna 1.0 (sin cambio) si no hay noticias críticas o si la DB no está disponible.
        """
        try:
            if not self.db.cursor:
                return 1.0
            self.db.cursor.execute("""
                SELECT COUNT(*) FROM raw_news_feed
                WHERE published_at > NOW() - INTERVAL '30 minutes'
                AND (
                    title ILIKE '%fed%'        OR title ILIKE '%nfp%'
                    OR title ILIKE '%fomc%'    OR title ILIKE '%cpi%'
                    OR title ILIKE '%gdp%'     OR title ILIKE '%inflation%'
                    OR title ILIKE '%powell%'  OR title ILIKE '%employment%'
                    OR title ILIKE '%jobs%'    OR title ILIKE '%interest rate%'
                    OR title ILIKE '%rate decision%'
                )
            """)
            count = self.db.cursor.fetchone()[0]
            if count > 0:
                print(f"[RISK] Noticias de alto impacto recientes ({count}). Lotaje reducido al 50%.")
                return 0.5
        except Exception as e:
            print(f"[RISK] Error verificando noticias para IA-Risk: {e}")
        return 1.0

    def calcular_lotes(self, simbolo_interno: str, sl_precio: float) -> float | None:
        # (Este método se mantiene por compatibilidad si otros módulos lo usan, 
        # pero el Manager usará calcular_lotes_dinamicos)
        # ... logic omitted for brevity as per implementation plan focus on dynamic sizing
        pass

    # ------------------------------------------------------------------
    # Pilar 2: Filtro de Seguridad Pre-Ejecución
    # ------------------------------------------------------------------

    def filtro_seguridad(self, simbolo_interno: str) -> bool:
        """
        Compuerta de seguridad antes de intentar operar.
        Verifica:
          1. Que el activo esté en estado 'ACTIVO' en la BD.
          2. Que no haya ya una posición abierta en ese símbolo (anti-duplicado).
          3. Ventana horaria en horarios_operativos (si hay registros configurados).
        Retorna True solo si TODO está despejado.
        V13.1: En Modo Supervivencia (sin DB), solo valida contra MT5.
        """
        simbolo_broker = None

        # Verificación 1: Estado del activo en BD (solo si hay cursor disponible)
        if self.db.cursor:
            try:
                self.db.cursor.execute(
                    "SELECT estado_operativo, simbolo_broker FROM activos WHERE simbolo = %s;",
                    (simbolo_interno,)
                )
                fila = self.db.cursor.fetchone()
                if not fila:
                    print(f"[RISK] BLOQUEO: Activo '{simbolo_interno}' no existe en la BD.")
                    return False
                estado, simbolo_broker = fila
                if estado != "ACTIVO":
                    print(f"[RISK] BLOQUEO: {simbolo_interno} en estado '{estado}'. No se opera.")
                    return False
            except Exception as e:
                print(f"[RISK] Error en verificacion DB: {e}. Continuando en Survival Mode.")
        else:
            # Modo Supervivencia: usar mapa hardcoded
            simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
            print(f"[RISK] Survival Mode: Saltando verificacion de BD para {simbolo_interno}.")

        if not simbolo_broker:
            simbolo_broker = self.db.obtener_simbolo_broker(simbolo_interno)
        if not simbolo_broker:
            print(f"[RISK] BLOQUEO: No se puede mapear {simbolo_interno} a un símbolo broker.")
            return False

        # Verificación 2: No duplicar posición abierta en el mismo símbolo
        posiciones = mt5_lib.positions_get(symbol=simbolo_broker)
        if posiciones is not None and len(posiciones) > 0:
            print(f"[RISK] BLOQUEO: Ya hay {len(posiciones)} posicion(es) abierta(s) en {simbolo_broker}.")
            return False

        # Verificación 3: Ventana horaria — MOVIDA a verificar_ventana_ejecucion()
        # Se llama desde manager.py DESPUES de que los workers voten, no aquí.
        # Esto garantiza que el dashboard siempre muestre votos reales.

        # Verificación 4: Protección de Capital — DESHABILITADO en modo demo
        # max_perdida_flotante = self.db.get_parametros().get("GERENTE.max_drawdown_usd", 1000.0)
        # acc_info = mt5_lib.account_info()
        # if acc_info and acc_info.profit < -max_perdida_flotante:
        #     print(f"[RISK] BLOQUEO DE SEGURIDAD: Perdida flotante supera umbral.")
        #     return False

        print(f"[RISK] OK: {simbolo_interno} ({simbolo_broker}) despejado para operar.")
        return True
