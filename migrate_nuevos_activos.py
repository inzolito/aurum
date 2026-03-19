"""
Migración: agrega AUDUSD_i, USDCAD_i, GEREUR a la tabla activos.
Ejecutar una sola vez: venv/bin/python migrate_nuevos_activos.py
"""
import sys
sys.path.insert(0, '/opt/aurum')
from dotenv import load_dotenv
load_dotenv('/opt/aurum/.env')
from config.db_connector import DBConnector

db = DBConnector()
db.conectar()

nuevos = [
    ("AUDUSD",  "Dolar Australiano/Dolar",  "FOREX",   "AUDUSD_i"),
    ("USDCAD",  "Dolar/Dolar Canadiense",   "FOREX",   "USDCAD_i"),
    ("GEREUR",  "DAX 40 (GER40)",           "INDICES", "GEREUR"),
]

for simbolo, nombre, categoria, simbolo_broker in nuevos:
    db.cursor.execute("SELECT id FROM activos WHERE simbolo = %s", (simbolo,))
    if db.cursor.fetchone():
        print(f"[SKIP] {simbolo} ya existe en activos")
        continue
    db.cursor.execute(
        """
        INSERT INTO activos (simbolo, nombre, categoria, simbolo_broker, estado_operativo)
        VALUES (%s, %s, %s, %s, 'ACTIVO')
        """,
        (simbolo, nombre, categoria, simbolo_broker)
    )
    db.conn.commit()
    print(f"[OK] Insertado: {simbolo} ({simbolo_broker}) — {categoria}")

db.cursor.execute("SELECT id, simbolo, simbolo_broker, estado_operativo FROM activos ORDER BY id")
rows = db.cursor.fetchall()
print("\nActivos en BD:")
for r in rows:
    print(f"  {r[0]:>3}. {r[1]:<12} broker={r[2]:<14} estado={r[3]}")
