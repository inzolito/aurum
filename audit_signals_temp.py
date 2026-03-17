import sys
import os
sys.path.append(os.getcwd())
from config.db_connector import DBConnector

db = DBConnector()
if db.conectar():
    query = """
    SELECT 
        fecha, 
        simbolo, 
        veredicto, 
        confianza, 
        estado, 
        motivo_rechazo 
    FROM registro_senales 
    ORDER BY fecha DESC 
    LIMIT 15;
    """
    db.cursor.execute(query)
    rows = db.cursor.fetchall()
    
    if rows:
        print(f"{'FECHA':<20} | {'ACTIVO':<8} | {'VEREDICTO':<8} | {'CONF.':<6} | {'ESTADO':<15} | {'MOTIVO'}")
        print("-" * 100)
        for r in rows:
            try:
                # Si es dict
                f = str(r.get('fecha'))[:19]
                s = r.get('simbolo')
                v = float(r.get('veredicto', 0))
                c = float(r.get('confianza', 0))
                e = r.get('estado')
                m = r.get('motivo_rechazo')
                print(f"{f:<20} | {s:<8} | {v:<8.4f} | {c:<6.2f} | {e:<15} | {m}")
            except:
                # Si es tuple
                f = str(r[0])[:19]
                s = r[1]
                v = float(r[2])
                c = float(r[3])
                e = r[4]
                m = r[5]
                print(f"{f:<20} | {s:<8} | {v:<8.4f} | {c:<6.2f} | {e:<15} | {m}")
    else:
        print("No se encontraron registros en registro_senales.")
    db.desconectar()
