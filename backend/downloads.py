"""Servicios de descarga reutilizables por el frontend CLI."""

from __future__ import annotations


def _cli():
    import ofbackup_cli
    return ofbackup_cli


def run_ofscraper(arguments: list[str], *, mode: str = "publicacion", target: str | None = None) -> int:
    return _cli().run_ofscraper(arguments, mode=mode, target=target)


def download_user(username: str | None = None, *, source: str = "menu") -> int:
    return _cli().download_user(username, source=source)


def download_link(url: str | None = None) -> int:
    return _cli().download_link(url)


def build_complete_profile_command(username: str) -> list[str]:
    return _cli().build_complete_profile_command(username)


def normalize_url(value: str) -> str:
    return _cli().normalize_url(value)

