import os

SERVICES_DIR = "/opt/aurum/scripts/services"
SYSTEMD_DIR = "/etc/systemd/system"

os.makedirs(SERVICES_DIR, exist_ok=True)

SERVICIOS = {
    "aurum-core.service": """[Unit]
Description=Aurum Motor Principal
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=aurum_bot
WorkingDirectory=/opt/aurum
EnvironmentFile=/opt/aurum/.env
ExecStart=/opt/aurum/venv/bin/python main.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aurum-core

[Install]
WantedBy=multi-user.target
""",
    "aurum-hunter.service": """[Unit]
Description=Aurum News Hunter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=aurum_bot
WorkingDirectory=/opt/aurum
EnvironmentFile=/opt/aurum/.env
ExecStart=/opt/aurum/venv/bin/python news_hunter.py
Restart=always
RestartSec=20
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aurum-hunter

[Install]
WantedBy=multi-user.target
""",
    "aurum-telegram.service": """[Unit]
Description=Aurum Telegram Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=aurum_bot
WorkingDirectory=/opt/aurum
EnvironmentFile=/opt/aurum/.env
ExecStart=/opt/aurum/venv/bin/python telegram_daemon.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aurum-telegram

[Install]
WantedBy=multi-user.target
""",
}

for nombre, contenido in SERVICIOS.items():
    ruta = os.path.join(SERVICES_DIR, nombre)
    with open(ruta, "w") as f:
        f.write(contenido)
    os.system(f"cp {ruta} {SYSTEMD_DIR}/{nombre}")
    print(f"OK: {nombre}")

os.system("systemctl daemon-reload")
os.system("systemctl enable aurum-core aurum-hunter aurum-telegram")
os.system("systemctl start aurum-core aurum-hunter aurum-telegram")
print("\nListo. Verificando estado...")
os.system("systemctl status aurum-core aurum-hunter aurum-telegram --no-pager -l")
