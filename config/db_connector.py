import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


class DBConnector:
    """
    Puente CRUD entre Python y PostgreSQL (GCP).
    Centraliza todas las consultas SQL del sistema Aurum.
    """

    def __init__(self):
        self.conn = None
        self.cursor = None

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

    def get_parametros(self) -> dict:
        """
        Lee la tabla parametros_sistema.
        Retorna un dict con clave 'MODULO.nombre_parametro' y valor float.
        Ej: {'GERENTE.riesgo_trade_pct': 1.5, 'TENDENCIA.peso_voto': 0.3, ...}
        """
        self.cursor.execute("SELECT modulo, nombre_parametro, valor FROM parametros_sistema;")
        rows = self.cursor.fetchall()
        result = {}
        for modulo, nombre, valor in rows:
            # Si nombre_parametro ya incluye el prefijo del módulo, lo usa directamente
            if modulo and nombre.startswith(modulo + "."):
                clave = nombre
            else:
                clave = f"{modulo}.{nombre}" if modulo else nombre
            result[clave] = float(valor)
        return result


    def obtener_activos_patrullaje(self) -> list:
        """
        Retorna lista de dicts con todos los activos en estado ACTIVO.
        Cada dict tiene: id, simbolo, nombre, categoria, simbolo_broker.
        Este es el unico lugar donde el motor obtiene que activos vigilar.
        """
        self.cursor.execute(
            """
            SELECT id, simbolo, nombre, categoria, simbolo_broker
            FROM activos
            WHERE estado_operativo = 'ACTIVO'
            ORDER BY id;
            """
        )
        cols = ["id", "simbolo", "nombre", "categoria", "simbolo_broker"]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    # Alias de compatibilidad hacia atras
    def obtener_activos_encendidos(self) -> list:
        return [a["simbolo"] for a in self.obtener_activos_patrullaje()]

    def obtener_impactos_por_activo(self, id_activo: int) -> list:
        """
        Retorna los impactos de regimenes ACTIVO/FORMANDOSE para un activo especifico.
        Cada dict: {titulo, clasificacion, estado, valor_impacto}
        """
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
        Traduce el símbolo estándar interno (ej: 'XAUUSD') al nombre
        real que usa el broker en MT5 (ej: 'XAUUSD_i').
        Retorna None si el activo no existe o no tiene simbolo_broker configurado.
        """
        self.cursor.execute(
            "SELECT simbolo_broker FROM activos WHERE simbolo = %s;",
            (simbolo_interno,)
        )
        fila = self.cursor.fetchone()
        if not fila or not fila[0]:
            return None
        return fila[0]


    # ------------------------------------------------------------------
    # Escritura de auditoría
    # ------------------------------------------------------------------

    def guardar_senal(self, simbolo: str, v_trend: float, v_nlp: float,
                      v_flow: float, veredicto: float, decision: str, motivo: str):
        """Inserta una fila en registro_senales (incluyendo señales ignoradas)."""
        self.cursor.execute(
            """
            INSERT INTO registro_senales
                (activo_id, voto_tendencia, voto_nlp, voto_order_flow,
                 voto_final_ponderado, decision_gerente, motivo)
            SELECT id, %s, %s, %s, %s, %s, %s
            FROM activos WHERE simbolo = %s;
            """,
            (v_trend, v_nlp, v_flow, veredicto, decision, motivo, simbolo),
        )
        self.conn.commit()

    def guardar_operacion(self, datos: dict):
        """
        Inserta el registro completo del trade en registro_operaciones.
        Espera un dict con las claves del esquema, incluyendo justificacion_entrada.
        """
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

    # ------------------------------------------------------------------
    # Estado en vivo (Heartbeat)
    # ------------------------------------------------------------------

    def update_estado_bot(self, estado: str, pensamiento: str):
        """
        Upsert en estado_bot. Mantiene siempre una sola fila activa (id=1).
        Si no existe, la crea. Si existe, la actualiza.
        """
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

    def registrar_log(self, nivel: str, modulo: str, mensaje: str):
        """
        Inserta un evento en log_sistema.
        nivel: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
        """
        self.cursor.execute(
            """
            INSERT INTO log_sistema (nivel, modulo, mensaje)
            VALUES (%s, %s, %s);
            """,
            (nivel, modulo, mensaje),
        )
        self.conn.commit()


# ------------------------------------------------------------------
# Test de Conexión (ejecutar directamente: python config/db_connector.py)
# ------------------------------------------------------------------
if __name__ == "__main__":
    db = DBConnector()
    if db.conectar():
        db.test_conexion()
        db.desconectar()
