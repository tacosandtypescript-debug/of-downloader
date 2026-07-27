"""Persistencia de trabajos de la cola, aislada del servidor HTTP."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class QueueStore:
    """Almacena snapshots JSON usando las escrituras seguras del CLI."""

    def __init__(self, path: Path, read_json: Callable[[Path], Any], write_json: Callable[[Path, Any], None]):
        self.path = path
        self._read_json = read_json
        self._write_json = write_json

    def load(self, limit: int = 50) -> list[dict[str, Any]]:
        payload = self._read_json(self.path)
        rows = payload.get("jobs", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return []
        return [row for row in rows[-limit:] if isinstance(row, dict)]

    def save(self, rows: list[dict[str, Any]], limit: int = 50) -> None:
        self._write_json(self.path, {"jobs": rows[-limit:]})
