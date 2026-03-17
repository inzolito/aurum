import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.notifier import _enviar_telegram

print("Enviando mensaje de prueba a Telegram...")
_enviar_telegram("🧪 <b>TEST DE CONEXIÓN AURUM</b>\nEl sistema de notificaciones está respondiendo correctamente.")
print("Verifica tu celular.")
