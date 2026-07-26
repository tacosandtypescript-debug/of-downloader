"""Integración con Google Drive mediante rclone."""

from __future__ import annotations


def _cli():
    import ofbackup_cli
    return ofbackup_cli


def drive_command(args: list[str]) -> int:
    return _cli().drive_command(args)


def drive_status_text(state: dict | None = None) -> str:
    return _cli().drive_status_text(state)


def upload_drive_queue(*, quiet: bool = False) -> int:
    return _cli().upload_drive_queue(quiet=quiet)


def maybe_upload_to_drive(files, destination) -> None:
    _cli().maybe_upload_to_drive(files, destination)

