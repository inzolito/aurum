# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/opt/aurum')
sys.executable = '/opt/aurum/venv/bin/python'
from dotenv import load_dotenv
load_dotenv('/opt/aurum/.env')
from config.db_connector import DBConnector

db = DBConnector()
db.conectar()
db.cursor.execute("""
    ALTER TABLE estado_bot
    ADD COLUMN IF NOT EXISTS balance NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS equity NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS pnl_flotante NUMERIC(15,2)
""")
db.conn.commit()

# Subir umbral disparo a 0.55
db.cursor.execute("""
    UPDATE parametros_sistema SET valor = '0.55'
    WHERE modulo = 'GERENTE' AND nombre_parametro = 'umbral_disparo'
""")
db.conn.commit()
print("OK - columnas + umbral 0.55")
db.cursor.execute("SELECT modulo, nombre_parametro, valor FROM parametros_sistema WHERE nombre_parametro = 'umbral_disparo'")
print(db.cursor.fetchone())
