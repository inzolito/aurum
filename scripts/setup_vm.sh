#!/bin/bash
# =============================================================================
# Aurum — Setup inicial del VM aurum-server (GCP)
# Ejecutar UNA SOLA VEZ en el VM después del primer deploy.
# Uso: bash /opt/aurum/scripts/setup_vm.sh
# =============================================================================
set -e

AURUM_DIR="/opt/aurum"
AURUM_USER="aurum_bot"
PYTHON_VERSION="3.11"

echo "============================================"
echo " Aurum Bot — Setup VM (Ubuntu/Debian)"
echo "============================================"

# 1. Paquetes del sistema
echo "[1/7] Instalando paquetes del sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    build-essential \
    libpq-dev \
    git \
    curl \
    screen \
    htop \
    jq

# 2. Usuario del servicio (sin login)
echo "[2/7] Creando usuario $AURUM_USER..."
if ! id "$AURUM_USER" &>/dev/null; then
    sudo useradd --system --no-create-home --shell /bin/false "$AURUM_USER"
    echo "    Usuario creado."
else
    echo "    Usuario ya existe, saltando."
fi

# 3. Permisos del directorio
echo "[3/7] Configurando permisos de $AURUM_DIR..."
sudo chown -R "$AURUM_USER":root "$AURUM_DIR"
sudo chmod -R 750 "$AURUM_DIR"
# Los logs necesitan ser escribibles
sudo mkdir -p "$AURUM_DIR/logs" "$AURUM_DIR/temp"
sudo chown -R "$AURUM_USER":root "$AURUM_DIR/logs" "$AURUM_DIR/temp"
sudo chmod -R 770 "$AURUM_DIR/logs" "$AURUM_DIR/temp"

# 4. Entorno virtual Python
echo "[4/7] Creando venv en $AURUM_DIR/venv..."
if [ ! -d "$AURUM_DIR/venv" ]; then
    sudo -u "$AURUM_USER" python${PYTHON_VERSION} -m venv "$AURUM_DIR/venv"
fi

echo "[4/7] Instalando dependencias Python..."
sudo -u "$AURUM_USER" "$AURUM_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$AURUM_USER" "$AURUM_DIR/venv/bin/pip" install --quiet -r "$AURUM_DIR/requirements_linux.txt"

# 5. Copiar archivo .env (debe existir en /opt/aurum/.env)
echo "[5/7] Verificando .env..."
if [ ! -f "$AURUM_DIR/.env" ]; then
    echo "⚠️  ADVERTENCIA: No se encontró $AURUM_DIR/.env"
    echo "    Crea el archivo manualmente antes de iniciar los servicios."
    echo "    Usa $AURUM_DIR/.env.example como plantilla."
else
    sudo chmod 600 "$AURUM_DIR/.env"
    sudo chown "$AURUM_USER":root "$AURUM_DIR/.env"
    echo "    .env encontrado y asegurado."
fi

# 6. Instalar servicios systemd
echo "[6/7] Instalando servicios systemd..."
for SERVICE_FILE in "$AURUM_DIR/scripts/services/"*.service; do
    SERVICE_NAME=$(basename "$SERVICE_FILE")
    sudo cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME"
    echo "    Instalado: $SERVICE_NAME"
done

sudo systemctl daemon-reload

# 7. Habilitar e iniciar servicios
echo "[7/7] Habilitando servicios..."
sudo systemctl enable aurum-core.service
sudo systemctl enable aurum-hunter.service
sudo systemctl enable aurum-telegram.service

echo ""
echo "============================================"
echo " Setup completado."
echo "============================================"
echo ""
echo " Para iniciar los servicios:"
echo "   sudo systemctl start aurum-core"
echo "   sudo systemctl start aurum-hunter"
echo "   sudo systemctl start aurum-telegram"
echo ""
echo " Para ver logs en tiempo real:"
echo "   sudo journalctl -u aurum-core -f"
echo "   sudo journalctl -u aurum-hunter -f"
echo "   sudo journalctl -u aurum-telegram -f"
echo ""
echo " Para verificar estado:"
echo "   sudo systemctl status aurum-core aurum-hunter aurum-telegram"
echo ""
