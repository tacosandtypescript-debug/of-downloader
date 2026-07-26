"""Menú CLI público, conservado durante la separación."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    from ofbackup_cli import main as cli_main
    return cli_main(argv)


def interactive_menu() -> int:
    from ofbackup_cli import menu
    return menu()

