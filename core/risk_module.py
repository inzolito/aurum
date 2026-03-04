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

    def calcular_lotes(self, simbolo_interno: str, sl_precio: float) -> float | None:
        """
        Calcula el volumen (lotes) exacto para que una pérdida en el SL
        equivalga al % de riesgo configurado en parametros_sistema.

        simbolo_interno : Nombre estándar (ej: 'XAUUSD')
        sl_precio       : Precio del Stop Loss
        Retorna: volumen en lotes (redondeado al step permitido), o None si falla.
        """
        # 1. Obtener símbolo real del broker desde la BD
        self.db.cursor.execute(
            "SELECT simbolo_broker FROM activos WHERE simbolo = %s;",
            (simbolo_interno,)
        )
        fila = self.db.cursor.fetchone()
        if not fila or not fila[0]:
            print(f"[RISK] ERROR: No hay simbolo_broker para '{simbolo_interno}'")
            return None
        simbolo_broker = fila[0]

        # 2. Obtener balance de la cuenta DEMO vía MT5
        info_cuenta = mt5_lib.account_info()
        if info_cuenta is None:
            print("[RISK] ERROR: No se pudo obtener info de la cuenta MT5.")
            return None
        balance = info_cuenta.balance

        # 3. Obtener % de riesgo desde parametros_sistema
        params = self.db.get_parametros()
        pct_riesgo = params.get("GERENTE.riesgo_trade_pct", 1.5)

        # 4. Obtener precio actual y calcular distancia al SL
        tick = mt5_lib.symbol_info_tick(simbolo_broker)
        if tick is None:
            print(f"[RISK] ERROR: No se pudo obtener precio de {simbolo_broker}")
            return None
        precio_actual = tick.ask  # Asumimos entrada en compra (Ask)
        distancia_sl  = abs(precio_actual - sl_precio)

        if distancia_sl == 0:
            print("[RISK] ERROR: Distancia al SL es cero. Stop Loss inválido.")
            return None

        # 5. Obtener info del símbolo (valor del tick)
        info_simbolo = mt5_lib.symbol_info(simbolo_broker)
        if info_simbolo is None:
            print(f"[RISK] ERROR: No se pudo obtener info del símbolo {simbolo_broker}")
            return None

        # Valor monetario de 1 punto de movimiento por 1 lote
        valor_tick = info_simbolo.trade_tick_value
        tick_size  = info_simbolo.trade_tick_size

        # Valor de 1 punto por 1 lote (ajustado al tamaño del tick)
        valor_por_punto = valor_tick / tick_size if tick_size > 0 else valor_tick

        # 6. Fórmula de lotaje
        dinero_a_arriesgar = balance * (pct_riesgo / 100)
        lotes_raw = dinero_a_arriesgar / (distancia_sl * valor_por_punto)

        # 7. Redondear al step del broker y validar límites
        vol_min  = info_simbolo.volume_min
        vol_max  = info_simbolo.volume_max
        vol_step = info_simbolo.volume_step

        lotes = round(lotes_raw / vol_step) * vol_step
        lotes = max(vol_min, min(vol_max, lotes))
        lotes = round(lotes, 2)

        print(f"[RISK] Balance: ${balance:,.2f} | Riesgo: {pct_riesgo}% = ${dinero_a_arriesgar:,.2f}")
        print(f"[RISK] Precio actual: {precio_actual} | SL: {sl_precio} | Distancia: {distancia_sl:.2f} pts")
        print(f"[RISK] Valor/punto: ${valor_por_punto:.4f} | Lotes calculados: {lotes}")

        return lotes

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
