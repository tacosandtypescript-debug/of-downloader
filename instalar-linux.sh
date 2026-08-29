#!/usr/bin/env bash
# Atajo público. Implementación: deploy/linux/instalar.sh
set -euo pipefail
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$ROOT/deploy/linux/instalar.sh" ]]; then
        exec bash "$ROOT/deploy/linux/instalar.sh" "$@"
    fi
fi
echo "Este instalador debe ejecutarse desde el clon del repositorio:"
echo "  bash deploy/linux/instalar.sh"
exit 1
