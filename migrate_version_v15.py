import sys
sys.path.insert(0, '/opt/aurum')
from dotenv import load_dotenv
load_dotenv('/opt/aurum/.env')
from config.db_connector import DBConnector

db = DBConnector()
db.conectar()

db.cursor.execute("UPDATE versiones_sistema SET estado='INACTIVA' WHERE estado='ACTIVA'")
db.cursor.execute("""
    INSERT INTO versiones_sistema (numero_version, descripcion, estado, fecha_despliegue)
    VALUES ('V15.0', 'Aurum OMNI V15.0 — MetaAPI Cloud, 9 workers, SHIELD heartbeat, PnL en tiempo real', 'ACTIVA', NOW())
""")
db.conn.commit()

db.cursor.execute("SELECT id, numero_version, estado FROM versiones_sistema ORDER BY id")
rows = db.cursor.fetchall()
print("OK:", rows)
