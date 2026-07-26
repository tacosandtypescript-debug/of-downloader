"""Servicios de autenticación expuestos por el backend."""

from __future__ import annotations


def _cli():
    import ofbackup_cli
    return ofbackup_cli


def configure_credentials() -> int:
    return _cli().configure_credentials()


def credentials_ready() -> bool:
    return _cli().credentials_ready()


def require_credentials() -> None:
    _cli().require_credentials()


def import_credentials_file(path) -> None:
    _cli().import_credentials_file(path)


def receive_credentials_locally(*, port: int = 8765, show_qr: bool = False) -> int:
    return _cli().receive_credentials_locally(port=port, show_qr=show_qr)


def test_credentials(timeout: int = 60) -> int:
    return _cli().test_credentials(timeout=timeout)

