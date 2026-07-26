"""Punto de entrada del frontend CLI conservando la interfaz histórica."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Delegar en el CLI legado durante la migración sin cambiar comandos."""
    from ofbackup_cli import main as legacy_main

    return legacy_main(argv)

