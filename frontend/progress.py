"""Renderizador de progreso para el frontend CLI."""

from __future__ import annotations

import os
import shutil
import sys


PALETTE = {
    "cyan": "38;2;0;175;240",
    "green": "92",
    "gray": "90",
    "red": "38;2;255;77;103",
}


def colors_enabled() -> bool:
    if os.getenv("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return os.getenv("TERM", "").lower() != "dumb"
    # PowerShell clasico no interpreta ANSI y mostraria los escapes crudos.
    return bool(
        os.getenv("WT_SESSION")
        or os.getenv("ANSICON")
        or os.getenv("ConEmuANSI", "").upper() == "ON"
        or os.getenv("TERM_PROGRAM")
    )


def show_download_progress(percent: int | None, label: str, *, failed: bool = False) -> None:
    columns = shutil.get_terminal_size((60, 20)).columns
    width = max(10, min(24, columns - 36))
    if percent is None:
        percent_text = "--"
        filled = 0
    else:
        percent = min(100, max(0, percent))
        percent_text = f"{percent:02d}"
        filled = percent * width // 100
    if colors_enabled():
        bar = (
            f"\033[1;{PALETTE['green']}m{'▰' * filled}"
            f"\033[0;{PALETTE['gray']}m{'▱' * (width - filled)}\033[0m"
        )
    else:
        bar = "#" * filled + "-" * (width - filled)
    max_label = max(12, columns - width - 10)
    if len(label) > max_label:
        label = label[: max_label - 1].rstrip() + "…"
    message = f"{bar} {percent_text}% {label}"
    if sys.stdout.isatty():
        prefix = "\033[2K\r"
        if colors_enabled():
            color = PALETTE["red"] if failed else PALETTE["cyan"]
            # La barra ya lleva sus colores; coloreamos solo el texto.
            print(f"{prefix}{bar} \033[1;{color}m{percent_text}% {label}\033[0m", end="", flush=True)
        else:
            print(prefix + message, end="", flush=True)
    else:
        print(message)
