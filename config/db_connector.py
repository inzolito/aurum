import os
import psycopg2
import collections
from collections import deque
import threading
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

def survival_shield(func):
    """Bypass global de DB para activar Modo Supervivencia (V10.6)."""
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (psycopg2.InterfaceError, psycopg2.OperationalError, Exception) as e:
            # IMPORTANTE: Revertir transaccion fallida para no envenenar la conexion
            if hasattr(self, 'conn') and self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass
                    
            if not getattr(self, "MODO_SUPERVIVENCIA", False):
                self.MODO_SUPERVIVENCIA = True
                msg = "⚠️ DB FALLIDA - Entrando en Modo Supervivencia RAM. Ejecución prioritaria activa."
                print(f"[DB-SURVIVAL] 🚨 {msg} Error: {e}")
                try:
                    from config.notifier import _enviar_telegram
                    _enviar_telegram(msg)
                except:
                    pass
                self._iniciar_reconexión()
            return self._manejar_fallo_ram(func.__name__, args, kwargs)
    return wrapper


class DBConnector:
    """
    Puente CRUD entre Python y PostgreSQL (GCP).
    Centraliza todas las consultas SQL del sistema Aurum.
    """

    def __init__(self):
        self.conn = None
        self.cursor = None
        self._lock = threading.Lock()
        
        # Cache de parámetros (V8.0)
        self._params_cache = {}
        self._params_last_refresh = 0
        self._cache_ttl = 300 # 5 minutos
        
        # --- V10.6: SURVIVAL MODE (RAM Bypass) ---
        self.MODO_SUPERVIVENCIA = False
        self.RAM_BUFFER = collections.defaultdict(lambda: deque(maxlen=200)) # {simbolo: deque}
        self.LOG_BUFFER = deque(maxlen=200)
        self._last_reconnect_attempt = 0
        self._reconnect_interval = 300 # 5 minutos (300s)
        self._reconnect_thread = None
        self._last_assets_cache = [] # V10.6

    # --- V10.6: SURVIVAL MODE (RAM Bypass) ---
    def survival_shield(func):
        """Decorador para atrapar fallos de DB y activar modo supervivencia."""
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except (psycopg2.InterfaceError, psycopg2.OperationalError, Exception) as e:
                # IMPORTANTE: Revertir transaccion fallida para no envenenar la conexion
                if hasattr(self, 'conn') and self.conn:
                    try:
                        self.conn.rollback()
                    except:
                        pass

                # Evitar circulares y spam si ya estamos en modo supervivencia
                if not getattr(self, "MODO_SUPERVIVENCIA", False):
                    self.MODO_SUPERVIVENCIA = True
                    msg = "DB FALLIDA - Entrando en Modo Supervivencia RAM. Ejecucion prioritaria activa."
                    print(f"[DB-SURVIVAL] CRITICO: {msg} Error: {e}")
                    try:
                        from config.notifier import _enviar_telegram
                        _enviar_telegram(msg)
                    except:
                        pass
                    self._iniciar_reconexión()
                
                return self._manejar_fallo_ram(func.__name__, args, kwargs)
        return wrapper

    def _iniciar_reconexión(self):
        if not hasattr(self, "_reconnect_thread") or self._reconnect_thread is None or not self._reconnect_thread.is_alive():
            self._reconnect_thread = threading.Thread(target=self._bucle_reconexion, daemon=True)
            self._reconnect_thread.start()

    def _bucle_reconexion(self):
        while self.MODO_SUPERVIVENCIA:
            time.sleep(self._reconnect_interval)
            print("[DB-SURVIVAL] Intentando reconexión...")
            if self.conectar():
                if self.test_conexion():
                    self.MODO_SUPERVIVENCIA = False
                    msg = "DB RECUPERADA - Saliendo del Modo Supervivencia."
                    print(f"[DB-SURVIVAL] {msg}")
                    from config.notifier import _enviar_telegram
                    _enviar_telegram(msg)
                    break
                else:
                    self.desconectar()

    def _manejar_fallo_ram(self, func_name, args, kwargs):
        with self._lock:
            if func_name in ['guardar_senal', 'guardar_operacion', 'guardar_error_ejecucion']:
                simbolo = args[0] if args else "GLOBAL"
                self.RAM_BUFFER[simbolo].append({"t": datetime.now(), "f": func_name, "args": args})
                print(f"[DB-SURVIVAL] Datos de {func_name} ({simbolo}) salvados en RAM.")
            elif func_name == 'registrar_log':
                self.LOG_BUFFER.append(args)

        if func_name == 'get_parametros': return self._params_cache or {}
        if func_name == 'obtener_activos_patrullaje': return self._last_assets_cache or []
        return None

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def conectar(self) -> bool:
        """Establece la conexión con PostgreSQL. Retorna True si exitosa."""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT", 5432),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                connect_timeout=10,
            )
            self.cursor = self.conn.cursor()
            print("[DB] Conexión exitosa a PostgreSQL.")
            return True
        except psycopg2.OperationalError as e:
            print(f"[DB] ERROR de conexión: {e}")
            return False

    def desconectar(self):
        """Cierra el cursor y la conexión de forma limpia."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("[DB] Conexión cerrada.")

    def test_conexion(self):
        """Verifica la conexión ejecutando SELECT version()."""
        with self._lock:
            try:
                self.cursor.execute("SELECT version();")
                version = self.cursor.fetchone()[0]
                print(f"[DB] Test OK -> {version}")
                return True
            except Exception as e:
                print(f"[DB] Test FALLIDO: {e}")
                return False

    # ------------------------------------------------------------------
    # Lectura de configuración
    # ------------------------------------------------------------------

    # Parámetros por defecto para Modo Supervivencia (V13.1)
    _DEFAULT_PARAMS = {
        "GERENTE.umbral_disparo":   0.45,
        "GERENTE.riesgo_trade_pct": 1.0,
        "GERENTE.ratio_tp":         2.0,
        "GERENTE.sl_atr_mult":      1.5,
        "GERENTE.max_drawdown_pct": 6.7,       # Max perdida flotante en % del balance
        "TENDENCIA.peso_voto":      0.40,
        "NLP.peso_voto":            0.30,
        "ORDER_FLOW.peso_voto":     0.15,
        "SNIPER.peso_voto":         0.15,
    }

    @survival_shield
    def get_parametros(self) -> dict:
        """
        Lee la tabla parametros_sistema con caché de 5 minutos (V8.0).
        V13.1: Si la DB no está disponible, retorna parámetros hardcoded.
        """
        ahora = time.time()
        if ahora - self._params_last_refresh < self._cache_ttl and self._params_cache:
            return self._params_cache

        # Guarda: Si la DB no está disponible, usar defaults
        if not self.cursor:
            return self._DEFAULT_PARAMS.copy()

        with self._lock:
            try:
                self.cursor.execute("SELECT modulo, nombre_parametro, valor FROM parametros_sistema;")
                rows = self.cursor.fetchall()
            except Exception:
                return self._params_cache or self._DEFAULT_PARAMS.copy()
            result = {}
            for modulo, nombre, valor in rows:
                if modulo and nombre.startswith(modulo + "."):
                    clave = nombre
                else:
                    clave = f"{modulo}.{nombre}" if modulo else nombre
                result[clave] = float(valor)
            
            self._params_cache = result
            self._params_last_refresh = ahora
            return result


    @survival_shield
    def obtener_activos_patrullaje(self) -> list:
        """
        Retorna lista de dicts con todos los activos en estado ACTIVO.
        V13.1: Incluye Fallback Local (Hardcoded) para modo supervivencia.
        """
        cols = ["id", "simbolo", "nombre", "categoria", "simbolo_broker"]
        # El filtrado de activos se controla exclusivamente via estado_operativo en la BD.
        # Para pausar un activo: UPDATE activos SET estado_operativo = 'PAUSADO' WHERE simbolo = 'XAUUSD';
        # Para reactivarlo:      UPDATE activos SET estado_operativo = 'ACTIVO'  WHERE simbolo = 'XAUUSD';

        with self._lock:
            try:
                if self.conn and not self.conn.closed and self.cursor:
                    self.cursor.execute(
                        """
                        SELECT id, simbolo, nombre, categoria, simbolo_broker
                        FROM activos
                        WHERE estado_operativo = 'ACTIVO'
                        ORDER BY id;
                        """
                    )
                    res = [dict(zip(cols, row)) for row in self.cursor.fetchall()]
                    self._last_assets_cache = res
                    return res
            except Exception as e:
                print(f"[DB-SURVIVAL] Error en consulta: {e}. Usando lista pre-cargada.")

        # --- FALLBACK HARDCODED (Modo Supervivencia V13.1) ---
        print("[DB-SECURITY] Utilizando lista de activos HARDCODED (Fallo de DB).")
        fallback_list = [
            {"id": 1, "simbolo": "XAUUSD", "nombre": "Oro", "categoria": "COMMODITIES", "simbolo_broker": "XAUUSD_i"},
            {"id": 2, "simbolo": "XAGUSD", "nombre": "Plata", "categoria": "COMMODITIES", "simbolo_broker": "XAGUSD_i"},
            {"id": 3, "simbolo": "US30", "nombre": "Dow Jones", "categoria": "INDICES", "simbolo_broker": "US30_i"},
            {"id": 4, "simbolo": "US500", "nombre": "S&P 500", "categoria": "INDICES", "simbolo_broker": "US500_i"},
            {"id": 5, "simbolo": "USTEC", "nombre": "Nasdaq 100", "categoria": "INDICES", "simbolo_broker": "USTEC_i"},
            {"id": 6, "simbolo": "EURUSD", "nombre": "Euro/Dolar", "categoria": "FOREX", "simbolo_broker": "EURUSD_i"},
            {"id": 7, "simbolo": "GBPUSD", "nombre": "Libra/Dolar", "categoria": "FOREX", "simbolo_broker": "GBPUSD_i"},
            {"id": 8, "simbolo": "USDJPY", "nombre": "Dolar/Yen", "categoria": "FOREX", "simbolo_broker": "USDJPY_i"},
            {"id": 9, "simbolo": "GBPJPY", "nombre": "Libra/Yen", "categoria": "FOREX", "simbolo_broker": "GBPJPY_i"},
            {"id": 10, "simbolo": "XTIUSD", "nombre": "Petroleo WTI", "categoria": "COMMODITIES", "simbolo_broker": "XTIUSD_i"},
            {"id": 11, "simbolo": "AUDUSD", "nombre": "Dolar Australiano/Dolar", "categoria": "FOREX", "simbolo_broker": "AUDUSD_i"},
            {"id": 12, "simbolo": "USDCAD", "nombre": "Dolar/Dolar Canadiense", "categoria": "FOREX", "simbolo_broker": "USDCAD_i"},
            {"id": 13, "simbolo": "GEREUR", "nombre": "DAX 40 (GER40)", "categoria": "INDICES", "simbolo_broker": "GEREUR"},
        ]
        return fallback_list

    # Alias de compatibilidad hacia atras
    def obtener_activos_encendidos(self) -> list:
        return [a["simbolo"] for a in self.obtener_activos_patrullaje()]

    def get_activos_lab_only(self) -> list:
        """
        Retorna activos asignados a labs ACTIVOS que NO están en producción
        (estado_operativo != 'ACTIVO'). Se usan para correr workers en modo
        simulación y alimentar al LabEvaluator.
        """
        with self._lock:
            try:
                self.cursor.execute("""
                    SELECT DISTINCT a.id, a.simbolo, a.nombre, a.categoria, a.simbolo_broker
                    FROM lab_activos la
                    JOIN laboratorios l ON l.id = la.lab_id
                    JOIN activos a ON a.id = la.activo_id
                    WHERE la.estado = 'ACTIVO'
                      AND l.estado  = 'ACTIVO'
                      AND a.estado_operativo != 'ACTIVO'
                    ORDER BY a.simbolo
                """)
                cols = ["id", "simbolo", "nombre", "categoria", "simbolo_broker"]
                return [dict(zip(cols, r)) for r in self.cursor.fetchall()]
            except Exception:
                self.conn.rollback()
                return []

    # Mapa de símbolo interno -> símbolo broker (fallback Survival Mode V13.1)
    # V15.3: Nomenclatura real de Weltrade — índices americanos sin sufijo _i,
    # DAX como GEREUR. Actualizar si se cambia de broker.
    _SIMBOLO_BROKER_MAP = {
        "EURUSD": "EURUSD_i", "GBPUSD": "GBPUSD_i", "USDJPY": "USDJPY_i",
        "GBPJPY": "GBPJPY_i", "USDCAD": "USDCAD_i",
        "US30":  "DJIUSD",  "US500": "SPXUSD",  "USTEC": "NDXUSD",
        "GER40": "GEREUR",
        "XTIUSD": "XTIUSD_i", "XAUUSD": "XAUUSD_i",
        "XAGUSD": "XAGUSD_i", "XBRUSD": "XBRUSD_i",
    }

    def obtener_impactos_por_activo(self, id_activo: int) -> list:
        """
        Retorna los impactos de regimenes ACTIVO/FORMANDOSE para un activo especifico.
        V13.1: Retorna lista vacía si la DB no está disponible.
        """
        if not self.cursor:
            return []
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    SELECT rm.titulo, rm.clasificacion, rm.estado, ir.valor_impacto
                    FROM impactos_regimen ir
                    JOIN regimenes_mercado rm ON rm.id = ir.id_regimen
                    WHERE ir.id_activo = %s
                      AND rm.estado IN ('ACTIVO', 'FORMANDOSE')
                    ORDER BY rm.fecha_inicio DESC;
                    """,
                    (id_activo,)
                )
                cols = ["titulo", "clasificacion", "estado", "valor_impacto"]
                return [dict(zip(cols, row)) for row in self.cursor.fetchall()]
            except Exception:
                return []

    # Mantenemos get_regimenes_activos como alias para backward-compat
    def get_regimenes_activos(self) -> list:
        """Deprecated: usar obtener_impactos_por_activo(id_activo). Retorna lista vacia."""
        return []

    def obtener_simbolo_broker(self, simbolo_interno: str) -> str | None:
        """
        Traduce el símbolo estándar interno (ej: 'XAUUSD') al nombre del broker.
        V13.1: Si la DB no está disponible, usa mapa hardcoded.
        """
        if not self.cursor:
            return self._SIMBOLO_BROKER_MAP.get(simbolo_interno, f"{simbolo_interno}_i")
        with self._lock:
            try:
                self.cursor.execute(
                    "SELECT simbolo_broker FROM activos WHERE simbolo = %s;",
                    (simbolo_interno,)
                )
                fila = self.cursor.fetchone()
                if not fila or not fila[0]:
                    return self._SIMBOLO_BROKER_MAP.get(simbolo_interno)
                return fila[0]
            except Exception:
                return self._SIMBOLO_BROKER_MAP.get(simbolo_interno, f"{simbolo_interno}_i")

    @survival_shield
    def get_global_regimenes(self) -> list:
        """Atomic fetch of global market regimes."""
        with self._lock:
            self.cursor.execute(
                """
                SELECT titulo, clasificacion, estado
                FROM regimenes_mercado
                WHERE estado IN ('ACTIVO', 'FORMANDOSE')
                ORDER BY id;
                """
            )
            cols = ["titulo", "clasificacion", "estado"]
            return [dict(zip(cols, row)) for row in self.cursor.fetchall()]


    # ------------------------------------------------------------------
    # Escritura de auditoría
    # ------------------------------------------------------------------

    @survival_shield
    def guardar_senal(self, simbolo: str, v_trend: float, v_nlp: float,
                      v_flow: float, veredicto: float, decision: str, motivo: str,
                      v_vol: float = 0.0, v_cross: float = 0.0,
                      v_hurst: float = 0.5, v_sniper: float = 0.0,
                      v_macro: float = 0.0):
        """Inserta una fila en registro_senales con bloqueo de hilo (V10.0 Enhanced)."""
        with self._lock:
            self.cursor.execute(
                """
                INSERT INTO registro_senales
                    (activo_id, voto_tendencia, voto_nlp, voto_order_flow,
                     voto_final_ponderado, decision_gerente, motivo,
                     voto_volume, voto_cross, voto_hurst, voto_sniper, voto_macro)
                SELECT id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                FROM activos WHERE simbolo = %s;
                """,
                (v_trend, v_nlp, v_flow, veredicto, decision, motivo,
                 v_vol, v_cross, v_hurst, v_sniper, v_macro, simbolo),
            )
            self.conn.commit()

    @survival_shield
    def guardar_operacion(self, datos: dict):
        """
        Inserta el registro completo del trade en registro_operaciones.
        """
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO registro_operaciones
                        (activo_id, ticket_mt5, tipo_orden, volumen_lotes,
                         precio_entrada, stop_loss, take_profit,
                         justificacion_entrada, veredicto_apertura, probabilidad_est,
                         version_id)
                    SELECT a.id, %(ticket_mt5)s, %(tipo_orden)s, %(volumen_lotes)s,
                           %(precio_entrada)s, %(stop_loss)s, %(take_profit)s,
                           %(justificacion_entrada)s, %(veredicto_apertura)s, %(probabilidad_est)s,
                           (SELECT id FROM versiones_sistema WHERE estado = 'ACTIVA' ORDER BY id DESC LIMIT 1)
                    FROM activos a WHERE a.simbolo = %(simbolo)s;
                    """,
                    datos,
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error guardando operacion: {e}")
                self.conn.rollback()

    @survival_shield
    def guardar_autopsia(self, ticket: int, simbolo: str, pnl: float,
                         tipo_fallo: str, worker_culpable: str,
                         descripcion: str, correccion: str):
        """D3 V14: Persiste el análisis de autopsia de una pérdida en autopsias_perdidas."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO autopsias_perdidas
                        (ticket_mt5, simbolo, pnl_usd, tipo_fallo, worker_culpable, descripcion, correccion_sugerida)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (ticket, simbolo, pnl, tipo_fallo, worker_culpable, descripcion, correccion)
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error guardando autopsia #{ticket}: {e}")
                self.conn.rollback()

    @survival_shield
    def guardar_error_ejecucion(self, simbolo: str, retcode: int, mensaje: str,
                                decision: str, lotes: float, contexto: str):
        """
        Inserta un fallo de MT5 en la tabla errores_ejecucion.
        """
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO errores_ejecucion (simbolo, retcode, mensaje_error, decision_intentada, lotes, contexto_bot)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (simbolo, retcode, mensaje, decision, lotes, contexto),
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error guardando error ejecucion: {e}")
                self.conn.rollback()

    # ------------------------------------------------------------------
    # Estado en vivo (Heartbeat)
    # ------------------------------------------------------------------

    @survival_shield
    def update_estado_bot(self, estado: str, pensamiento: str, balance: float = None, equity: float = None, pnl_flotante: float = None):
        """Upsert en estado_bot con bloqueo de hilo (V8.0)."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO estado_bot (id, estado_general, pensamiento_actual, tiempo, balance, equity, pnl_flotante)
                    VALUES (1, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                        SET estado_general    = EXCLUDED.estado_general,
                            pensamiento_actual = EXCLUDED.pensamiento_actual,
                            tiempo            = CURRENT_TIMESTAMP,
                            balance           = COALESCE(EXCLUDED.balance, estado_bot.balance),
                            equity            = COALESCE(EXCLUDED.equity, estado_bot.equity),
                            pnl_flotante      = COALESCE(EXCLUDED.pnl_flotante, estado_bot.pnl_flotante);
                    """,
                    (estado, pensamiento, balance, equity, pnl_flotante),
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error actualizando estado bot: {e}")
                self.conn.rollback()

    @survival_shield
    def registrar_log(self, nivel: str, modulo: str, mensaje: str):
        """
        Inserta un evento en log_sistema con bloqueo de hilo.
        """
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO log_sistema (nivel, modulo, mensaje)
                    VALUES (%s, %s, %s);
                    """,
                    (nivel, modulo, mensaje),
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error registrando log: {e}")
                self.conn.rollback()

    # ------------------------------------------------------------------
    # Métodos Atómicos NLP (V8.1)
    # ------------------------------------------------------------------

    @survival_shield
    def get_nlp_reasoning(self, simbolo: str) -> str | None:
        """Atomic fetch of reasoning from cache Table."""
        with self._lock:
            try:
                self.cursor.execute(
                    "SELECT razonamiento FROM cache_nlp_impactos WHERE simbolo = %s ORDER BY creado_en DESC LIMIT 1;",
                    (simbolo,)
                )
                fila = self.cursor.fetchone()
                return fila[0] if fila else None
            except Exception as e:
                print(f"[DB] Error fetching nlp reasoning for {simbolo}: {e}")
                return None

    def upsert_nlp_cache(self, datos: list):
        """Atomic batch UPSERT into cache_nlp_impactos.
        FIX-NLP-02: Usa ON CONFLICT DO UPDATE para evitar acumulación de filas stale.
        """
        with self._lock:
            try:
                self.cursor.executemany(
                    """
                    INSERT INTO cache_nlp_impactos (simbolo, voto, razonamiento, hash_contexto, hash_regimenes)
                    VALUES (%s, %s, %s, %s, 'v9_migrado')
                    ON CONFLICT (simbolo) DO UPDATE
                        SET voto        = EXCLUDED.voto,
                            razonamiento = EXCLUDED.razonamiento,
                            hash_contexto = EXCLUDED.hash_contexto,
                            creado_en   = CURRENT_TIMESTAMP;
                    """,
                    datos
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error upserting nlp cache: {e}")
                self.conn.rollback()
                # Fallback: si no existe constraint UNIQUE en simbolo, insertar simple
                try:
                    self.cursor.executemany(
                        """
                        INSERT INTO cache_nlp_impactos (simbolo, voto, razonamiento, hash_contexto, hash_regimenes)
                        VALUES (%s, %s, %s, %s, 'v9_migrado');
                        """,
                        datos
                    )
                    self.conn.commit()
                    print("[DB] NLP cache guardado en modo fallback (INSERT simple).")
                except Exception as e2:
                    print(f"[DB] Error fallback nlp cache: {e2}")
                    self.conn.rollback()

    @survival_shield
    def leer_cache_nlp(self, hash_ctx: str, id_activo: int) -> float | None:
        """Atomic check of nlp cache.
        FIX-NLP-02: Filtra por TTL (5 min) para no devolver datos stale.
        Busca por simbolo (más fiable que por hash cuando hay multiples filas).
        """
        with self._lock:
            try:
                ttl_min = int(os.getenv("NLP_CACHE_TTL_MIN", "5"))
                self.cursor.execute(
                    """
                    SELECT c.voto 
                    FROM cache_nlp_impactos c
                    JOIN activos a ON a.simbolo = c.simbolo
                    WHERE a.id = %s
                      AND c.creado_en >= NOW() - INTERVAL '%s minutes'
                    ORDER BY c.creado_en DESC
                    LIMIT 1;
                    """,
                    (id_activo, ttl_min)
                )
                fila = self.cursor.fetchone()
                return float(fila[0]) if fila else None
            except Exception as e:
                print(f"[DB] Error reading nlp cache: {e}")
                return None

    @survival_shield
    def guardar_sentimiento_noticia(self, simbolo: str, impacto: float, razonamiento: str):
        """Guarda el análisis de una noticia en la tabla sentimiento_noticias."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO sentimiento_noticias (activo_id, titular, impacto_nlp, fuente, razonamiento_ia)
                    SELECT id, %s, %s, %s, %s
                    FROM activos WHERE simbolo = %s;
                    """,
                    ("Analisis Gemini", impacto, "Gemini AI", razonamiento, simbolo)
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error guardando sentimiento noticia: {e}")
                self.conn.rollback()

    @survival_shield
    def guardar_noticia_cruda(self, source: str, title: str, summary: str, hash_id: str, published_at=None):
        """Guarda una noticia en raw_news_feed (V13.0)."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO raw_news_feed (source, title, content_summary, hash_id, published_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (hash_id) DO UPDATE 
                    SET published_at = EXCLUDED.published_at;
                    """,
                    (source, title, summary, hash_id, published_at)
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error guardando noticia cruda: {e}")
                self.conn.rollback()

    @survival_shield
    def get_top_news(self, limit: int = 10) -> list:
        """Retorna las últimas noticias crudas con su fecha original (V13.0)."""
        with self._lock:
            query = "SELECT title, source, timestamp, hash_id FROM raw_news_feed ORDER BY timestamp DESC LIMIT %s"
            self.cursor.execute(query, (limit,))
            return [dict(zip(["title", "source", "fecha", "hash_id"], row)) for row in self.cursor.fetchall()]

    @survival_shield
    def verificar_hash_noticia(self, hash_id: str) -> bool:
        """Retorna True si el hash ya existe."""
        with self._lock:
            self.cursor.execute("SELECT 1 FROM raw_news_feed WHERE hash_id = %s LIMIT 1", (hash_id,))
            return self.cursor.fetchone() is not None

    @survival_shield
    def get_catalizadores_activos(self) -> list:
        """Retorna lista de catalizadores de largo plazo (V11.2)."""
        with self._lock:
            self.cursor.execute(
                "SELECT event_name, ai_sentiment_score FROM market_catalysts WHERE is_active = TRUE"
            )
            return [dict(zip(["name", "score"], row)) for row in self.cursor.fetchall()]

    @survival_shield
    def upsert_catalizador(self, name: str, score: float):
        """Crea o actualiza un catalizador (V11.2)."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO market_catalysts (event_name, ai_sentiment_score, is_active, last_update)
                    VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (event_name) DO UPDATE
                    SET ai_sentiment_score = EXCLUDED.ai_sentiment_score,
                        last_update = CURRENT_TIMESTAMP;
                    """,
                    (name, score)
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error upsert catalizador: {e}")
                self.conn.rollback()

    # --- V11.1: TELEGRAM INTERACTIVE READS ---
    @survival_shield
    def get_tablero_global(self) -> list:
        """Retorna el último veredicto de cada activo para el Tablero Global."""
        with self._lock:
            # Subconsulta para obtener la última señal por activo
            query = """
                SELECT a.simbolo, rs.voto_tendencia, rs.voto_nlp, rs.voto_order_flow,
                       rs.voto_final_ponderado, rs.motivo, rs.tiempo
                FROM activos a
                LEFT JOIN (
                    SELECT DISTINCT ON (activo_id) *
                    FROM registro_senales
                    ORDER BY activo_id, tiempo DESC
                ) rs ON a.id = rs.activo_id
                WHERE a.estado_operativo = 'ACTIVO'
                ORDER BY a.id;
            """
            self.cursor.execute(query)
            cols = ["simbolo", "trend", "nlp", "flow", "veredicto", "motivo", "fecha"]
            return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    @survival_shield
    def get_detalle_activo(self, simbolo: str) -> dict | None:
        """Retorna detalles profundos de un activo desde la DB."""
        with self._lock:
            # 1. Datos de señal
            query_senal = """
                SELECT rs.voto_final_ponderado, rs.motivo, rs.tiempo
                FROM registro_senales rs
                JOIN activos a ON a.id = rs.activo_id
                WHERE a.simbolo = %s
                ORDER BY rs.tiempo DESC LIMIT 1;
            """
            self.cursor.execute(query_senal, (simbolo,))
            col_s = ["veredicto", "motivo", "fecha"]
            senal = dict(zip(col_s, self.cursor.fetchone())) if self.cursor.rowcount > 0 else {}

            # 2. Último comentario IA
            query_log = """
                SELECT mensaje, tiempo FROM log_sistema
                WHERE modulo = 'MANAGER' AND nivel = 'INFO' AND mensaje LIKE '%%' || %s || '%%'
                ORDER BY tiempo DESC LIMIT 1;
            """
            self.cursor.execute(query_log, (simbolo,))
            log = self.cursor.fetchone()
            comentario_ia = log[0] if log else "No hay comentarios recientes."

            if not senal: return None
            
            return {**senal, "comentario_ia": comentario_ia}

    @survival_shield
    def get_radar_noticias(self) -> list:
        """Retorna las últimas 5 noticias procesadas por la IA."""
        with self._lock:
            query = "SELECT simbolo, razonamiento, creado_en FROM cache_nlp_impactos ORDER BY creado_en DESC LIMIT 10;"
            self.cursor.execute(query)
            cols = ["simbolo", "razonamiento", "fecha"]
            return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    @survival_shield
    def get_dashboard_data(self) -> list:
        """Retorna el estado detallado de todos los activos para el dashboard."""
        with self._lock:
            query = """
                SELECT a.simbolo, rs.voto_tendencia, c.voto as voto_nlp, rs.voto_order_flow,
                       rs.voto_volume, rs.voto_cross, rs.voto_hurst, rs.voto_sniper,
                       rs.voto_final_ponderado, c.razonamiento, rs.tiempo
                FROM activos a
                LEFT JOIN (
                    SELECT DISTINCT ON (activo_id) *
                    FROM registro_senales
                    ORDER BY activo_id, tiempo DESC
                ) rs ON a.id = rs.activo_id
                LEFT JOIN (
                    SELECT DISTINCT ON (simbolo) *
                    FROM cache_nlp_impactos
                    ORDER BY simbolo, creado_en DESC
                ) c ON a.simbolo = c.simbolo
                WHERE a.estado_operativo = 'ACTIVO'
                ORDER BY a.id;
            """
            self.cursor.execute(query)
            cols = ["simbolo", "trend", "nlp", "flow", "vol", "cross", "hurst", "sniper", "verdict", "ia_analysis", "fecha"]
            return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    # ------------------------------------------------------------------
    # Métodos del Laboratorio (V18)
    # ------------------------------------------------------------------

    def get_lab_params(self, lab_id: int) -> dict:
        """
        Lee lab_parametros para un lab, con fallback a get_parametros() si no existe.
        Retorna dict fusionado: producción + overrides del lab.
        """
        base = self.get_parametros().copy()
        if not self.cursor:
            return base
        with self._lock:
            try:
                self.cursor.execute(
                    "SELECT nombre_parametro, valor FROM lab_parametros WHERE lab_id = %s",
                    (lab_id,)
                )
                for nombre, valor in self.cursor.fetchall():
                    try:
                        base[nombre] = float(valor)
                    except (ValueError, TypeError):
                        base[nombre] = valor
            except Exception as e:
                print(f"[DB-LAB] Error leyendo lab_parametros para lab {lab_id}: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
        return base

    def bump_lab_version(self, lab_id: int, bump: str, notas: str, nuevos_params: dict) -> str:
        """
        Guarda snapshot de params+métricas actuales en lab_versiones,
        actualiza lab_parametros con nuevos_params y sube la versión.
        bump: 'patch' | 'minor' | 'major'
        Retorna la nueva versión como string.
        """
        import json as _json
        with self._lock:
            try:
                # 1. Versión actual
                self.cursor.execute("SELECT version FROM laboratorios WHERE id = %s", (lab_id,))
                row = self.cursor.fetchone()
                version_actual = (row[0] if row else "1.0.0") or "1.0.0"
                parts = version_actual.split(".")
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

                if bump == "major":
                    major += 1; minor = 0; patch = 0
                elif bump == "minor":
                    minor += 1; patch = 0
                else:
                    patch += 1
                nueva_version = f"{major}.{minor}.{patch}"

                # 2. Snapshot de parámetros actuales
                self.cursor.execute(
                    "SELECT nombre_parametro, valor FROM lab_parametros WHERE lab_id = %s",
                    (lab_id,)
                )
                params_actuales = {r[0]: r[1] for r in self.cursor.fetchall()}

                # 3. Snapshot de métricas actuales
                self.cursor.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE estado='CERRADA') as trades,
                        COUNT(*) FILTER (WHERE estado='CERRADA' AND resultado='TP') as ganados,
                        COALESCE(SUM(pnl_virtual) FILTER (WHERE estado='CERRADA'), 0) as pnl,
                        l.balance_virtual, l.capital_virtual
                    FROM lab_operaciones lo
                    JOIN laboratorios l ON l.id = lo.lab_id
                    WHERE lo.lab_id = %s
                    GROUP BY l.balance_virtual, l.capital_virtual
                """, (lab_id,))
                mr = self.cursor.fetchone()
                metricas_snap = None
                if mr:
                    trades = int(mr[0] or 0)
                    ganados = int(mr[1] or 0)
                    pnl = float(mr[2] or 0)
                    balance = float(mr[3] or 0)
                    capital = float(mr[4] or 1)
                    metricas_snap = {
                        "trades": trades,
                        "ganados": ganados,
                        "perdidos": trades - ganados,
                        "win_rate": round(ganados / trades * 100, 1) if trades > 0 else 0,
                        "pnl_total": round(pnl, 2),
                        "roe_pct": round((balance - capital) / capital * 100, 2) if capital > 0 else 0,
                    }

                # 4. Guardar snapshot en lab_versiones
                self.cursor.execute("""
                    INSERT INTO lab_versiones (lab_id, version, parametros, metricas, notas)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    lab_id, nueva_version,
                    _json.dumps(params_actuales),
                    _json.dumps(metricas_snap) if metricas_snap else None,
                    notas,
                ))

                # 5. Actualizar lab_parametros con nuevos valores
                for nombre, valor in nuevos_params.items():
                    self.cursor.execute("""
                        INSERT INTO lab_parametros (lab_id, nombre_parametro, valor)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (lab_id, nombre_parametro) DO UPDATE SET valor = EXCLUDED.valor
                    """, (lab_id, nombre, str(valor)))

                # 6. Actualizar versión en laboratorios
                self.cursor.execute(
                    "UPDATE laboratorios SET version = %s WHERE id = %s",
                    (nueva_version, lab_id)
                )
                self.conn.commit()
                return nueva_version
            except Exception as e:
                self.conn.rollback()
                raise e

    def get_lab_versiones(self, lab_id: int) -> list:
        """Retorna historial de versiones de un lab, más reciente primero."""
        with self._lock:
            try:
                self.cursor.execute("""
                    SELECT version, parametros, metricas, notas, creado_en
                    FROM lab_versiones
                    WHERE lab_id = %s
                    ORDER BY creado_en DESC
                """, (lab_id,))
                cols = ["version", "parametros", "metricas", "notas", "creado_en"]
                rows = []
                for r in self.cursor.fetchall():
                    row = dict(zip(cols, r))
                    row["creado_en"] = row["creado_en"].isoformat() if row["creado_en"] else None
                    rows.append(row)
                return rows
            except Exception:
                self.conn.rollback()
                return []

    def get_labs_activos(self) -> list:
        """
        Retorna lista de labs con estado=ACTIVO con sus activos asignados.
        Cada item: {id, nombre, categoria, estado, capital_virtual, balance_virtual, activos: [list]}
        """
        if not self.cursor:
            return []
        with self._lock:
            try:
                self.cursor.execute("""
                    SELECT l.id, l.nombre, l.categoria, l.estado,
                           l.capital_virtual, l.balance_virtual
                    FROM laboratorios l
                    WHERE l.estado = 'ACTIVO'
                    ORDER BY l.id
                """)
                cols = ["id", "nombre", "categoria", "estado", "capital_virtual", "balance_virtual"]
                labs = [dict(zip(cols, row)) for row in self.cursor.fetchall()]

                for lab in labs:
                    self.cursor.execute("""
                        SELECT la.activo_id, a.simbolo
                        FROM lab_activos la
                        JOIN activos a ON a.id = la.activo_id
                        WHERE la.lab_id = %s AND la.estado = 'ACTIVO'
                    """, (lab["id"],))
                    lab["activos"] = [
                        {"id": r[0], "simbolo": r[1]}
                        for r in self.cursor.fetchall()
                    ]
                return labs
            except Exception as e:
                print(f"[DB-LAB] Error en get_labs_activos: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return []

    def get_activos_para_evaluar(self) -> list:
        """
        UNION de activos de producción + activos de labs activos.
        Retorna lista de dicts con {id, simbolo, nombre, categoria, simbolo_broker}.
        Cada activo aparece UNA sola vez (DISTINCT).
        """
        if not self.cursor:
            return self.obtener_activos_patrullaje()
        cols = ["id", "simbolo", "nombre", "categoria", "simbolo_broker"]
        with self._lock:
            try:
                self.cursor.execute("""
                    SELECT DISTINCT a.id, a.simbolo, a.nombre, a.categoria, a.simbolo_broker
                    FROM activos a
                    WHERE a.id IN (
                        SELECT id FROM activos WHERE estado_operativo = 'ACTIVO'
                        UNION
                        SELECT la.activo_id FROM lab_activos la
                        JOIN laboratorios l ON l.id = la.lab_id
                        WHERE la.estado = 'ACTIVO' AND l.estado = 'ACTIVO'
                    )
                    ORDER BY a.id
                """)
                res = [dict(zip(cols, row)) for row in self.cursor.fetchall()]
                if res:
                    self._last_assets_cache = res
                return res
            except Exception as e:
                print(f"[DB-LAB] Error en get_activos_para_evaluar: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return self.obtener_activos_patrullaje()

    def guardar_lab_senal(self, lab_id: int, activo_id: int, votos: dict,
                          decision: str, motivo: str, umbral: float, pesos: dict) -> int | None:
        """
        Inserta una señal de lab en lab_senales.
        Retorna el id insertado (para referencia en lab_operaciones).
        """
        if not self.cursor:
            return None
        import json as _json
        with self._lock:
            try:
                self.cursor.execute("""
                    INSERT INTO lab_senales
                        (lab_id, activo_id, voto_tendencia, voto_nlp, voto_sniper,
                         voto_hurst, voto_volume, voto_cross, voto_macro,
                         voto_final_ponderado,
                         decision_gerente, motivo, umbral_usado, pesos_usados)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    lab_id, activo_id,
                    votos.get("trend", 0.0), votos.get("nlp", 0.0),
                    votos.get("sniper", 0.0), votos.get("hurst", 0.5),
                    votos.get("volume", 0.0), votos.get("cross", 0.0),
                    votos.get("macro", 0.0),
                    votos.get("veredicto", 0.0),
                    decision, motivo, umbral,
                    _json.dumps(pesos)
                ))
                row = self.cursor.fetchone()
                self.conn.commit()
                return row[0] if row else None
            except Exception as e:
                print(f"[DB-LAB] Error guardando lab_senal (lab={lab_id}): {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return None

    def guardar_lab_operacion(self, lab_id: int, activo_id: int, senal_id: int,
                               tipo: str, precio: float, sl: float, tp: float,
                               lotes: float, capital: float, justificacion: str) -> int | None:
        """Inserta una operación virtual en lab_operaciones. Retorna id."""
        if not self.cursor:
            return None
        with self._lock:
            try:
                self.cursor.execute("""
                    INSERT INTO lab_operaciones
                        (lab_id, activo_id, lab_senal_id, tipo_orden,
                         precio_entrada, stop_loss, take_profit,
                         volumen_lotes, capital_usado, justificacion_entrada,
                         version_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            (SELECT id FROM versiones_sistema WHERE estado = 'ACTIVA' ORDER BY id DESC LIMIT 1))
                    RETURNING id
                """, (
                    lab_id, activo_id, senal_id, tipo,
                    precio, sl, tp, lotes, capital, justificacion
                ))
                row = self.cursor.fetchone()
                self.conn.commit()
                return row[0] if row else None
            except Exception as e:
                print(f"[DB-LAB] Error guardando lab_operacion (lab={lab_id}): {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return None

    def actualizar_pnl_flotante_lab(self, op_id: int, pnl: float, roe: float):
        """Actualiza pnl_virtual y roe_pct de una operación ABIERTA con P&L flotante."""
        if not self.cursor:
            return
        with self._lock:
            try:
                self.cursor.execute("""
                    UPDATE lab_operaciones
                    SET pnl_virtual = %s, roe_pct = %s
                    WHERE id = %s AND estado = 'ABIERTA'
                """, (pnl, roe, op_id))
                self.conn.commit()
            except Exception as e:
                print(f"[DB-LAB] Error actualizando pnl flotante op {op_id}: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass

    def cerrar_lab_operacion(self, op_id: int, precio_salida: float,
                              resultado: str, pnl: float, roe: float):
        """Cierra una operación virtual (TP/SL/MANUAL) y actualiza balance del lab."""
        if not self.cursor:
            return
        with self._lock:
            try:
                self.cursor.execute("""
                    UPDATE lab_operaciones
                    SET estado = 'CERRADA', tiempo_salida = NOW(),
                        precio_salida = %s, resultado = %s,
                        pnl_virtual = %s, roe_pct = %s
                    WHERE id = %s
                """, (precio_salida, resultado, pnl, roe, op_id))
                # Actualizar balance_virtual del lab
                self.cursor.execute("""
                    UPDATE laboratorios
                    SET balance_virtual = balance_virtual + %s
                    WHERE id = (
                        SELECT lab_id FROM lab_operaciones WHERE id = %s
                    )
                """, (pnl, op_id))
                self.conn.commit()
            except Exception as e:
                print(f"[DB-LAB] Error cerrando lab_operacion {op_id}: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass

    def get_lab_operaciones_abiertas(self, lab_id: int) -> list:
        """Retorna todas las operaciones virtuales abiertas de un lab."""
        if not self.cursor:
            return []
        with self._lock:
            try:
                self.cursor.execute("""
                    SELECT lo.id, lo.activo_id, a.simbolo, lo.tipo_orden,
                           lo.precio_entrada, lo.stop_loss, lo.take_profit,
                           lo.volumen_lotes, lo.capital_usado, lo.tiempo_entrada
                    FROM lab_operaciones lo
                    JOIN activos a ON a.id = lo.activo_id
                    WHERE lo.lab_id = %s AND lo.estado = 'ABIERTA'
                    ORDER BY lo.tiempo_entrada DESC
                """, (lab_id,))
                cols = ["id", "activo_id", "simbolo", "tipo_orden",
                        "precio_entrada", "stop_loss", "take_profit",
                        "volumen_lotes", "capital_usado", "tiempo_entrada"]
                return [dict(zip(cols, row)) for row in self.cursor.fetchall()]
            except Exception as e:
                print(f"[DB-LAB] Error en get_lab_operaciones_abiertas (lab={lab_id}): {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return []

    def get_regimenes_macro_activos(self) -> list:
        """Retorna regímenes macro activos para inyectar en NLP."""
        if not self.cursor:
            return []
        with self._lock:
            try:
                self.cursor.execute("""
                    SELECT id, tipo, nombre, fase, direccion, peso,
                           activos_afectados, razonamiento, expira_en
                    FROM regimenes_macro
                    WHERE activo = TRUE
                    ORDER BY peso DESC, creado_en DESC
                """)
                cols = ["id", "tipo", "nombre", "fase", "direccion", "peso",
                        "activos_afectados", "razonamiento", "expira_en"]
                return [dict(zip(cols, row)) for row in self.cursor.fetchall()]
            except Exception as e:
                print(f"[DB-LAB] Error en get_regimenes_macro_activos: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return []

    def guardar_regimen_macro(self, tipo: str, nombre: str, fase: str, direccion: str,
                              peso: float, activos_afectados: str, razonamiento: str,
                              expira_en=None, fuente_noticia: str = None) -> int | None:
        """INSERT en regimenes_macro. Retorna el id del nuevo registro o None si falla."""
        if not self.cursor:
            return None
        with self._lock:
            try:
                self.cursor.execute("""
                    INSERT INTO regimenes_macro
                        (tipo, nombre, fase, direccion, peso, activos_afectados,
                         razonamiento, expira_en, fuente_noticia, creado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'AUTO')
                    RETURNING id
                """, (tipo, nombre, fase, direccion, peso, activos_afectados,
                      razonamiento, expira_en, fuente_noticia))
                new_id = self.cursor.fetchone()[0]
                self.conn.commit()
                print(f"[DB-LAB] guardar_regimen_macro: nuevo régimen #{new_id} '{nombre}'.")
                return new_id
            except Exception as e:
                print(f"[DB-LAB] Error en guardar_regimen_macro: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return None

    def actualizar_regimen_macro(self, regimen_id: int, fase: str = None,
                                 peso: float = None, razonamiento: str = None,
                                 activo: bool = None):
        """UPDATE parcial de un régimen macro existente."""
        if not self.cursor:
            return
        campos = []
        valores = []
        if fase is not None:
            campos.append("fase = %s")
            valores.append(fase)
        if peso is not None:
            campos.append("peso = %s")
            valores.append(peso)
        if razonamiento is not None:
            campos.append("razonamiento = %s")
            valores.append(razonamiento)
        if activo is not None:
            campos.append("activo = %s")
            valores.append(activo)
        if not campos:
            return
        valores.append(regimen_id)
        with self._lock:
            try:
                self.cursor.execute(
                    f"UPDATE regimenes_macro SET {', '.join(campos)} WHERE id = %s",
                    valores
                )
                self.conn.commit()
                print(f"[DB-LAB] actualizar_regimen_macro: #{regimen_id} actualizado.")
            except Exception as e:
                print(f"[DB-LAB] Error en actualizar_regimen_macro: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass

    def cleanup_lab_senales(self):
        """DELETE lab_senales WHERE tiempo < NOW() - 30 días (job nocturno)."""
        if not self.cursor:
            return
        with self._lock:
            try:
                self.cursor.execute(
                    "DELETE FROM lab_senales WHERE tiempo < NOW() - INTERVAL '30 days'"
                )
                deleted = self.cursor.rowcount
                self.conn.commit()
                if deleted:
                    print(f"[DB-LAB] cleanup_lab_senales: {deleted} filas eliminadas.")
            except Exception as e:
                print(f"[DB-LAB] Error en cleanup_lab_senales: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass

    def expirar_regimenes_macro(self):
        """UPDATE activo=FALSE WHERE expira_en < NOW() (job nocturno)."""
        if not self.cursor:
            return
        with self._lock:
            try:
                self.cursor.execute("""
                    UPDATE regimenes_macro
                    SET activo = FALSE
                    WHERE activo = TRUE AND expira_en IS NOT NULL AND expira_en < NOW()
                """)
                updated = self.cursor.rowcount
                self.conn.commit()
                if updated:
                    print(f"[DB-LAB] expirar_regimenes_macro: {updated} regímenes expirados.")
            except Exception as e:
                print(f"[DB-LAB] Error en expirar_regimenes_macro: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass


# ------------------------------------------------------------------
# Test de Conexión (ejecutar directamente: python config/db_connector.py)
# ------------------------------------------------------------------
if __name__ == "__main__":
    db = DBConnector()
    if db.conectar():
        db.test_conexion()
        db.desconectar()
