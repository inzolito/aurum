"""
Script de insercion retroactiva de entradas del lab de indices (lab_id=8).
Se ejecuta UNA sola vez para recuperar las entradas que el sistema ignoro
por pesos erroneos antes del fix de 2026-03-23.
"""
import sys
sys.path.insert(0, '/opt/aurum')

import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv('/opt/aurum/.env')

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', 5432),
    dbname=os.getenv('DB_NAME', 'aurum_db'),
    user=os.getenv('DB_USER', 'aurum_admin'),
    password=os.getenv('DB_PASSWORD', '')
)
cur = conn.cursor()

# Obtener version activa
cur.execute("SELECT id FROM versiones_sistema WHERE estado='ACTIVA' ORDER BY id DESC LIMIT 1")
row = cur.fetchone()
version_id = row[0] if row else None
print(f"Version activa: {version_id}")

# Entradas retroactivas:
# Precio = precio real confirmado en produccion ~20:38-20:40 UTC
# sl = precio * 0.005 * 4.0 (sl_atr_multiplier=4.0)
# tp = sl_dist * 2.5 (ratio_tp=2.5)
# capital = 3000 * 0.20 = 600, lotes = 0.60

entradas = [
    {
        "activo_id": 11,  # US30
        "simbolo": "US30",
        "senal_id": 1780,
        "tipo": "BUY",
        "precio": 46247.8,
        "veredicto": 0.885,
        "trend": 0.800, "nlp": 0.970, "sniper": 0.000,
        "tiempo": "2026-03-23 20:40:53+00",
    },
    {
        "activo_id": 7,  # US500
        "simbolo": "US500",
        "senal_id": 1781,
        "tipo": "BUY",
        "precio": 6588.02,
        "veredicto": 0.970,
        "trend": 0.800, "nlp": 0.990, "sniper": 0.500,
        "tiempo": "2026-03-23 20:40:53+00",
    },
    {
        "activo_id": 9,  # USTEC
        "simbolo": "USTEC",
        "senal_id": 1782,
        "tipo": "BUY",
        "precio": 24212.8,
        "veredicto": 0.890,
        "trend": 0.800, "nlp": 0.980, "sniper": 0.000,
        "tiempo": "2026-03-23 20:40:53+00",
    },
    {
        "activo_id": 21,  # FTSGBP (UK100)
        "simbolo": "FTSGBP",
        "senal_id": 1785,
        "tipo": "BUY",
        "precio": 9947.12,
        "veredicto": 0.965,
        "trend": 0.800, "nlp": 0.980, "sniper": 0.500,
        "tiempo": "2026-03-23 20:40:53+00",
    },
]

capital = 600.0
lotes = 0.60
sl_mult = 4.0
ratio_tp = 2.5

for e in entradas:
    precio = e["precio"]
    sl_dist = precio * 0.005 * sl_mult
    tp_dist = sl_dist * ratio_tp

    if e["tipo"] == "BUY":
        sl = round(precio - sl_dist, 4)
        tp = round(precio + tp_dist, 4)
    else:
        sl = round(precio + sl_dist, 4)
        tp = round(precio - tp_dist, 4)

    justificacion = json.dumps({
        "ia_texto": "",
        "motivo_lab": (
            f"[LAB-RETRO] {e['simbolo']} {e['tipo']}. "
            f"Trend={e['trend']:+.2f} NLP={e['nlp']:+.2f} Sniper={e['sniper']:+.2f}. "
            f"Veredicto={e['veredicto']:.3f}. "
            f"Precio real produccion ~20:38-20:40 UTC 2026-03-23. "
            f"Entrada ignorada por bug de pesos (NLP.peso era 0.30 en vez de 0.50)."
        )
    }, ensure_ascii=False)

    cur.execute("""
        INSERT INTO lab_operaciones
            (lab_id, activo_id, lab_senal_id, tipo_orden,
             precio_entrada, stop_loss, take_profit,
             volumen_lotes, capital_usado, justificacion_entrada,
             tiempo_entrada, version_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        8, e["activo_id"], e["senal_id"], e["tipo"],
        precio, sl, tp,
        lotes, capital, justificacion,
        e["tiempo"], version_id
    ))
    op_id = cur.fetchone()[0]
    print(f"[OK] lab_op {op_id}: {e['simbolo']} {e['tipo']} @ {precio} | SL={sl} TP={tp}")

conn.commit()
cur.close()
conn.close()
print("[DONE] Entradas retroactivas insertadas correctamente.")
