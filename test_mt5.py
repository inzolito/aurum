"""
Script de prueba: Fase 2.3 - MT5Connector
Conecta a MetaTrader 5, pide las últimas 5 velas M1 de XAUUSD_i
y las imprime en consola.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from config.mt5_connector import MT5Connector


def separador(titulo):
    print(f"\n{'='*55}")
    print(f"  {titulo}")
    print(f"{'='*55}")


def main():
    mt5 = MT5Connector()

    separador("1. Conectar a MT5")
    if not mt5.conectar():
        print("CRITICAL: No se pudo conectar a MT5.")
        print("Asegúrate de que MetaTrader 5 esté abierto y logeado.")
        sys.exit(1)

    separador("2. Precio actual XAUUSD_i")
    precio = mt5.obtener_precio_actual("XAUUSD_i")
    if precio:
        print(f"  Bid : {precio['bid']}")
        print(f"  Ask : {precio['ask']}")
        print(f"  Spread: {precio['spread']}")

    separador("3. Ultimas 5 velas M1 - XAUUSD_i")
    df = mt5.obtener_velas("XAUUSD_i", cantidad=5)
    if df.empty:
        print("  ERROR: No se pudieron obtener las velas.")
    else:
        print(df.to_string(index=False))

    separador("RESULTADO FINAL")
    print("  El bot puede 'ver' el mercado. MT5Connector operativo.")

    mt5.desconectar()


if __name__ == "__main__":
    main()
