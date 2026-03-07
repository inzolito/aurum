from config.db_connector import DBConnector
import sys

def test_guardar():
    db = DBConnector()
    if not db.conectar():
        print("Error conectando")
        return
    
    # Simular los mismos datos del bot
    try:
        # Desactivamos el decorador temporalmente o simplemente llamamos a la funcion
        # que falla. Como ya arreglé el decorador para que no envenene la transacción,
        # ahora deberíamos ver el error real.
        db.guardar_senal(
            simbolo='EURUSD', 
            v_trend=0.16, 
            v_nlp=0.0, 
            v_flow=0.0, 
            veredicto=0.0, 
            decision='IGNORADO', 
            motivo='Veredicto insuficiente (Umbral: 0.45)', 
            v_vol=0.0, 
            v_cross=0.0, 
            v_hurst=0.5, 
            v_sniper=0.0
        )
        print("¡Exito! La insercion funciono.")
    except Exception as e:
        print(f"ERROR DETECTADO: {e}")
    finally:
        db.desconectar()

if __name__ == "__main__":
    test_guardar()
