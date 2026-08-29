#!/data/data/com.termux/files/usr/bin/bash
# Actualización incremental para instalaciones hechas con curl | sh.
# No vuelve a instalar Debian, Python, FFmpeg ni borra la configuración del usuario.
set -euo pipefail

REPOSITORY_ARCHIVE_URL="${OFBACKUP_UPDATE_ARCHIVE_URL:-https://github.com/tacosandtypescript-debug/of-downloader/archive/refs/heads/main.tar.gz}"
APP_HOME="${HOME}/.local/share/ofbackup"
CONTAINER_APP_HOME="/root/.local/share/ofbackup"
CONTAINER="ofbackup-debian"
CACHE_DIR="${HOME}/.cache/ofbackup"
PREFIX_BIN="${PREFIX:-}/bin"
LOG_FILE="${HOME}/ofbackup-actualizacion.log"
TEMP_DIR=""

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE" || {
    echo "✗ No se pudo crear el registro: $LOG_FILE" >&2
    exit 1
}
chmod 600 "$LOG_FILE" 2>/dev/null || true

# Conserva la salida visible y una copia completa para diagnosticar errores.
# Nunca se imprimen aquí los contenidos del JSON de autenticación.
exec > >(tee -a "$LOG_FILE") 2>&1

on_error() {
    local code="$?"
    local line="$1"
    trap - ERR
    echo "✗ Falló la actualización en la línea $line (código $code)." >&2
    echo "Registro completo: $LOG_FILE" >&2
    exit "$code"
}

trap 'on_error "$LINENO"' ERR

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}

trap cleanup EXIT
trap 'exit 130' INT TERM

fail() {
    echo "✗ $*" >&2
    echo "Registro completo: $LOG_FILE" >&2
    exit 1
}

echo "=== OF Downloader · actualización incremental ==="
echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S %z')"
echo "Termux: ${PREFIX:-desconocido}"
echo "Arquitectura: $(uname -m 2>/dev/null || echo desconocida)"
echo "Contenedor: $CONTAINER"
echo "Registro: $LOG_FILE"

if [[ "${PREFIX:-}" != *"com.termux"* ]]; then
    fail "Este actualizador debe ejecutarse dentro de Termux."
fi

command -v curl >/dev/null 2>&1 || fail "Falta curl. Ejecuta: pkg install -y curl"
command -v tar >/dev/null 2>&1 || fail "Falta tar. Ejecuta: pkg install -y tar"
command -v proot-distro >/dev/null 2>&1 || \
    fail "Falta proot-distro. Ejecuta primero la instalación de OF Downloader."

if [[ ! -x "$APP_HOME/.venv/bin/python" ]]; then
    fail "No encuentro el motor instalado en $APP_HOME. Ejecuta instalar-termux.sh una sola vez."
fi

CONTAINER_DIR="${PREFIX}/var/lib/proot-distro/containers/${CONTAINER}/rootfs"
if [[ ! -d "$CONTAINER_DIR" ]]; then
    fail "No encuentro Debian ($CONTAINER). Ejecuta instalar-termux.sh una sola vez."
fi

mkdir -p "$CACHE_DIR"
chmod 700 "$CACHE_DIR" 2>/dev/null || true
TEMP_DIR="$(mktemp -d "$CACHE_DIR/incremental.XXXXXX")" || \
    fail "No se pudo crear la carpeta temporal de actualización."

ARCHIVE="$TEMP_DIR/of-downloader-main.tar.gz"
SOURCE_DIR="$TEMP_DIR/source"

echo "Descargando solo el código actualizado…"
if ! curl -fL --retry 3 --retry-delay 1 --connect-timeout 15 \
    "$REPOSITORY_ARCHIVE_URL" -o "$ARCHIVE"; then
    fail "No se pudo obtener la actualización desde GitHub."
fi

mkdir -p "$SOURCE_DIR"
tar -xzf "$ARCHIVE" -C "$SOURCE_DIR" --strip-components=1 || \
    fail "El paquete de actualización está incompleto o no es válido."

for required in deploy/termux/launcher ofbackup_cli.py requirements/termux.txt backend frontend; do
    [[ -e "$SOURCE_DIR/$required" ]] || \
        fail "La actualización no contiene el componente requerido: $required"
done

requirements_changed=0
if [[ ! -f "$APP_HOME/requirements-termux.txt" ]] || \
   ! cmp -s "$SOURCE_DIR/requirements/termux.txt" "$APP_HOME/requirements-termux.txt"; then
    requirements_changed=1
fi

mkdir -p "$APP_HOME/backend" "$APP_HOME/frontend"
install -m 600 "$SOURCE_DIR/ofbackup_cli.py" "$APP_HOME/ofbackup_cli.py"
cp -R "$SOURCE_DIR/backend/." "$APP_HOME/backend/"
cp -R "$SOURCE_DIR/frontend/." "$APP_HOME/frontend/"
chmod -R u=rwX,go= "$APP_HOME/backend" "$APP_HOME/frontend"
install -m 600 "$SOURCE_DIR/requirements/termux.txt" "$APP_HOME/requirements-termux.txt"

mkdir -p "$PREFIX_BIN"
install -m 755 "$SOURCE_DIR/deploy/termux/launcher" "$PREFIX_BIN/of"
install -m 755 "$SOURCE_DIR/deploy/termux/launcher" "$PREFIX_BIN/ofbackup"

if [[ "$requirements_changed" -eq 1 ]]; then
    echo "Las dependencias cambiaron; actualizando solo Python…"
    if ! proot-distro login --shared-home "$CONTAINER" -- \
        "$CONTAINER_APP_HOME/.venv/bin/python" -m pip install --upgrade \
        -r "$CONTAINER_APP_HOME/requirements-termux.txt"; then
        fail "El código se actualizó, pero no se pudieron actualizar las dependencias Python."
    fi
else
    echo "Dependencias Python sin cambios; se conservan las instaladas."
fi

if ! proot-distro login --shared-home "$CONTAINER" -- \
    "$CONTAINER_APP_HOME/.venv/bin/python" -m py_compile \
    "$CONTAINER_APP_HOME/ofbackup_cli.py"; then
    fail "La actualización no superó la comprobación del código Python."
fi

echo "✓ OF Downloader actualizado sin reinstalar Debian, Python ni FFmpeg."
echo "✓ Cookie, perfiles, configuración y descargas se conservaron."
echo "Registro completo: $LOG_FILE"
echo "Ejecuta: of"
