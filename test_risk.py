"""
Test de Stress: Fase 3.1 - RiskModule
Simula una intención de compra en XAUUSD_i con SL 5 USD por debajo del precio actual.
Imprime: balance, USD a arriesgar y lotaje calculado.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector
from core.risk_module import RiskModule


def separador(titulo):
    print(f"\n{'='*55}")
    print(f"  {titulo}")
    print(f"{'='*55}")


def main():
    db  = DBConnector()
    mt5 = MT5Connector()

    separador("Conexiones")
    if not db.conectar():
        print("CRITICAL: No se pudo conectar a la BD.")
        sys.exit(1)
    if not mt5.conectar():
        print("CRITICAL: No se pudo conectar a MT5.")
        sys.exit(1)

    risk = RiskModule(db, mt5)

    # ------------------------------------------------------------------
    separador("Filtro de Seguridad XAUUSD")
    ok = risk.filtro_seguridad("XAUUSD")
    print(f"  Resultado: {'VERDE - Despejado para operar' if ok else 'ROJO - Bloqueado'}")

    # ------------------------------------------------------------------
    separador("Test de Stress: Lotaje XAUUSD (SL = -5 USD)")
    import MetaTrader5 as mt5_lib
    tick = mt5_lib.symbol_info_tick("XAUUSD_i")
    precio_actual = tick.ask if tick else None

    if precio_actual:
        sl_precio = precio_actual - 5.0
        print(f"  Precio Ask actual : {precio_actual}")
        print(f"  Stop Loss simulado: {sl_precio} (5 USD por debajo)")
        print()
        lotes = risk.calcular_lotes("XAUUSD", sl_precio)
        print()
        if lotes:
            print(f"  >> Lotaje final a enviar al broker: {lotes} lotes")
        else:
            print("  >> No se pudo calcular el lotaje.")
    else:
        print("  ERROR: No se pudo obtener precio actual de XAUUSD_i")

    # ------------------------------------------------------------------
    separador("RESULTADO FINAL")
    print("  Test de Stress completado.")

    mt5.desconectar()
    db.desconectar()


if __name__ == "__main__":
    main()
