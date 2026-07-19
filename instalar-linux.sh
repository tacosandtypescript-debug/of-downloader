#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/of-downloader"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
LOG_FILE="${TMPDIR:-/tmp}/of-downloader-instalacion.log"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Este instalador es únicamente para Linux de escritorio."
    exit 1
fi

if [[ "${PREFIX:-}" == *com.termux* ]]; then
    echo "En Termux debes usar: bash instalar-termux.sh"
    exit 1
fi

if [[ -t 1 ]]; then
    BLUE=$'\033[38;2;0;175;240m'
    GREEN=$'\033[32m'
    RED=$'\033[31m'
    RESET=$'\033[0m'
else
    BLUE="" GREEN="" RED="" RESET=""
fi

step() { printf '%s[%s/5]%s %s\n' "$BLUE" "$1" "$RESET" "$2"; }
fail() {
    echo "${RED}✗ $1${RESET}"
    echo "Registro: $LOG_FILE"
    exit 1
}

install_system_packages() {
    local runner=()
    if [[ "$(id -u)" -ne 0 ]]; then
        command -v sudo >/dev/null 2>&1 || fail "Falta sudo para instalar las dependencias del sistema."
        runner=(sudo)
    fi

    if command -v apt-get >/dev/null 2>&1; then
        "${runner[@]}" apt-get update >>"$LOG_FILE" 2>&1 || return 1
        "${runner[@]}" apt-get install -y python3 python3-venv ffmpeg rclone >>"$LOG_FILE" 2>&1 || return 1
    elif command -v dnf >/dev/null 2>&1; then
        "${runner[@]}" dnf install -y python3 ffmpeg-free rclone >>"$LOG_FILE" 2>&1 || return 1
    elif command -v pacman >/dev/null 2>&1; then
        "${runner[@]}" pacman -Sy --needed --noconfirm python ffmpeg rclone >>"$LOG_FILE" 2>&1 || return 1
    else
        fail "No reconozco el gestor de paquetes. Instala Python 3.11–3.13, venv y FFmpeg."
    fi
}

: >"$LOG_FILE"
echo "${BLUE}OF Downloader · instalación para Linux${RESET}"
echo "Puede tardar varios minutos según el equipo y la conexión."
echo

step 1 "Comprobando dependencias del sistema…"
if ! command -v python3 >/dev/null 2>&1 || \
   ! command -v ffmpeg >/dev/null 2>&1 || \
   ! command -v rclone >/dev/null 2>&1 || \
   ! python3 -c 'import venv' >/dev/null 2>&1; then
    echo "Se instalaran Python, venv, FFmpeg y rclone. Puede pedir tu contrasena."
    install_system_packages || fail "No se pudieron instalar las dependencias."
fi

if ! python3 -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)' >/dev/null 2>&1; then
    fail "Se necesita Python 3.11, 3.12 o 3.13. Tu distribución ofrece $(python3 --version 2>&1)."
fi

step 2 "Copiando la aplicación…"
mkdir -p "$APP_DIR" "$BIN_DIR" "$APPLICATIONS_DIR"
install -m 600 "$SOURCE_DIR/ofbackup_cli.py" "$APP_DIR/ofbackup_cli.py"
install -m 600 "$SOURCE_DIR/requirements-termux.txt" "$APP_DIR/requirements-linux.txt"
printf '%s\n' "$SOURCE_DIR" >"$APP_DIR/repo-path"
chmod 600 "$APP_DIR/repo-path"

step 3 "Creando el entorno privado de Python…"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
    python3 -m venv "$APP_DIR/.venv" >>"$LOG_FILE" 2>&1 || fail "No se pudo crear el entorno de Python."
fi

step 4 "Instalando el motor de descarga…"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip >>"$LOG_FILE" 2>&1 || fail "No se pudo actualizar pip."
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements-linux.txt" >>"$LOG_FILE" 2>&1 || fail "No se pudieron instalar los paquetes de Python."

step 5 "Creando accesos directos…"
install -m 755 "$SOURCE_DIR/of-downloader-linux" "$BIN_DIR/of-downloader"
if [[ ! -e "$BIN_DIR/of" || -L "$BIN_DIR/of" ]]; then
    ln -sfn "$BIN_DIR/of-downloader" "$BIN_DIR/of"
else
    echo "AVISO: no se reemplazó $BIN_DIR/of porque ya pertenece a otro programa."
fi
cat >"$APPLICATIONS_DIR/of-downloader.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OF Downloader
Comment=Menú de descargas en la terminal
Exec=$BIN_DIR/of
Terminal=true
Categories=Network;Utility;
EOF
chmod 644 "$APPLICATIONS_DIR/of-downloader.desktop"

echo
echo "${GREEN}✓ OF Downloader quedó instalado.${RESET}"
echo "Abre el menú interactivo en la terminal ejecutando:"
echo "  $BIN_DIR/of"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo "Para usar 'of' u 'of-downloader' en una terminal nueva, añade a tu shell:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo "Descargas: ${XDG_DOWNLOAD_DIR:-$HOME/Downloads}/OFDownloader"
