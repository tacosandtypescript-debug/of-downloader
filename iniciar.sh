#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 no está instalado."
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)'; then
    echo "Se necesita Python 3.11, 3.12 o 3.13."
    echo "En Termux ejecuta ./instalar-termux.sh para usar Python 3.13 en Debian."
    exit 1
fi
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
