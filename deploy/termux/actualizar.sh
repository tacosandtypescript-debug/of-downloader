#!/data/data/com.termux/files/usr/bin/bash
# Actualizador del código de OF Downloader.
#
# Dos modos de origen:
#   1. Instalaciones hechas con curl | sh: descarga el paquete de GitHub.
#   2. Copia local: el lanzador de Termux pasa OFBACKUP_LOCAL_SOURCE=<repo>.
#
# No reinstala Debian, Python ni FFmpeg, y conserva la cookie, los perfiles, la
# configuración y las descargas. El código se reemplaza de forma atómica: si
# algo falla después de escribir los archivos nuevos, se restaura lo anterior.
set -euo pipefail

REPOSITORY_ARCHIVE_URL="${OFBACKUP_UPDATE_ARCHIVE_URL:-https://github.com/tacosandtypescript-debug/of-downloader/archive/refs/heads/main.tar.gz}"
APP_HOME="${HOME}/.local/share/ofbackup"
CONTAINER_APP_HOME="/root/.local/share/ofbackup"
CONTAINER="ofbackup-debian"
CACHE_DIR="${HOME}/.cache/ofbackup"
PREFIX_BIN="${PREFIX:-}/bin"
LOG_FILE="${HOME}/ofbackup-actualizacion.log"
LOCAL_SOURCE="${OFBACKUP_LOCAL_SOURCE:-}"
TEMP_DIR=""
SOURCE_DIR=""
BACKUP_DIR=""

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE" || {
    echo "✗ No se pudo crear el registro: $LOG_FILE" >&2
    exit 1
}
chmod 600 "$LOG_FILE" 2>/dev/null || true

# Conserva la salida visible y una copia completa para diagnosticar errores.
# Nunca se imprimen aquí los contenidos del JSON de autenticación.
exec > >(tee -a "$LOG_FILE") 2>&1

fail() {
    echo "✗ $*" >&2
    echo "Registro completo: $LOG_FILE" >&2
    exit 1
}

# ── Comprobaciones desde el host ──────────────────────────────────────────
# Termux ve el mismo HOME que el contenedor, pero los enlaces del venv apuntan
# a rutas del contenedor (/usr/bin/python3). Con -x el enlace queda colgado
# desde fuera y la comprobación fallaría siempre, así que se valida el enlace
# en sí (-L) además del destino (-e).
venv_python_present() {
    [[ -e "$APP_HOME/.venv/bin/python" || -L "$APP_HOME/.venv/bin/python" ]]
}

required_components_present() {
    local dir="$1"
    local required
    for required in deploy/termux/launcher ofbackup_cli.py requirements/termux.txt backend frontend; do
        if [[ ! -e "$dir/$required" ]]; then
            echo "La actualización no contiene el componente requerido: $required" >&2
            return 1
        fi
    done
    return 0
}

# ── Copia sin bytecode ────────────────────────────────────────────────────
# cp -R copiaría __pycache__ y .pyc de otra versión de Python; en un móvil,
# además, ocupa espacio de más.
copy_tree_without_pycache() {
    local source="$1"
    local target="$2"
    mkdir -p "$target"
    cp -R -- "$source/." "$target/"
    find "$target" -type d -name '__pycache__' -prune -exec rm -rf -- {} + 2>/dev/null || true
    find "$target" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
}

# ── Respaldo y rollback ───────────────────────────────────────────────────
backup_previous() {
    BACKUP_DIR="$CACHE_DIR/rollback.$$"
    rm -rf -- "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR/app" "$BACKUP_DIR/bin"
    local item
    for item in ofbackup_cli.py backend frontend requirements-termux.txt; do
        if [[ -e "$APP_HOME/$item" ]]; then
            mv -- "$APP_HOME/$item" "$BACKUP_DIR/app/$item"
        fi
    done
    for item in of ofbackup; do
        if [[ -e "$PREFIX_BIN/$item" ]]; then
            mv -- "$PREFIX_BIN/$item" "$BACKUP_DIR/bin/$item"
        fi
    done
}

restore_previous() {
    [[ -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]] || return 0
    echo "↩ Restaurando la versión anterior…"
    rm -rf -- "$APP_HOME/backend" "$APP_HOME/frontend"
    rm -f -- "$APP_HOME/ofbackup_cli.py" "$APP_HOME/requirements-termux.txt"
    local item
    for item in ofbackup_cli.py backend frontend requirements-termux.txt; do
        if [[ -e "$BACKUP_DIR/app/$item" ]]; then
            mv -- "$BACKUP_DIR/app/$item" "$APP_HOME/$item"
        fi
    done
    for item in of ofbackup; do
        if [[ -e "$BACKUP_DIR/bin/$item" ]]; then
            mv -- "$BACKUP_DIR/bin/$item" "$PREFIX_BIN/$item"
        fi
    done
    rm -rf -- "$BACKUP_DIR"
    BACKUP_DIR=""
}

cleanup() {
    # Si queda respaldo es que la actualización no terminó bien: mejor volver a
    # la versión anterior que dejar la aplicación a medias.
    if [[ -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]]; then
        restore_previous || true
    fi
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}

trap cleanup EXIT
trap 'exit 130' INT TERM

on_error() {
    local code="$?"
    local line="$1"
    trap - ERR
    echo "✗ Falló la actualización en la línea $line (código $code)." >&2
    echo "Registro completo: $LOG_FILE" >&2
    exit "$code"
}
trap 'on_error "$LINENO"' ERR

# ── Origen del código ─────────────────────────────────────────────────────
stage_source() {
    if [[ -n "$LOCAL_SOURCE" ]]; then
        [[ -d "$LOCAL_SOURCE" ]] || fail "La copia local indicada no existe: $LOCAL_SOURCE"
        SOURCE_DIR="$(cd -- "$LOCAL_SOURCE" && pwd)"
        echo "Usando la copia local: $SOURCE_DIR"
        required_components_present "$SOURCE_DIR" || fail "La copia local no contiene todos los componentes de OF Downloader."
        return 0
    fi

    command -v curl >/dev/null 2>&1 || fail "Falta curl. Ejecuta: pkg install -y curl"
    command -v tar >/dev/null 2>&1 || fail "Falta tar. Ejecuta: pkg install -y tar"

    echo "Descargando solo el código actualizado…"
    TEMP_DIR="$(mktemp -d "$CACHE_DIR/incremental.XXXXXX")" || \
        fail "No se pudo crear la carpeta temporal de actualización."
    local archive="$TEMP_DIR/of-downloader-main.tar.gz"
    SOURCE_DIR="$TEMP_DIR/source"
    # --proto '=https' y --tlsv1.2 evitan una degradación silenciosa a HTTP.
    if ! curl -fL --retry 3 --retry-delay 1 --connect-timeout 15 \
        --proto '=https' --tlsv1.2 \
        "$REPOSITORY_ARCHIVE_URL" -o "$archive"; then
        fail "No se pudo obtener la actualización desde GitHub."
    fi
    mkdir -p "$SOURCE_DIR"
    tar -xzf "$archive" -C "$SOURCE_DIR" --strip-components=1 || \
        fail "El paquete de actualización está incompleto o no es válido."
    required_components_present "$SOURCE_DIR" || fail "La actualización no contiene todos los componentes requeridos."
}

# ── Inicio ────────────────────────────────────────────────────────────────
echo "=== OF Downloader · actualización ==="
echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S %z')"
echo "Termux: ${PREFIX:-desconocido}"
echo "Arquitectura: $(uname -m 2>/dev/null || echo desconocida)"
echo "Contenedor: $CONTAINER"
echo "Registro: $LOG_FILE"

if [[ "${PREFIX:-}" != *"com.termux"* ]]; then
    fail "Este actualizador debe ejecutarse dentro de Termux."
fi

command -v proot-distro >/dev/null 2>&1 || \
    fail "Falta proot-distro. Ejecuta primero la instalación de OF Downloader."

if ! venv_python_present; then
    fail "No encuentro el motor instalado en $APP_HOME. Ejecuta instalar-termux.sh una sola vez."
fi

CONTAINER_DIR="${PREFIX}/var/lib/proot-distro/containers/${CONTAINER}/rootfs"
if [[ ! -d "$CONTAINER_DIR" ]]; then
    fail "No encuentro Debian ($CONTAINER). Ejecuta instalar-termux.sh una sola vez."
fi

mkdir -p "$CACHE_DIR"
chmod 700 "$CACHE_DIR" 2>/dev/null || true

stage_source

requirements_changed=0
if [[ ! -f "$APP_HOME/requirements-termux.txt" ]] || \
   ! cmp -s "$SOURCE_DIR/requirements/termux.txt" "$APP_HOME/requirements-termux.txt"; then
    requirements_changed=1
fi

echo "Aplicando el código nuevo…"
backup_previous

install -m 600 -- "$SOURCE_DIR/ofbackup_cli.py" "$APP_HOME/ofbackup_cli.py" || \
    fail "No se pudo copiar ofbackup_cli.py."
copy_tree_without_pycache "$SOURCE_DIR/backend" "$APP_HOME/backend"
copy_tree_without_pycache "$SOURCE_DIR/frontend" "$APP_HOME/frontend"
chmod -R u=rwX,go= "$APP_HOME/backend" "$APP_HOME/frontend"
install -m 600 -- "$SOURCE_DIR/requirements/termux.txt" "$APP_HOME/requirements-termux.txt" || \
    fail "No se pudo copiar requirements-termux.txt."

for component in of ofbackup; do
    install -m 755 -- "$SOURCE_DIR/deploy/termux/launcher" "$PREFIX_BIN/$component" || \
        fail "No se pudo instalar el comando $component."
done

if [[ ! -f "$APP_HOME/backend/constants.py" ]] || \
   [[ ! -f "$APP_HOME/backend/queue/__init__.py" ]] || \
   [[ ! -f "$APP_HOME/frontend/progress.py" ]]; then
    fail "La actualización quedó incompleta: faltan paquetes Python."
fi

if [[ "$requirements_changed" -eq 1 ]]; then
    echo "Las dependencias cambiaron; actualizando solo Python…"
    if ! proot-distro login --shared-home "$CONTAINER" -- \
        "$CONTAINER_APP_HOME/.venv/bin/python" -m pip install --upgrade \
        -r "$CONTAINER_APP_HOME/requirements-termux.txt"; then
        fail "No se pudieron actualizar las dependencias Python."
    fi
else
    echo "Dependencias Python sin cambios; se conservan las instaladas."
fi

if ! proot-distro login --shared-home "$CONTAINER" -- \
    "$CONTAINER_APP_HOME/.venv/bin/python" -m py_compile \
    "$CONTAINER_APP_HOME/ofbackup_cli.py"; then
    fail "La actualización no superó la comprobación del código Python."
fi

# Todo correcto: el respaldo ya no hace falta.
rm -rf -- "$BACKUP_DIR"
BACKUP_DIR=""

echo "✓ OF Downloader actualizado sin reinstalar Debian, Python ni FFmpeg."
echo "✓ Cookie, perfiles, configuración y descargas se conservaron."
echo "Registro completo: $LOG_FILE"
echo "Ejecuta: of"
