"""Persistencia, rutas, medios y registros."""

from __future__ import annotations


def _cli():
    import ofbackup_cli
    return ofbackup_cli


def get_state() -> dict:
    return _cli().get_state()


def save_state(state: dict) -> None:
    _cli().save_state(state)


def media_snapshot(root):
    return _cli().media_snapshot(root)


def changed_media_files(before, after):
    return _cli().changed_media_files(before, after)


def write_visible_log(destination, filename: str, content: str):
    return _cli().write_visible_log(destination, filename, content)


def mirror_download_log(destination):
    return _cli().mirror_download_log(destination)

