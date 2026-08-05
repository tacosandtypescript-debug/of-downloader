"""Servicio de terminal para OF Downloader.

Centraliza colores ANSI, estilo de menú, y renderizado de UI en terminal.
"""

from __future__ import annotations

import os
import sys


class TerminalService:
    """Gestiona la presentación visual en terminal."""

    PALETTE = {
        "cyan":   "38;2;0;175;240",
        "blue":   "38;2;0;140;207",
        "navy":   "38;2;0;92;143",
        "white":  "38;2;245;250;255",
        "muted":  "38;2;148;180;200",
        "green":  "38;2;32;213;166",
        "yellow": "38;2;255;200;87",
        "red":    "38;2;255;77;103",
    }

    MENU_LOGO_LINES = (
        "⣠⣾⣿⣷⣦⣴⣿⣿⣿⠟",
        "⣿⣿⠁⠈⣿⣿⣿⡿⠋",
        "⢿⣿⣦⣴⣿⣿⣿⣶⡄",
        "⠀⠻⣿⣿⡿⠟⠉",
    )

    # ── Detección de soporte ──────────────────────────────────────────────

    def ansi_supported(self) -> bool:
        if os.getenv("NO_COLOR"):
            return False
        if not sys.stdout.isatty():
            return False
        if os.name != "nt":
            return os.getenv("TERM", "").lower() != "dumb"
        return bool(
            os.getenv("WT_SESSION")
            or os.getenv("ANSICON")
            or os.getenv("ConEmuANSI", "").upper() == "ON"
            or os.getenv("TERM_PROGRAM")
        )

    def colors_enabled(self) -> bool:
        return self.ansi_supported()

    # ── Estilo ────────────────────────────────────────────────────────────

    def styled(self, message: str, color: str = "white", *, bold: bool = False) -> str:
        if not self.colors_enabled():
            return message
        weight = "1;" if bold else ""
        return f"\033[{weight}{self.PALETTE[color]}m{message}\033[0m"

    def status_text(self, message: str, color: str) -> str:
        return self.styled(message, color)

    # ── Menú ──────────────────────────────────────────────────────────────

    def menu_option(self, number: str, label: str) -> None:
        badge = self.styled(f"[{number}]", "cyan", bold=True)
        print(f"  {badge} {self.styled(label, 'white')}")

    def menu_banner_line(self, message: str, color: str = "cyan", *, bold: bool = False) -> None:
        if len(message) > 44:
            raise ValueError("La línea del encabezado supera 44 caracteres.")
        border = self.styled("│", "cyan", bold=True)
        print(border + self.styled(message.ljust(44), color, bold=bold) + border)

    def menu_brand_line(self, label: str, logo_line: str) -> None:
        left = f"  {label}".ljust(20)
        print(self.styled(left, "white", bold=bool(label)) + self.styled(logo_line, "blue", bold=True))

    # ── Badges ────────────────────────────────────────────────────────────

    def update_badge(self, status: str | None = None) -> str:
        status = status or os.getenv("OFDOWNLOADER_UPDATE_STATUS", "unknown")
        if status == "available":
            return self.styled("● ACTUALIZACIÓN DISPONIBLE", "yellow", bold=True)
        if status == "current":
            return self.styled("● AL DÍA", "green", bold=True)
        if status == "diverged":
            return self.styled("● REVISAR REPOSITORIO", "yellow", bold=True)
        return self.styled("● NO COMPROBADA", "muted")

    def update_notification(self, status: str | None = None) -> str | None:
        status = status or os.getenv("OFDOWNLOADER_UPDATE_STATUS", "unknown")
        if status == "available":
            return self.styled(
                "  ⚠ NOTIFICACIÓN: hay una actualización disponible. "
                "Elige [8] para instalarla y reiniciar.", "yellow", bold=True)
        if status == "diverged":
            return self.styled(
                "  ⚠ NOTIFICACIÓN: el repositorio local y remoto han divergido. "
                "Revisa el repositorio antes de actualizar.", "yellow", bold=True)
        if status == "offline":
            return self.styled(
                "  · Actualizaciones: no se pudo comprobar la conexión.", "muted")
        return None


# ── Singleton ────────────────────────────────────────────────────────────

_terminal_service: TerminalService | None = None


def get_terminal_service() -> TerminalService:
    global _terminal_service
    if _terminal_service is None:
        _terminal_service = TerminalService()
    return _terminal_service


# ── Funciones de compatibilidad ──────────────────────────────────────────

def colors_enabled() -> bool:
    return get_terminal_service().colors_enabled()


def ansi_supported() -> bool:
    return get_terminal_service().ansi_supported()


def styled(message: str, color: str = "white", *, bold: bool = False) -> str:
    return get_terminal_service().styled(message, color, bold=bold)


def menu_option(number: str, label: str) -> None:
    get_terminal_service().menu_option(number, label)


def menu_banner_line(message: str, color: str = "cyan", *, bold: bool = False) -> None:
    get_terminal_service().menu_banner_line(message, color, bold=bold)


def menu_brand_line(label: str, logo_line: str) -> None:
    get_terminal_service().menu_brand_line(label, logo_line)
