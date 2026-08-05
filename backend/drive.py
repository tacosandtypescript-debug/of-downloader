"""Servicio de Google Drive para OF Downloader.

Centraliza la lógica de rclone: cola de subida, configuración de remotes,
y subida automática tras cada descarga.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from backend.models import UserError


class DriveService:
    """Gestiona la integración con Google Drive vía rclone."""

    DRIVE_LOG_NAME = "google-drive.log"
    DRIVE_QUEUE_PATH = Path.home() / ".config" / "ofbackup" / "drive-pending.json"

    def __init__(self, config_service=None):
        self._config = config_service

    # ── rclone ────────────────────────────────────────────────────────────

    @staticmethod
    def find_rclone() -> str | None:
        configured = os.getenv("RCLONE_BIN")
        if configured:
            resolved = shutil.which(configured) or configured
            if Path(resolved).is_file():
                return str(Path(resolved))
        return shutil.which("rclone")

    def remote_configured(self, remote: str) -> bool:
        executable = self.find_rclone()
        if not executable:
            return False
        completed = subprocess.run(
            [executable, "listremotes"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", check=False,
        )
        if completed.returncode:
            return False
        wanted = remote.rstrip(":") + ":"
        return wanted in {line.strip() for line in completed.stdout.splitlines()}

    # ── Cola de archivos ─────────────────────────────────────────────────

    def queue(self) -> list[dict[str, str]]:
        from ofbackup_cli import read_json
        data = read_json(self.DRIVE_QUEUE_PATH, {"items": []})
        items = data.get("items", [])
        return items if isinstance(items, list) else []

    def save_queue(self, items: list[dict[str, str]]) -> None:
        from ofbackup_cli import secure_write_json
        secure_write_json(self.DRIVE_QUEUE_PATH, {"items": items})

    def enqueue(self, files: list[Path], destination: Path, state: dict | None = None) -> int:
        from ofbackup_cli import get_state
        state = state or get_state()
        destination = destination.expanduser()
        queued = self.queue()
        seen = {(item.get("local"), item.get("remote")) for item in queued}
        added = 0
        for file in files:
            try:
                relative = file.expanduser().resolve().relative_to(destination.resolve())
            except (OSError, ValueError):
                relative = Path(file.name)
            remote = str(state.get("drive_remote") or "gdrive").rstrip(":")
            folder = str(state.get("drive_folder") or "OFDownloader").strip().strip("/\\")
            target = f"{remote}:{folder}/{relative.as_posix()}"
            item = {"local": str(file), "remote": target}
            key = (item["local"], item["remote"])
            if key in seen:
                continue
            queued.append(item)
            seen.add(key)
            added += 1
        if added:
            self.save_queue(queued)
        return added

    def upload_pending(self, *, quiet: bool = False) -> int:
        from ofbackup_cli import get_state
        state = get_state()
        destination = Path(state["download_dir"]).expanduser()
        executable = self.find_rclone()
        if not executable:
            if not quiet:
                print("rclone no esta instalado.")
            return 2
        if not self.remote_configured(str(state.get("drive_remote", "gdrive"))):
            if not quiet:
                print(f"Google Drive no esta configurado.")
            return 2

        items = self.queue()
        if not items:
            if not quiet:
                print("No hay archivos pendientes para Google Drive.")
            return 0

        remaining: list[dict[str, str]] = []
        uploaded = 0
        for item in items:
            local = Path(str(item.get("local", ""))).expanduser()
            remote = str(item.get("remote", ""))
            if not local.is_file() or not remote:
                continue
            completed = subprocess.run(
                [executable, "copyto", str(local), remote, "--create-empty-src-dirs"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", check=False,
            )
            if completed.returncode == 0:
                uploaded += 1
                if state.get("drive_delete_after_upload"):
                    try:
                        local.unlink()
                    except OSError:
                        pass
            else:
                remaining.append(item)

        self.save_queue(remaining)
        if not quiet:
            print(f"Google Drive: {uploaded} subidos, {len(remaining)} fallidos.")
        return 0 if len(remaining) == 0 else 1

    def status_text(self, state: dict | None = None) -> str:
        from ofbackup_cli import get_state
        state = state or get_state()
        if not self.find_rclone():
            return "rclone no instalado"
        if not self.remote_configured(str(state.get("drive_remote", "gdrive"))):
            return f"remote {state.get('drive_remote', 'gdrive')} no configurado"
        return "configurado"


# ── Singleton ────────────────────────────────────────────────────────────

_drive_service: DriveService | None = None


def get_drive_service() -> DriveService:
    global _drive_service
    if _drive_service is None:
        _drive_service = DriveService()
    return _drive_service
