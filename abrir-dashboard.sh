#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if command -v of >/dev/null 2>&1; then
  exec of dashboard
fi
exec bash "$ROOT/iniciar.sh" dashboard
