#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_HOME="$HOME/.local/share/ofbackup"
CONTAINER="ofbackup-debian"
CONTAINER_DIR="$PREFIX/var/lib/proot-distro/containers/$CONTAINER/rootfs"

if [[ "${PREFIX:-}" != *"com.termux"* ]]; then
    echo "Este instalador debe ejecutarse dentro de Termux."
    exit 1
fi

echo "[1/7] Actualizando Termux…"
pkg update -y
pkg upgrade -y

echo "[2/7] Instalando herramientas base…"
pkg install -y proot-distro git termux-tools

if [[ ! -e "$HOME/storage/downloads" ]] && command -v termux-setup-storage >/dev/null; then
    echo "[3/7] Android pedirá permiso para guardar en Descargas. Pulsa Permitir."
    termux-setup-storage || true
else
    echo "[3/7] El acceso al almacenamiento ya está configurado."
fi

if [[ ! -d "$CONTAINER_DIR" ]]; then
    echo "[4/7] Instalando Debian con Python compatible…"
    proot-distro install debian:trixie --name "$CONTAINER"
else
    echo "[4/7] Debian ya está instalado."
fi

echo "[5/7] Actualizando Python 3.13, FFmpeg y librerías…"
proot-distro login --shared-home "$CONTAINER" -- bash -lc '
    set -e
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get upgrade -y
    apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip ffmpeg ca-certificates git \
        build-essential pkg-config rustc cargo \
        libffi-dev libssl-dev libxml2-dev libxslt1-dev \
        libjpeg62-turbo-dev zlib1g-dev
    python3 -c "import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14), sys.version"
'

echo "[6/7] Instalando OF Backup y OF-Scraper…"
mkdir -p "$APP_HOME"
install -m 600 "$SOURCE_DIR/ofbackup_cli.py" "$APP_HOME/ofbackup_cli.py"
install -m 600 "$SOURCE_DIR/requirements-termux.txt" "$APP_HOME/requirements-termux.txt"

proot-distro login --shared-home "$CONTAINER" -- bash -lc '
    set -e
    cd /root/.local/share/ofbackup
    if [[ ! -x .venv/bin/python ]]; then
        python3 -m venv .venv
    fi
    .venv/bin/python -m pip install --upgrade pip setuptools wheel
    .venv/bin/python -m pip install --upgrade -r requirements-termux.txt
    .venv/bin/python -m pip check
'

echo "[7/7] Creando el comando ofbackup…"
install -m 755 "$SOURCE_DIR/ofbackup" "$PREFIX/bin/ofbackup"
mkdir -p "$HOME/storage/downloads/OFBackup" 2>/dev/null || mkdir -p "$HOME/OFBackup"

echo
echo "Instalación terminada. Abriendo el menú…"
exec ofbackup
