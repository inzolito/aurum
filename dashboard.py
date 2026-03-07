import os
import sys
import time
from datetime import datetime
import pandas as pd
from config.db_connector import DBConnector

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    print("=" * 100)
    print(f"  AURUM OMNI - {title}")
    print("=" * 100)

def show_status_table(db):
    clear_screen()
    print_header("ESTADO DE ACTIVOS (DIRECTO DB)")
    
    data = db.get_dashboard_data()
    if not data:
        print("\n[!] No hay datos de señales registrados en la base de datos.")
        input("\nPresione Enter para volver al menú...")
        return

    # Create DataFrame for nice printing
    df = pd.DataFrame(data)
    
    # Rename columns for clarity
    df.columns = [
        "Activo", "Trend", "NLP", "Flow", "Vol", 
        "Cross", "Hurst", "Sniper", "Total", "Razonamiento IA", "Ultimo Ciclo"
    ]
    
    # Fill NaN IA analysis (especially after cache clear)
    df["Razonamiento IA"] = df["Razonamiento IA"].fillna("Esperando proximo ciclo de IA...")
    
    # Format numeric columns
    numeric_cols = ["Trend", "NLP", "Flow", "Vol", "Cross", "Hurst", "Sniper", "Total"]
    for col in numeric_cols:
        df[col] = df[col].apply(lambda x: f"{float(x):+.2f}" if x is not None and pd.notnull(x) else "N/A")
    
    # Format timestamp
    df["Ultimo Ciclo"] = pd.to_datetime(df["Ultimo Ciclo"]).dt.strftime('%H:%M:%S')

    # Display table (truncated reasoning for the table view)
    display_df = df.copy()
    display_df["Razonamiento IA"] = display_df["Razonamiento IA"].apply(
        lambda x: (x[:50] + "...") if isinstance(x, str) and len(x) > 50 else x
    )
    
    print(display_df.to_string(index=False))
    
    print("\n" + "-" * 100)
    print("TIP: Los valores N/A significan que el activo aun no ha corrido con la V10.0.")
    print(f"Ultima actualizacion del sistema: {datetime.now().strftime('%H:%M:%S')}")
    input("\nPresione Enter para volver al menú...")

def show_news_radar(db):
    clear_screen()
    print_header("RADAR DE NOTICIAS (HISTORICO)")
    
    noticias = db.get_radar_noticias()
    if not noticias:
        print("\n[!] No hay noticias analizadas en la base de datos.")
    else:
        for n in noticias:
            fecha_str = n['fecha'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[ {n['simbolo']} ] - {fecha_str}")
            print(f"Razonamiento: {n['razonamiento']}")
            print("-" * 60)
            
    input("\nPresione Enter para volver al menú...")

def restart_bot():
    print("\n[!] Reiniciando el bot...")
    # Kill all python processes EXCEPT this one
    current_pid = os.getpid()
    if os.name == 'nt':
        # On Windows, we can use taskkill to kill main.py specifically by checking command line
        # but for simplicity and since the user usually only runs this bot:
        os.system(f'taskkill /F /FI "IMAGENAME eq python.exe" /FI "PID ne {current_pid}"')
    else:
        os.system(f"pkill -f main.py")
    
    time.sleep(2)
    
    # Start main.py in the background
    try:
        if os.name == 'nt':
            import subprocess
            subprocess.Popen([sys.executable, "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            os.system("nohup python3 main.py > bot.log 2>&1 &")
        print("\n[OK] Bot iniciado en una nueva consola.")
    except Exception as e:
        print(f"\n[ERROR] No se pudo iniciar el bot: {e}")
    
    time.sleep(2)

def main_menu():
    db = DBConnector()
    if not db.conectar():
        print("Error: No se pudo conectar a la base de datos.")
        sys.exit(1)
        
    try:
        while True:
            clear_screen()
            print_header("MENU TACTICO")
            print("1. Ver Tablero Global de Activos (7 Obreros)")
            print("2. Ver Radar de Noticias (Analisis Previos)")
            print("3. Reiniciar Bot (Kill & Start)")
            print("4. Refrescar")
            print("5. Salir")
            
            opcion = input("\nSeleccione una opcion: ")
            
            if opcion == "1":
                show_status_table(db)
            elif opcion == "2":
                show_news_radar(db)
            elif opcion == "3":
                restart_bot()
            elif opcion == "4":
                continue
            elif opcion == "5":
                print("\nSaliendo del dashboard...")
                break
            else:
                print("\nOpcion no valida.")
                time.sleep(1)
                
    finally:
        db.desconectar()

if __name__ == "__main__":
    main_menu()
