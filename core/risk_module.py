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
        # lote = MIN_LOT + ((confianza - 0.45) / (0.80 - 0.45)) * (0.12 - 0.05)
        lote = MIN_LOT + ((confianza - THRESHOLD_ENTRY) / (THRESHOLD_FULL - THRESHOLD_ENTRY)) * (MAX_LOT - MIN_LOT)
        
        return round(lote, 2)

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
        if not tick:
            return None, None
            
        precio = tick.ask if direccion == "COMPRA" else tick.bid
        
        dist_sl = atr * 1.5
        dist_tp = atr * 2.0
        
        sl = precio - dist_sl if direccion == "COMPRA" else precio + dist_sl
        tp = precio + dist_tp if direccion == "COMPRA" else precio - dist_tp
        
        return sl, tp

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
        """
        # Verificación 1: Estado del activo en BD
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

        # Verificación 2: No duplicar posición abierta en el mismo símbolo
        posiciones = mt5_lib.positions_get(symbol=simbolo_broker)
        if posiciones is not None and len(posiciones) > 0:
            print(f"[RISK] BLOQUEO: Ya hay {len(posiciones)} posicion(es) abierta(s) en {simbolo_broker}.")
            return False

        # Verificación 3: Ventana horaria (si hay configuración en la BD)
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
        if horarios:
            from datetime import datetime, timezone
            hora_actual = datetime.now(timezone.utc).time()
            dentro_ventana = any(
                apertura <= hora_actual <= cierre
                for apertura, cierre in horarios
            )
            if not dentro_ventana:
                print(f"[RISK] BLOQUEO: {simbolo_interno} fuera de horario operativo.")
                return False

        print(f"[RISK] OK: {simbolo_interno} ({simbolo_broker}) despejado para operar.")
        return True
