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
installer_tmp="$(mktemp)"
curl -fsSL "$installer_url" -o "$installer_tmp"
bash "$installer_tmp" "$@"
status=$?
rm -f "$installer_tmp"
exit "$status"
