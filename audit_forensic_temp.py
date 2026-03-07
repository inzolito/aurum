import sys
import os
sys.path.append(os.getcwd())
from config.db_connector import DBConnector

db = DBConnector()
if db.conectar():
    query = """
    SELECT 
        s.tiempo, 
        a.simbolo, 
        s.voto_tendencia as "Trend", 
        s.voto_order_flow as "Flow", 
        s.voto_nlp as "NLP",
        s.voto_final_ponderado as "Final",
        s.decision_gerente as "Estado",
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
            print(f"{'HORA':<9} | {'ACTIVO':<8} | {'TREND':<6} | {'FLOW':<6} | {'NLP':<6} | {'FINAL':<6} | {'ESTADO':<12} | {'MOTIVO'}")
            print("-" * 130)
            for r in rows:
                try:
                    # Dict handle
                    t = str(r.get('tiempo'))[11:19]
                    s = r.get('simbolo') or 'UNK'
                    vt = float(r.get('Trend', 0))
                    vf = float(r.get('Flow', 0))
                    vn = float(r.get('NLP', 0))
                    v_fin = float(r.get('Final', 0))
                    e = r.get('Estado')
                    m = r.get('motivo')
                    print(f"{t:<9} | {s:<8} | {vt:<+6.2f} | {vf:<+6.2f} | {vn:<+6.2f} | {v_fin:<+6.2f} | {e:<12} | {m[:60]}")
                except:
                    # Tuple handle
                    t = str(r[0])[11:19]
                    s = r[1] or 'UNK'
                    vt = float(r[2])
                    vf = float(r[3])
                    vn = float(r[4])
                    v_fin = float(r[5])
                    e = r[6]
                    m = r[7]
                    print(f"{t:<9} | {s:<8} | {vt:<+6.2f} | {vf:<+6.2f} | {vn:<+6.2f} | {v_fin:<+6.2f} | {e:<12} | {m[:60]}")
        else:
            print("No se encontraron registros.")
    except Exception as e:
        print(f"Error: {e}")
    db.desconectar()
