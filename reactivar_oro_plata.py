"""
Reactiva XAUUSD y XAGUSD en la tabla activos.
Ejecutar una sola vez: venv/bin/python reactivar_oro_plata.py
"""
import sys
sys.path.insert(0, '/opt/aurum')
from dotenv import load_dotenv
load_dotenv('/opt/aurum/.env')
from config.db_connector import DBConnector

db = DBConnector()
db.conectar()

for simbolo in ("XAUUSD", "XAGUSD"):
    db.cursor.execute("SELECT id, estado_operativo FROM activos WHERE simbolo = %s", (simbolo,))
    row = db.cursor.fetchone()
    if not row:
        print(f"[ERROR] {simbolo} no encontrado en BD")
        continue
    if row[1] == 'ACTIVO':
        print(f"[SKIP] {simbolo} ya está ACTIVO")
        continue
    db.cursor.execute("UPDATE activos SET estado_operativo = 'ACTIVO' WHERE simbolo = %s", (simbolo,))
    db.conn.commit()
    print(f"[OK] {simbolo} reactivado (id={row[0]})")

db.cursor.execute("SELECT id, simbolo, simbolo_broker, estado_operativo FROM activos ORDER BY id")
rows = db.cursor.fetchall()
print("\nActivos en BD:")
for r in rows:
    estado = "✓ ACTIVO" if r[3] == 'ACTIVO' else "✗ PAUSADO"
    print(f"  {r[0]:>3}. {r[1]:<12} broker={r[2]:<14} {estado}")
