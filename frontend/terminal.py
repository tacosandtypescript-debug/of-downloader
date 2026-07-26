"""Colores y utilidades de terminal del frontend CLI."""

from __future__ import annotations


def styled(message: str, color: str = "white", *, bold: bool = False) -> str:
    from ofbackup_cli import styled as style
    return style(message, color, bold=bold)


def colors_enabled() -> bool:
    from ofbackup_cli import colors_enabled as enabled
    return enabled()

