"""
Test del Gerente Ensemble — Evalúa XAUUSD en modo simulación
y verifica la auditoría en registro_senales.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.manager import Manager


def main():
    db  = DBConnector()
    mt5 = MT5Connector()

    if not db.conectar() or not mt5.conectar():
        print("ERROR: Conexión fallida.")
        sys.exit(1)

    gerente = Manager(db, mt5)

    # Evaluar XAUUSD en modo simulación
    resultado = gerente.evaluar("XAUUSD", modo_simulacion=True)

    # Verificar auditoría en GCP
    print(f"\n{'='*60}")
    print("  Verificando registro_senales en GCP...")
    print(f"{'='*60}")
    db.cursor.execute("""
        SELECT rs.tiempo, a.simbolo,
               rs.voto_tendencia, rs.voto_nlp, rs.voto_order_flow,
               rs.voto_final_ponderado, rs.decision_gerente, rs.motivo
        FROM registro_senales rs
        JOIN activos a ON a.id = rs.activo_id
        ORDER BY rs.tiempo DESC LIMIT 1;
    """)
    fila = db.cursor.fetchone()
    if fila:
        print(f"  Tiempo    : {fila[0]}")
        print(f"  Simbolo   : {fila[1]}")
        print(f"  Trend     : {fila[2]:+.3f}")
        print(f"  NLP       : {fila[3]:+.3f}")
        print(f"  Flow      : {fila[4]:+.3f}")
        print(f"  Veredicto : {fila[5]:+.4f}")
        print(f"  Decision  : {fila[6]}")
        print(f"  Motivo    : {fila[7][:120]}...")
    else:
        print("  ERROR: No se encontro fila en registro_senales.")

    mt5.desconectar()
    db.desconectar()


if __name__ == "__main__":
    main()
