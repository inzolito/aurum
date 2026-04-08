import sys
sys.path.append('/opt/aurum')
from config.db_connector import DBConnector
from config.mt5_connector import MT5Connector

db = DBConnector()
mt5 = MT5Connector()
db.conectar()
mt5.conectar()

sb = db.obtener_simbolo_broker('AUDJPY')
print('Simbolo broker:', sb)

velas = mt5.obtener_velas(sb, 100)
if not velas.empty:
    print('Velas recientes:')
    print(velas.tail(40)[['time', 'open', 'high', 'low', 'close']])

mt5.desconectar()
db.desconectar()
