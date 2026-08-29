#!/data/data/com.termux/files/usr/bin/bash
# Atajo público. Implementación: deploy/termux/actualizar.sh
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi
set -euo pipefail
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$ROOT/deploy/termux/actualizar.sh" ]]; then
        exec bash "$ROOT/deploy/termux/actualizar.sh" "$@"
    fi
fi
updater_url="${OFBACKUP_UPDATE_SCRIPT_URL:-https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/deploy/termux/actualizar.sh}"
updater_tmp="$(mktemp)"
curl -fsSL "$updater_url" -o "$updater_tmp"
bash "$updater_tmp" "$@"
status=$?
rm -f "$updater_tmp"
exit "$status"
