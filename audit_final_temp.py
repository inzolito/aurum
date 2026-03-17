import sys
import os
sys.path.append(os.getcwd())
from config.db_connector import DBConnector

db = DBConnector()
if db.conectar():
    # Intenta unir con activos para el símbolo
    query = """
    SELECT 
        s.tiempo, 
        a.simbolo, 
        s.voto_final_ponderado as veredicto, 
        s.decision_gerente as estado, 
        s.motivo 
    FROM registro_senales s
    LEFT JOIN activos a ON s.activo_id = a.id
    ORDER BY s.tiempo DESC 
    LIMIT 20;
    """
    try:
        db.cursor.execute(query)
        rows = db.cursor.fetchall()
        
        if rows:
            print(f"{'TIEMPO':<20} | {'ACTIVO':<10} | {'VEREDICTO':<10} | {'ESTADO':<15} | {'MOTIVO'}")
            print("-" * 120)
            for r in rows:
                try:
                    # Dict handle
                    t = str(r.get('tiempo'))[:19]
                    s = r.get('simbolo') or 'UNK'
                    v = float(r.get('veredicto', 0))
                    e = r.get('estado')
                    m = r.get('motivo')
                    print(f"{t:<20} | {s:<10} | {v:<10.4f} | {e:<15} | {m}")
                except:
                    # Tuple handle
                    t = str(r[0])[:19]
                    s = r[1] or 'UNK'
                    v = float(r[2])
                    e = r[3]
                    m = r[4]
                    print(f"{t:<20} | {s:<10} | {v:<10.4f} | {e:<15} | {m}")
        else:
            print("No se encontraron registros en registro_senales.")
    except Exception as e:
        print(f"Error en query: {e}")
    db.desconectar()
