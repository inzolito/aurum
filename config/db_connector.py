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

    @survival_shield
    def get_parametros(self) -> dict:
        """
        Lee la tabla parametros_sistema con caché de 5 minutos (V8.0).
        """
        ahora = time.time()
        if ahora - self._params_last_refresh < self._cache_ttl and self._params_cache:
            return self._params_cache

        with self._lock:
            self.cursor.execute("SELECT modulo, nombre_parametro, valor FROM parametros_sistema;")
            rows = self.cursor.fetchall()
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
        """
        with self._lock:
            self.cursor.execute(
                """
                SELECT id, simbolo, nombre, categoria, simbolo_broker
                FROM activos
                WHERE estado_operativo = 'ACTIVO'
                ORDER BY id;
                """
            )
            cols = ["id", "simbolo", "nombre", "categoria", "simbolo_broker"]
            res = [dict(zip(cols, row)) for row in self.cursor.fetchall()]
            self._last_assets_cache = res # V10.6 Cache local
            return res

    # Alias de compatibilidad hacia atras
    def obtener_activos_encendidos(self) -> list:
        return [a["simbolo"] for a in self.obtener_activos_patrullaje()]

    def obtener_impactos_por_activo(self, id_activo: int) -> list:
        """
        Retorna los impactos de regimenes ACTIVO/FORMANDOSE para un activo especifico.
        """
        with self._lock:
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

    # Mantenemos get_regimenes_activos como alias para backward-compat
    def get_regimenes_activos(self) -> list:
        """Deprecated: usar obtener_impactos_por_activo(id_activo). Retorna lista vacia."""
        return []

    def obtener_simbolo_broker(self, simbolo_interno: str) -> str | None:
        """
        Traduce el símbolo estándar interno (ej: 'XAUUSD') al nombre del broker.
        """
        with self._lock:
            self.cursor.execute(
                "SELECT simbolo_broker FROM activos WHERE simbolo = %s;",
                (simbolo_interno,)
            )
            fila = self.cursor.fetchone()
            if not fila or not fila[0]:
                return None
            return fila[0]

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
                      v_hurst: float = 0.5, v_sniper: float = 0.0):
        """Inserta una fila en registro_senales con bloqueo de hilo (V10.0 Enhanced)."""
        with self._lock:
            self.cursor.execute(
                """
                INSERT INTO registro_senales
                    (activo_id, voto_tendencia, voto_nlp, voto_order_flow,
                     voto_final_ponderado, decision_gerente, motivo,
                     voto_volume, voto_cross, voto_hurst, voto_sniper)
                SELECT id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                FROM activos WHERE simbolo = %s;
                """,
                (v_trend, v_nlp, v_flow, veredicto, decision, motivo, 
                 v_vol, v_cross, v_hurst, v_sniper, simbolo),
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
                        (activo_id, ticket_mt5, tipo_orden, tamano_real_usd, volumen_lotes,
                         precio_entrada, stop_loss, take_profit, fee_comision, justificacion_entrada)
                    SELECT a.id, %(ticket_mt5)s, %(tipo_orden)s, %(tamano_real_usd)s,
                           %(volumen_lotes)s, %(precio_entrada)s, %(stop_loss)s,
                           %(take_profit)s, %(fee_comision)s, %(justificacion_entrada)s
                    FROM activos a WHERE a.simbolo = %(simbolo)s;
                    """,
                    datos,
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error guardando operacion: {e}")
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
    def update_estado_bot(self, estado: str, pensamiento: str):
        """Upsert en estado_bot con bloqueo de hilo (V8.0)."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO estado_bot (id, estado_general, pensamiento_actual, tiempo)
                    VALUES (1, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE
                        SET estado_general    = EXCLUDED.estado_general,
                            pensamiento_actual = EXCLUDED.pensamiento_actual,
                            tiempo            = CURRENT_TIMESTAMP;
                    """,
                    (estado, pensamiento),
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
        """Atomic batch insert into cache_nlp_impactos."""
        with self._lock:
            try:
                self.cursor.executemany(
                    """
                    INSERT INTO cache_nlp_impactos (simbolo, voto, razonamiento, hash_contexto, hash_regimenes)
                    VALUES (%s, %s, %s, %s, 'v9_migrado');
                    """,
                    datos
                )
                self.conn.commit()
            except Exception as e:
                print(f"[DB] Error upserting nlp cache: {e}")
                self.conn.rollback()

    @survival_shield
    def leer_cache_nlp(self, hash_ctx: str, id_activo: int) -> float | None:
        """Atomic check of nlp cache."""
        with self._lock:
            try:
                self.cursor.execute(
                    """
                    SELECT c.voto 
                    FROM cache_nlp_impactos c
                    JOIN activos a ON a.simbolo = c.simbolo
                    WHERE c.hash_contexto = %s AND a.id = %s
                    LIMIT 1;
                    """,
                    (hash_ctx, id_activo)
                )
                fila = self.cursor.fetchone()
                return float(fila[0]) if fila else None
            except Exception as e:
                print(f"[DB] Error reading nlp cache: {e}")
                return None

    # --- V11.0: TELEGRAM INTERACTIVE READS ---
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
                SELECT a.simbolo, rs.voto_tendencia, rs.voto_nlp, rs.voto_order_flow,
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
            cols = ["simbolo", "trend", "nlp", "flow", "vol", "cross", "hurst", "sniper", "veredicto", "ia_analysis", "fecha"]
            return [dict(zip(cols, row)) for row in self.cursor.fetchall()]


# ------------------------------------------------------------------
# Test de Conexión (ejecutar directamente: python config/db_connector.py)
# ------------------------------------------------------------------
if __name__ == "__main__":
    db = DBConnector()
    if db.conectar():
        db.test_conexion()
        db.desconectar()
