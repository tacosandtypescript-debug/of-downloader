"""Actualización del motor y de la aplicación."""

from __future__ import annotations


def update_engine() -> int:
    import ofbackup_cli
    return ofbackup_cli.update_engine()

