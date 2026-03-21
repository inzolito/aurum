"""
Backfill: genera autopsias Gemini para todos los trades PERDIDOS sin análisis.
Ejecutar una sola vez: venv/bin/python backfill_autopsias.py
"""
import sys, json, time
sys.path.insert(0, '/opt/aurum')
from dotenv import load_dotenv
load_dotenv('/opt/aurum/.env')
from config.db_connector import DBConnector

db = DBConnector()
db.conectar()

db.cursor.execute("""
    SELECT ro.ticket_mt5, a.simbolo, ro.pnl_usd, ro.justificacion_entrada
    FROM registro_operaciones ro
    JOIN activos a ON a.id = ro.activo_id
    LEFT JOIN autopsias_perdidas ap ON ap.ticket_mt5 = ro.ticket_mt5
    WHERE ro.resultado_final = 'PERDIDO' AND ap.id IS NULL
    ORDER BY ro.tiempo_entrada DESC
""")
pendientes = db.cursor.fetchall()
print(f"[BACKFILL] {len(pendientes)} trades sin autopsia")

from workers.worker_nlp import _llamar_gemini_api, GEMINI_MODEL_LITE

for ticket, simbolo, pnl, justificacion_raw in pendientes:
    try:
        motivo = "Sin registro de justificación"
        if justificacion_raw:
            try:
                j = json.loads(justificacion_raw) if isinstance(justificacion_raw, str) else justificacion_raw
                motivo = j.get("ia_texto") or json.dumps(j, ensure_ascii=False)[:500]
            except Exception:
                motivo = str(justificacion_raw)[:500]

        prompt = (
            f"AUTOPSIA DE TRADE PERDEDOR — Sistema Aurum\n\n"
            f"ACTIVO: {simbolo}\n"
            f"TICKET: {ticket}\n"
            f"PERDIDA: ${abs(float(pnl or 0)):.2f} USD\n\n"
            f"JUSTIFICACION ORIGINAL DE ENTRADA:\n{motivo}\n\n"
            f"TAREA:\n"
            f"1. Identifica el fallo principal: tecnico (trend/flow/structure), macro (nlp), timing o riesgo.\n"
            f"2. Cual senal de advertencia se ignoro o peso incorrectamente?\n"
            f"3. Sugiere UNA correccion concreta al sistema.\n\n"
            f"Responde SOLO en JSON (sin markdown):\n"
            f"{{\"tipo_fallo\": \"TECNICO|MACRO|TIMING|RIESGO\", "
            f"\"worker_culpable\": \"TrendWorker|NLPWorker|FlowWorker|StructureWorker|Otro\", "
            f"\"descripcion\": \"...\", \"correccion_sugerida\": \"...\"}}"
        )

        texto = _llamar_gemini_api(prompt, model=GEMINI_MODEL_LITE)
        if not texto:
            print(f"  [SKIP] #{ticket} — Gemini sin respuesta")
            continue

        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio < 0 or fin <= inicio:
            print(f"  [SKIP] #{ticket} — JSON no encontrado en respuesta")
            continue

        data = json.loads(texto[inicio:fin])
        db.guardar_autopsia(
            ticket=ticket,
            simbolo=simbolo,
            pnl=float(pnl or 0),
            tipo_fallo=data.get("tipo_fallo", "DESCONOCIDO"),
            worker_culpable=data.get("worker_culpable", "Desconocido"),
            descripcion=data.get("descripcion", ""),
            correccion=data.get("correccion_sugerida", "")
        )
        print(f"  [OK] #{ticket} {simbolo} -> {data.get('tipo_fallo')} | {data.get('worker_culpable')}")
        time.sleep(1.5)  # respetar rate limit Gemini

    except Exception as e:
        print(f"  [ERROR] #{ticket} {simbolo}: {e}")

print("[BACKFILL] Completado.")
