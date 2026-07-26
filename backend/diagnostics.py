"""Diagnóstico del entorno de ejecución."""

from __future__ import annotations


def diagnostics() -> None:
    import ofbackup_cli
    ofbackup_cli.diagnostics()


def test_profile_lookup(username: str | None = None, timeout: int = 120) -> int:
    import ofbackup_cli
    return ofbackup_cli.test_profile_lookup(username, timeout=timeout)

