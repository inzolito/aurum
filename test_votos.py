import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('c:\\www\\Aurum\\.env')

try:
    conn = psycopg2.connect(
        host='35.239.183.207',
        port=5432,
        dbname='aurum_db',
        user='aurum_admin',
        password=os.getenv('DB_PASS')
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (a.simbolo)
            a.simbolo, rs.voto_tendencia, rs.voto_nlp, rs.voto_sniper,
            rs.voto_volume, rs.voto_cross, rs.decision_gerente, rs.tiempo,
            rs.voto_final_ponderado, rs.voto_hurst, rs.voto_macro
        FROM registro_senales rs
        JOIN activos a ON a.id = rs.activo_id
        WHERE a.estado_operativo = 'ACTIVO'
        ORDER BY a.simbolo, rs.tiempo DESC
    """)
    rows = cur.fetchall()
    print("Rows returned:", len(rows))
    
    # Try parsing
    votos_workers = []
    for r in rows:
        try:
            votos_workers.append({
                "simbolo": r[0], "trend": round(float(r[1] or 0), 2),
                "nlp": round(float(r[2] or 0), 2), "sniper": round(float(r[3] or 0), 2),
                "volumen": round(float(r[4] or 0), 2), "cross": round(float(r[5] or 0), 2),
                "decision": r[6], "tiempo": r[7].isoformat() if r[7] else None,
                "veredicto": round(float(r[8] or 0), 3),
                "hurst": round(float(r[9] or 0), 2), "macro": round(float(r[10] or 0), 2)
            })
        except Exception as e:
            print(f"Error parsing row {r[0]}: {e}")
            break
            
    print("Parsed output length:", len(votos_workers))

except Exception as e:
    print(f"DB Error: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()
