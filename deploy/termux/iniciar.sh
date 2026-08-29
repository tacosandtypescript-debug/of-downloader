#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
exec bash "$(cd "$(dirname "$0")" && pwd)/launcher" "$@"
