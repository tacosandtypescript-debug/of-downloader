#!/bin/bash
# Ejecuta el CLI desde el clon. Tras instalar, el comando público es `of`.
set -e
cd "$(cd "$(dirname "$0")/../.." && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 no está instalado."
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)'; then
    echo "Se necesita Python 3.11, 3.12 o 3.13."
    echo "En Termux ejecuta ./instalar-termux.sh (o deploy/termux/instalar.sh) para usar Python 3.13 en Debian."
    exit 1
fi
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements/desktop.txt
OFDOWNLOADER_PLATFORM=LINUX .venv/bin/python ofbackup_cli.py "$@"
