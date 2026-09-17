#!/bin/sh
# Atajo público. Implementación: deploy/ios/instalar.sh
set -eu
if [ -n "${0:-}" ] && [ -f "$0" ]; then
    # shellcheck disable=SC1007  # CDPATH= vacío evita que cd imprima la ruta
    ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
    if [ -f "$ROOT/deploy/ios/instalar.sh" ]; then
        exec sh "$ROOT/deploy/ios/instalar.sh" "$@"
    fi
fi
installer_url="${OF_IOS_INSTALLER_URL:-https://raw.githubusercontent.com/tacosandtypescript-debug/of-downloader/main/deploy/ios/instalar.sh}"
curl -fsSL "$installer_url" | sh
