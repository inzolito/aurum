import psycopg2
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('/opt/aurum/.env')

def extract_data():
    conn = None
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=os.getenv('DB_PORT', 5432),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            connect_timeout=10
        )
        cur = conn.cursor()

        query = """
        SELECT 
            l.nombre as lab_nombre,
            a.simbolo,
            lo.tipo_orden,
            lo.precio_entrada,
            lo.precio_salida,
            lo.resultado,
            lo.pnl_virtual,
            lo.roe_pct,
            lo.tiempo_entrada,
            lo.tiempo_salida,
            ls.voto_tendencia,
            ls.voto_nlp,
            ls.voto_sniper,
            ls.voto_macro,
            ls.voto_final_ponderado,
            lo.justificacion_entrada
        FROM lab_operaciones lo
        JOIN laboratorios l ON l.id = lo.lab_id
        JOIN activos a ON a.id = lo.activo_id
        LEFT JOIN lab_senales ls ON ls.id = lo.lab_senal_id
        WHERE lo.tiempo_entrada >= NOW() - INTERVAL '7 days'
        ORDER BY lo.tiempo_entrada DESC;
        """

        cur.execute(query)
        rows = cur.fetchall()

        if not rows:
            return "No se encontraron trades en la última semana."

        # Formatear el reporte en Markdown
        report = "# Reporte de Trades de Laboratorio - Última Semana\n\n"
        report += f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        report += "| Lab | Activo | Tipo | Entrada | Salida | Res | PnL | ROE% | Tiempo Entrada | V.Trend | V.NLP | V.Sniper | Contexto AT | Justificación |\n"
        report += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"

        for row in rows:
            lab_nombre, simbolo, tipo, entrada, salida, res, pnl, roe, t_in, t_out, v_t, v_n, v_s, v_m, v_f, just = row
            
            # Parsear justificación IA y Contexto Técnico
            ia_texto = ""
            at_ctx = ""
            if just:
                try:
                    just_json = json.loads(just)
                    # El campo ia_texto suele venir del NLPWorker
                    ia_texto = just_json.get('ia_texto', '').replace('\n', ' ')
                    # El motivo_lab (o motivo_produccion) ahora contiene [AT: ...]
                    motivo = just_json.get('motivo_lab', just_json.get('motivo', '')).replace('\n', ' ')
                    
                    if "[AT:" in motivo:
                        try:
                            at_ctx = motivo.split("[AT:")[1].split("]")[0].strip()
                        except:
                            at_ctx = "Error parsing AT"
                    
                    if not ia_texto:
                        ia_texto = motivo
                except:
                    ia_texto = just.replace('\n', ' ')
                    if "[AT:" in ia_texto:
                        try:
                            at_ctx = ia_texto.split("[AT:")[1].split("]")[0].strip()
                        except:
                          at_ctx = "Error parsing AT"

            # Formatear valores
            entrada = f"{entrada:.4f}" if entrada else "—"
            salida = f"{salida:.4f}" if salida else "—"
            pnl = f"{pnl:+.2f}" if pnl is not None else "—"
            roe = f"{roe:+.2f}%" if roe is not None else "—"
            t_in = t_in.strftime('%Y-%m-%d %H:%M') if t_in else "—"
            
            v_t = f"{v_t:+.2f}" if v_t is not None else "—"
            v_n = f"{v_n:+.2f}" if v_n is not None else "—"
            v_s = f"{v_s:+.2f}" if v_s is not None else "—"

            # Limpiar el ia_texto para que no sea redundante si ya sacamos el AT
            ia_texto_limpio = ia_texto.split("[AT:")[0].strip() if "[AT:" in ia_texto else ia_texto
            if not ia_texto_limpio:
                ia_texto_limpio = ia_texto

            report += f"| {lab_nombre} | {simbolo} | {tipo} | {entrada} | {salida} | {res or 'OPEN'} | {pnl} | {roe} | {t_in} | {v_t} | {v_n} | {v_s} | {at_ctx} | {ia_texto_limpio[:100]}... |\n"

        return report

    except Exception as e:
        return f"Error en la extracción: {e}"
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    markdown_report = extract_data()
    print(markdown_report)
    with open('/tmp/temp_lab_report.md', 'w', encoding='utf-8') as f:
        f.write(markdown_report)
