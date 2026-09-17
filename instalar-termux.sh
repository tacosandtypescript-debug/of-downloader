#!/data/data/com.termux/files/usr/bin/bash
# Atajo público. Implementación: deploy/termux/instalar.sh
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi
set -euo pipefail
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$ROOT/deploy/termux/instalar.sh" ]]; then
        exec bash "$ROOT/deploy/termux/instalar.sh" "$@"
    fi
fi
installer_url="${OFBACKUP_INSTALLER_URL:-https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/deploy/termux/instalar.sh}"
installer_tmp="$(mktemp)" || exit 1
# Sin este trap, un fallo de curl dejaba el temporal en el dispositivo.
trap 'rm -f "$installer_tmp"' EXIT INT TERM
curl -fL --retry 3 --retry-delay 1 --connect-timeout 15 \
    --proto '=https' --tlsv1.2 "$installer_url" -o "$installer_tmp"
bash "$installer_tmp" "$@"
status=$?
exit "$status"
