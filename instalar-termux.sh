#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_HOME="$HOME/.local/share/ofbackup"
CONTAINER="ofbackup-debian"
CONTAINER_DIR="${PREFIX:-}/var/lib/proot-distro/containers/$CONTAINER/rootfs"
LOG_FILE="$HOME/ofbackup-instalacion.log"
ACTIVE_PID=""

if [[ -t 1 ]]; then
    RED=$'\033[31m'
    GREEN=$'\033[32m'
    YELLOW=$'\033[33m'
    RESET=$'\033[0m'
else
    RED=""
    GREEN=""
    YELLOW=""
    RESET=""
fi

draw_progress() {
    local percent="$1"
    local label="$2"
    local marker="${3:-}"
    local width=24
    local filled=$((percent * width / 100))
    local empty=$((width - filled))
    local bar=""
    local index

    for ((index = 0; index < filled; index++)); do bar+="#"; done
    for ((index = 0; index < empty; index++)); do bar+="-"; done

    if [[ -t 1 ]]; then
        printf '\r\033[2K[%s] %3d%% %s %s' "$bar" "$percent" "$marker" "$label"
    else
        printf '[%s] %3d%% %s %s\n' "$bar" "$percent" "$marker" "$label"
    fi
}

suggest_fix() {
    if grep -Eqi 'No space left on device|not enough space' "$LOG_FILE"; then
        echo "Libera espacio de almacenamiento y vuelve a ejecutar el instalador."
    elif grep -Eqi 'Temporary failure resolving|Could not resolve|Network is unreachable|Connection timed out' "$LOG_FILE"; then
        echo "Comprueba Internet, usa una conexión estable y vuelve a ejecutar el instalador."
    elif grep -Eqi 'Permission denied|Operation not permitted' "$LOG_FILE"; then
        echo "Comprueba los permisos de Termux y vuelve a ejecutar el instalador."
    elif grep -Eqi 'dpkg was interrupted|Sub-process /usr/bin/dpkg|Hash Sum mismatch' "$LOG_FILE"; then
        echo "La instalación de Debian quedó incompleta. Vuelve a ejecutar este mismo script."
    elif grep -Eqi 'Failed building wheel|failed-wheel-build|Python.h: No such file' "$LOG_FILE"; then
        echo "Falló un paquete de Python. Actualiza el repositorio y ejecuta de nuevo el instalador."
    else
        echo "Vuelve a ejecutar el instalador. Si se repite, comparte las últimas líneas del registro."
    fi
}

fail_install() {
    local label="$1"
    local code="${2:-1}"
    ACTIVE_PID=""
    if [[ -t 1 ]]; then printf '\n'; fi
    echo "${RED}✗ ERROR: ${label}${RESET}"
    echo "El instalador se detuvo para no continuar con una configuración incompleta."
    echo
    echo "${YELLOW}Posible solución:${RESET}"
    suggest_fix
    echo
    echo "${YELLOW}Últimas líneas del error:${RESET}"
    tail -n 12 "$LOG_FILE" 2>/dev/null | sed 's/^/  /'
    echo
    echo "Registro completo: $LOG_FILE"
    exit "$code"
}

interrupt_install() {
    if [[ -n "$ACTIVE_PID" ]]; then
        kill "$ACTIVE_PID" 2>/dev/null || true
    fi
    if [[ -t 1 ]]; then printf '\n'; fi
    echo "${RED}✗ Instalación cancelada. Puedes ejecutar el script otra vez para continuar.${RESET}"
    exit 130
}

run_task() {
    local start="$1"
    local end="$2"
    local label="$3"
    shift 3
    local spinner=('|' '/' '-' $'\\')
    local position=0
    local code=0

    draw_progress "$start" "$label" "${spinner[0]}"
    printf '\n--- %s ---\n' "$label" >>"$LOG_FILE"

    if [[ "${OFBACKUP_VERBOSE:-0}" == "1" ]]; then
        if "$@" 2>&1 | tee -a "$LOG_FILE"; then
            code=0
        else
            code="${PIPESTATUS[0]}"
        fi
    else
        "$@" >>"$LOG_FILE" 2>&1 &
        ACTIVE_PID=$!
        if [[ -t 1 ]]; then
            while kill -0 "$ACTIVE_PID" 2>/dev/null; do
                local display=$((start + position / 4))
                if ((display >= end)); then display=$((end - 1)); fi
                draw_progress "$display" "$label" "${spinner[position % 4]}"
                position=$((position + 1))
                sleep 0.25
            done
        fi
        if wait "$ACTIVE_PID"; then
            code=0
        else
            code=$?
        fi
        ACTIVE_PID=""
    fi

    if [[ "$code" -ne 0 ]]; then
        fail_install "$label" "$code"
    fi

    draw_progress "$end" "$label" "${GREEN}✓${RESET}"
    printf '\n'
}

complete_task() {
    local percent="$1"
    local label="$2"
    draw_progress "$percent" "$label" "${GREEN}✓${RESET}"
    printf '\n'
}

prepare_ofbackup_files() {
    mkdir -p "$APP_HOME"
    install -m 600 "$SOURCE_DIR/ofbackup_cli.py" "$APP_HOME/ofbackup_cli.py"
    install -m 600 "$SOURCE_DIR/requirements-termux.txt" "$APP_HOME/requirements-termux.txt"
}

install_ofbackup_commands() {
    install -m 755 "$SOURCE_DIR/ofbackup" "$PREFIX/bin/of"
    install -m 755 "$SOURCE_DIR/ofbackup" "$PREFIX/bin/ofbackup"
    mkdir -p "$HOME/storage/downloads/OFDownloader" 2>/dev/null || mkdir -p "$HOME/OFDownloader"
}

trap interrupt_install INT TERM

if [[ "${PREFIX:-}" != *"com.termux"* ]]; then
    echo "Este instalador debe ejecutarse dentro de Termux."
    exit 1
fi

echo
echo "══════════════════════════════════════════════"
echo "  AVISO · PRIMERA INSTALACIÓN"
echo "══════════════════════════════════════════════"
echo "La primera instalación puede tardar bastante según el móvil y la conexión."
echo "La barra puede avanzar lentamente mientras se preparan Python y sus paquetes."
echo "No cierres Termux aunque un paso tarde varios minutos. Se recomienda usar"
echo "Wi-Fi, tener espacio libre y conectar el cargador."
echo

: >"$LOG_FILE"
draw_progress 0 "Iniciando instalación" ""
printf '\n'

run_task 0 8 "Consultando actualizaciones de Termux" pkg update -y
run_task 8 16 "Actualizando Termux" pkg upgrade -y
run_task 16 28 "Instalando herramientas base y selector Android" \
    pkg install -y proot-distro git termux-tools termux-api

if ! pm list packages 2>/dev/null | grep -q '^package:com.termux.api$'; then
    echo
    echo "AVISO: instala también la aplicación Termux:API."
    echo "Debe proceder de la misma fuente que Termux (F-Droid o GitHub)."
    echo "Sin ella podrás pegar datos, pero no abrir el selector Android."
    echo
fi

if [[ ! -e "$HOME/storage/downloads" ]] && command -v termux-setup-storage >/dev/null; then
    echo "Android pedirá permiso para guardar en Descargas. Pulsa Permitir."
    run_task 28 35 "Configurando acceso a Descargas" termux-setup-storage
else
    complete_task 35 "Acceso a Descargas configurado"
fi

if [[ ! -d "$CONTAINER_DIR" ]]; then
    run_task 35 48 "Instalando Debian compatible" \
        proot-distro install debian:trixie --name "$CONTAINER"
else
    complete_task 48 "Debian ya estaba instalado"
fi

run_task 48 77 "Preparando Python 3.13, FFmpeg y librerías" \
    proot-distro login --shared-home "$CONTAINER" -- bash -lc '
    set -e
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get upgrade -y
    apt-get install -y --no-install-recommends \
        python3 python3-dev python3-venv python3-pip ffmpeg ca-certificates git \
        build-essential pkg-config rustc cargo \
        libffi-dev libssl-dev libxml2-dev libxslt1-dev \
        libjpeg62-turbo-dev liblz4-dev libyaml-dev zlib1g-dev
    python3 -c "import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14), sys.version"
'

run_task 77 80 "Copiando archivos de OF Downloader" prepare_ofbackup_files

run_task 80 94 "Instalando OF Downloader y OF-Scraper" \
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

run_task 94 100 "Creando el comando of" install_ofbackup_commands

echo
echo "${GREEN}✓ Instalación terminada correctamente.${RESET}"
echo "Registro guardado en: $LOG_FILE"
echo "Abriendo el menú…"
trap - INT TERM
exec of
