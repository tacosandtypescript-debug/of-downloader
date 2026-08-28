#!/data/data/com.termux/files/usr/bin/bash

# The installer uses Bash features (arrays, [[ ]], pipefail), but many
# Android guides invoke it as `curl ... | sh`, which bypasses the shebang.
# Re-launch from Bash before the Bash-only body is parsed.  For a piped
# invocation there is no source path, so fetch the same script into a private
# temporary file first.  `OFBACKUP_INSTALLER_URL` keeps forks/self-hosted
# copies usable without changing the normal command.
if [ -z "${BASH_VERSION:-}" ]; then
    if [ -f "${0:-}" ]; then
        exec bash "$0" "$@"
    fi

    installer_url="${OFBACKUP_INSTALLER_URL:-https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/instalar-termux.sh}"
    if ! command -v bash >/dev/null 2>&1; then
        echo "✗ Este instalador necesita Bash. Instálalo con: pkg install bash" >&2
        exit 127
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "✗ Para usar curl | sh necesitas curl y Bash instalados." >&2
        exit 127
    fi
    installer_tmp="$(mktemp 2>/dev/null || true)"
    if [ -z "$installer_tmp" ]; then
        echo "✗ No se pudo crear un temporal para relanzar el instalador." >&2
        exit 1
    fi
    trap 'rm -f "$installer_tmp"' 0 1 2 15
    if ! curl -fsSL "$installer_url" -o "$installer_tmp"; then
        echo "✗ No se pudo descargar la versión Bash del instalador." >&2
        exit 1
    fi
    bash "$installer_tmp" "$@"
    installer_status=$?
    rm -f "$installer_tmp"
    trap - 0 1 2 15
    exit "$installer_status"
fi

set -euo pipefail

SOURCE_DIR=""
SOURCE_TEMP_DIR=""
REPOSITORY_URL="${OFBACKUP_REPOSITORY_URL:-https://github.com/tacosandtypescript-debug/of-downloader.git}"
REPOSITORY_BRANCH="${OFBACKUP_REPOSITORY_BRANCH:-main}"

source_has_required_files() {
    local candidate="${1:-}"
    [[ -n "$candidate" \
        && -f "$candidate/ofbackup_cli.py" \
        && -d "$candidate/backend" \
        && -d "$candidate/frontend" \
        && -f "$candidate/requirements-termux.txt" \
        && -f "$candidate/ofbackup" ]]
}

# When this file is executed from a checkout, use that checkout directly.  A
# command such as `curl .../instalar-termux.sh | bash` has no filesystem path
# for BASH_SOURCE[0], so SOURCE_DIR is resolved later by cloning the same
# branch into a temporary directory after Git has been installed.
if [[ -n "${OFBACKUP_SOURCE_DIR:-}" && -d "${OFBACKUP_SOURCE_DIR}" ]]; then
    SOURCE_DIR="$(cd -- "${OFBACKUP_SOURCE_DIR}" && pwd)"
elif [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
elif [[ -f "$PWD/ofbackup_cli.py" ]]; then
    SOURCE_DIR="$PWD"
fi
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

safe_sleep() {
    local seconds="${1:-0.25}"
    if command -v sleep >/dev/null 2>&1; then
        sleep "$seconds"
    else
        read -r -t "$seconds" _unused_sleep_input 2>/dev/null || true
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
    elif grep -Eqi 'cannot stat .*ofbackup_cli|No se pudo obtener el código' "$LOG_FILE"; then
        echo "No se encontró el código del proyecto. Ejecuta el instalador con Bash o vuelve a descargar el repositorio."
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

cleanup_source_temp() {
    if [[ -n "$SOURCE_TEMP_DIR" && -d "$SOURCE_TEMP_DIR" ]]; then
        rm -rf -- "$SOURCE_TEMP_DIR"
    fi
}

run_with_terminal_input() {
    # With `curl ... | bash`, stdin is the script pipe.  proot cannot bind
    # that exhausted descriptor reliably, and the final menu would receive
    # EOF.  Give interactive Termux commands the real terminal whenever it is
    # available; non-interactive runs keep their inherited stdin.
    if [[ -r /dev/tty ]]; then
        "$@" </dev/tty
    else
        "$@"
    fi
}

ensure_source_dir() {
    if source_has_required_files "$SOURCE_DIR"; then
        return 0
    fi

    # A piped invocation (curl | bash) does not have the repository files next
    # to the installer.  Fetch the matching branch after the base Termux
    # packages (including git) are available, then use that checkout for the
    # normal copy step below.
    mkdir -p "$HOME/.cache"
    if ! SOURCE_TEMP_DIR="$(mktemp -d "$HOME/.cache/of-downloader-source.XXXXXX")"; then
        echo "No se pudo crear el directorio temporal para descargar el proyecto." >&2
        return 1
    fi

    if ! git clone --depth 1 --branch "$REPOSITORY_BRANCH" "$REPOSITORY_URL" "$SOURCE_TEMP_DIR/repo"; then
        echo "No se pudo descargar el código de OF Downloader desde GitHub." >&2
        return 1
    fi

    SOURCE_DIR="$SOURCE_TEMP_DIR/repo"
    if ! source_has_required_files "$SOURCE_DIR"; then
        echo "El repositorio descargado no contiene los archivos requeridos por Termux." >&2
        return 1
    fi
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
        if run_with_terminal_input "$@" 2>&1 | tee -a "$LOG_FILE"; then
            code=0
        else
            code="${PIPESTATUS[0]}"
        fi
    else
        run_with_terminal_input "$@" >>"$LOG_FILE" 2>&1 &
        ACTIVE_PID=$!
        if [[ -t 1 ]]; then
            while kill -0 "$ACTIVE_PID" 2>/dev/null; do
                local display=$((start + position / 4))
                if ((display >= end)); then display=$((end - 1)); fi
                draw_progress "$display" "$label" "${spinner[position % 4]}"
                position=$((position + 1))
                safe_sleep 0.25
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
    mkdir -p "$APP_HOME/backend" "$APP_HOME/frontend"
    cp -R "$SOURCE_DIR/backend/." "$APP_HOME/backend/"
    cp -R "$SOURCE_DIR/frontend/." "$APP_HOME/frontend/"
    chmod -R u=rwX,go= "$APP_HOME/backend" "$APP_HOME/frontend"
    install -m 600 "$SOURCE_DIR/requirements-termux.txt" "$APP_HOME/requirements-termux.txt"
}

install_ofbackup_commands() {
    install -m 755 "$SOURCE_DIR/ofbackup" "$PREFIX/bin/of"
    install -m 755 "$SOURCE_DIR/ofbackup" "$PREFIX/bin/ofbackup"
    # Keep the launcher usable immediately after a clean installation.  The
    # launcher also creates this directory defensively for existing installs.
    mkdir -p "$HOME/.cache/ofbackup"
    chmod 700 "$HOME/.cache/ofbackup" 2>/dev/null || true
    mkdir -p "$HOME/storage/downloads/OFDownloader" 2>/dev/null || mkdir -p "$HOME/OFDownloader"
}

trap cleanup_source_temp EXIT
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
    pkg install -y proot-distro git termux-tools termux-api rclone

if ! run_with_terminal_input pkg install -y qrencode >/dev/null 2>&1; then
    echo "AVISO: qrencode no esta disponible en este repositorio de Termux."
    echo "El QR es opcional; el resto del descargador continuara funcionando."
fi

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
        python3 python3-dev python3-venv python3-pip ffmpeg rclone ca-certificates git \
        build-essential pkg-config rustc cargo \
        libffi-dev libssl-dev libxml2-dev libxslt1-dev \
        libjpeg62-turbo-dev liblz4-dev libyaml-dev zlib1g-dev
    python3 -c "import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14), sys.version"
'

if ! run_with_terminal_input proot-distro login --shared-home "$CONTAINER" -- bash -lc \
    'apt-get install -y --no-install-recommends qrencode >/dev/null 2>&1'; then
    echo "AVISO: qrencode no esta disponible dentro de Debian. El QR es opcional."
fi

if ! source_has_required_files "$SOURCE_DIR"; then
    draw_progress 77 "Descargando código de OF Downloader" "|"
    printf '\n--- Descargando código de OF Downloader ---\n' >>"$LOG_FILE"
    if ! ensure_source_dir >>"$LOG_FILE" 2>&1; then
        fail_install "Descargando código de OF Downloader" 1
    fi
    complete_task 77 "Código de OF Downloader listo"
fi

run_task 77 80 "Preparando y copiando archivos de OF Downloader" prepare_ofbackup_files

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
cleanup_source_temp
trap - INT TERM
if [[ -r /dev/tty ]]; then
    exec of </dev/tty
fi
exec of
